"""Exercise the installed console script, MCP transports, and native core."""

import os
import subprocess
import sys
from pathlib import Path

import anyio
import httpx2
import pytest
from deltachat2 import IOTransport, Rpc
from mcp import Client, StdioServerParameters

from deltachat_mcp.rpc import CoreError, DeltaChatRPC
from deltachat_mcp.tools import get_unread_count

TOOL_NAMES = {"send_message", "list_chats", "get_messages", "get_unread_count"}
VENV_BIN = Path(sys.executable).parent


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def isolated_env(tmp_path):
    return {
        "PATH": os.pathsep.join((str(VENV_BIN), os.environ.get("PATH", ""))),
        "DC_ACCOUNTS": str(tmp_path / "accounts"),
        "DC_ADDR": "",
        "DC_MAIL_PW": "",
        "BACKUP_STRING": "",
    }


@pytest.fixture
def configured_env(isolated_env):
    # Setting configured_addr on a fresh core creates its offline, test-only
    # pseudo transport. No mailbox credentials or external recipients are used.
    with IOTransport(
        accounts_dir=isolated_env["DC_ACCOUNTS"],
        rpc_executable=str(VENV_BIN / "deltachat-rpc-server"),
        stderr=subprocess.DEVNULL,
    ) as transport:
        rpc = Rpc(transport)
        account_id = rpc.add_account()
        rpc.set_config(account_id, "configured_addr", "test@example.invalid")
        assert rpc.is_configured(account_id)
    return isolated_env


@pytest.mark.anyio
@pytest.mark.parametrize("mode", ["auto", "legacy"])
async def test_stdio_console_script_reads_native_core(configured_env, mode):
    server = StdioServerParameters(
        command=str(VENV_BIN / "deltachat-mcp"),
        env={**configured_env, "MCP_MODE": "stdio", "PATH": os.defpath},
    )
    with anyio.fail_after(10):
        async with Client(server, mode=mode, read_timeout_seconds=5) as client:
            assert (client.protocol_version == "2026-07-28") == (mode == "auto")
            result = await client.list_tools()
            assert {tool.name for tool in result.tools} == TOOL_NAMES
            send = next(tool for tool in result.tools if tool.name == "send_message")
            schema = send.model_dump(by_alias=True)["inputSchema"]
            assert set(schema["properties"]) == {"text", "chat_id", "addr"}
            assert schema["required"] == ["text"]
            assert schema["oneOf"] == [{"required": ["addr"]}, {"required": ["chat_id"]}]
            result = await client.call_tool("list_chats", {})
            wire = result.model_dump(by_alias=True)
            assert not wire["isError"]
            assert wire["structuredContent"] == {"chats": []}
            invalid = await client.call_tool("send_message", {"text": ""})
            assert invalid.model_dump(by_alias=True)["isError"]


@pytest.mark.anyio
async def test_http_reads_native_core_and_rejects_foreign_origins(configured_env, free_tcp_port):
    port = free_tcp_port
    command = [str(VENV_BIN / "deltachat-mcp")]
    env = {**os.environ, **configured_env, "MCP_MODE": "http", "MCP_PORT": str(port)}
    url = f"http://127.0.0.1:{port}/tool"
    async with await anyio.open_process(command, env=env, stdout=subprocess.DEVNULL) as process:
        try:
            async with httpx2.AsyncClient(trust_env=False, timeout=2) as http:
                with anyio.fail_after(8):
                    while process.returncode is None:
                        try:
                            await http.get(url)
                        except httpx2.ConnectError:
                            await anyio.sleep(0.05)
                        else:
                            break
                    assert process.returncode is None, "MCP HTTP server exited during startup"

                rejected = await http.post(
                    url,
                    headers={"Origin": "http://example.com"},
                    json={"jsonrpc": "2.0", "method": "server/discover", "id": 1},
                )
                assert rejected.status_code == 403

            for mode in ("auto", "legacy"):
                with anyio.fail_after(8):
                    async with Client(url, mode=mode, read_timeout_seconds=5) as client:
                        assert (client.protocol_version == "2026-07-28") == (mode == "auto")
                        result = await client.call_tool("get_unread_count", {})
                        wire = result.model_dump(by_alias=True)
                        assert not wire["isError"]
                        assert wire["structuredContent"] == {"unread_count": 0}
        finally:
            if process.returncode is None:
                process.terminate()
                with anyio.move_on_after(5, shield=True):
                    await process.wait()


@pytest.mark.anyio
async def test_missing_account_configuration_fails_without_protocol_output(isolated_env):
    command = [str(VENV_BIN / "deltachat-mcp")]
    env = {**os.environ, **isolated_env, "MCP_MODE": "stdio"}
    with anyio.fail_after(8):
        result = await anyio.run_process(command, env=env, check=False)
    assert result.returncode == 1
    assert result.stdout == b""
    assert b"configured account directory" in result.stderr


@pytest.mark.anyio
async def test_closed_native_core_does_not_stall(configured_env):
    core = DeltaChatRPC(Path(configured_env["DC_ACCOUNTS"]))
    try:
        await core.start()
        process = core._transport.process
        process.terminate()
        await anyio.to_thread.run_sync(process.wait, 3)
        with anyio.fail_after(3), pytest.raises(CoreError, match="core is unavailable"):
            await core.run(get_unread_count, {})
    finally:
        await core.close()
