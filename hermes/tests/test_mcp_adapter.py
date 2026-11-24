import importlib.util
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from mcp.types import TextResourceContents


def load_plugin():
    path = Path(__file__).resolve().parents[1] / "deltachat_mcp" / "__init__.py"
    spec = importlib.util.spec_from_file_location("release_hermes_deltachat", path)
    plugin = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = plugin
    spec.loader.exec_module(plugin)
    return plugin


def load_adapter(plugin):
    # CI supplies the installed MCP SDK. VM acceptance supplies the installed
    # Hermes gateway. Here the Hermes doubles cover only the adapter boundary.
    class BaseAdapter:
        def __init__(self, *, config, platform):
            self.config = config
            self.platform = platform

        def build_source(self, **kwargs):
            return SimpleNamespace(**kwargs)

    modules = {name: ModuleType(name) for name in (
        "gateway", "gateway.config", "gateway.platforms", "gateway.platforms.base",
    )}
    modules["gateway.config"].Platform = str
    base = modules["gateway.platforms.base"]
    base.BasePlatformAdapter = BaseAdapter
    base.MessageEvent = SimpleNamespace
    base.MessageType = SimpleNamespace(TEXT="text")
    base.ProcessingOutcome = SimpleNamespace(SUCCESS="success", FAILURE="failure")
    base.SendResult = SimpleNamespace
    with patch.dict(sys.modules, modules):
        return __import__(plugin.__name__ + ".adapter", fromlist=["adapter"])


plugin = load_plugin()
adapter_module = load_adapter(plugin)
PEER = "peer@example.invalid"
CHAT = 123


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        state = TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.env = patch.dict(os.environ, {
            "DELTACHAT_MCP_URL": "http://127.0.0.1:12345/mcp",
            "DELTACHAT_MCP_STATE_DIR": state.name,
            "DELTACHAT_MCP_PEER_ADDR": PEER,
            "DELTACHAT_MCP_PEER_CHAT_ID": str(CHAT),
            "DELTACHAT_ALLOWED_USERS": PEER,
            "DELTACHAT_MCP_HELP_ONLY": "1",
            "DELTACHAT_MCP_TOKEN": "z" * 64,
        }, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.config = SimpleNamespace(extra={})
        self.adapter = self.build_adapter()

    def build_adapter(self):
        adapter = adapter_module.McpDeltaChatAdapter(self.config, plugin.Settings.load(self.config))
        adapter._ledger.initialize()

        async def handle(event):
            event._gateway_accepted = True
            await adapter.on_processing_complete(event, adapter_module.ProcessingOutcome.SUCCESS)

        adapter.handle_message = AsyncMock(side_effect=handle)
        return adapter

    @staticmethod
    def message(**changes):
        return {"id": 42, "chat_id": CHAT, "chat_type": "Single", "text": "/help",
                "sender_addr": PEER, "is_encrypted": True, "is_contact_request": False, **changes}

    def test_plugin_registers_normal_deltachat_platform(self):
        registry = Mock()
        plugin.register(registry)
        hooks = registry.register_platform.call_args.kwargs
        self.assertEqual(hooks["name"], "deltachat")
        self.assertTrue(hooks["check_fn"]())
        self.assertTrue(hooks["validate_config"](self.config))
        self.assertEqual(hooks["env_enablement_fn"](), {"mcp_url": os.environ["DELTACHAT_MCP_URL"]})
        with patch.dict(sys.modules, {adapter_module.__name__: adapter_module}):
            self.assertIsInstance(hooks["adapter_factory"](self.config), adapter_module.McpDeltaChatAdapter)
        with patch.dict(os.environ, {"DELTACHAT_ACCOUNTS_DIR": "/unused"}):
            self.assertFalse(hooks["check_fn"]())
            self.assertIsNone(hooks["env_enablement_fn"]())

    def test_only_local_endpoint_and_private_state(self):
        for endpoint in ("https://127.0.0.1:12345/mcp", "http://example.invalid:12345/mcp",
                         "http://127.0.0.1:12345/mcp?arg=1"):
            with self.subTest(endpoint=endpoint), patch.dict(os.environ, {"DELTACHAT_MCP_URL": endpoint}):
                with self.assertRaises(ValueError):
                    plugin.Settings.load()
        with patch.dict(os.environ, {"DELTACHAT_MCP_STATE_DIR": "/tmp"}), self.assertRaises(ValueError):
            plugin.Settings.load()

    async def test_help_reaches_gateway_and_retains_result_across_restart(self):
        await self.adapter._dispatch(self.message())
        event = self.adapter.handle_message.await_args.args[0]
        self.assertEqual(event.text, "/help")
        self.assertEqual(event.source.user_id, PEER)
        self.assertEqual(self.adapter.mcp_counts["complete"], 1)
        restarted = self.build_adapter()
        await restarted._dispatch(self.message())
        restarted.handle_message.assert_not_awaited()

    async def test_help_only_filters_backlog_and_checks_encrypted_accepted_peer(self):
        for message_id, changes in enumerate((
            {"is_contact_request": True}, {"is_encrypted": False},
            {"chat_id": 99}, {"sender_addr": "another@example.invalid"},
            {"chat_type": "Group"}, {"text": "normal text"}, {"text": "/stop"},
        ), 1):
            await self.adapter._dispatch(self.message(id=message_id, **changes))
        self.adapter.handle_message.assert_not_awaited()
        self.assertEqual(self.adapter.mcp_counts["outside_accepted_peer"], 5)
        self.assertEqual(self.adapter.mcp_counts["help_only_filtered"], 2)

    async def test_resource_and_catch_up_digest_dispatch_message_once(self):
        message = self.message()
        uri = adapter_module.INCOMING
        snapshot = TextResourceContents(uri=uri, text=json.dumps({"gap": 0, "messages": [message]}))
        result = SimpleNamespace(is_error=False, structured_content={
            "chats": [{"chat_id": CHAT, "messages": [message]}],
        })
        client = SimpleNamespace(
            read_resource=AsyncMock(return_value=SimpleNamespace(contents=[snapshot])),
            call_tool=AsyncMock(return_value=result),
        )
        await self.adapter._refresh(client, catch_up=True)
        await self.adapter._refresh(client, catch_up=False)
        self.adapter.handle_message.assert_awaited_once()

    async def test_ambiguous_send_is_not_replayed(self):
        client = SimpleNamespace(call_tool=AsyncMock(side_effect=TimeoutError))
        self.adapter._client = client
        denied = await self.adapter.send(str(CHAT), "plain text")
        self.assertFalse(denied.success)
        client.call_tool.assert_not_awaited()
        await self.adapter._dispatch(self.message())
        result = await self.adapter._send_with_retry(str(CHAT), "plain text")
        self.assertFalse(result.success)
        client.call_tool.assert_awaited_once_with("send_message", {
            "chat_id": CHAT, "text": "plain text", "require_encryption": True,
        })
        denied = await self.adapter.send("99", "plain text")
        self.assertFalse(denied.success)
        self.assertEqual(client.call_tool.await_count, 1)


if __name__ == "__main__":
    unittest.main()
