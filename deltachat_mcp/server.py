"""The stdio and loopback HTTP entry points for Delta Chat MCP."""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from queue import SimpleQueue

from deltachat2 import JsonRpcError
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import MCPError

from .rpc import CoreError, DeltaChatRPC
from .tools import ToolInputError, get_messages, get_unread_count, list_chats, send_message

LOG = logging.getLogger("deltachat_mcp.server")
EMPTY_SCHEMA = {"type": "object", "properties": {}}
TOOLS = {
    "send_message": (
        send_message,
        "Send text to a Delta Chat address or existing chat.",
        {
            "type": "object",
            "properties": {
                "addr": {"type": ["string", "null"], "description": "Email address of contact"},
                "chat_id": {"type": ["integer", "null"], "description": "Existing chat ID"},
                "text": {"type": "string", "description": "Message text"},
            },
            "required": ["text"],
            "oneOf": [{"required": ["addr"]}, {"required": ["chat_id"]}],
        },
    ),
    "list_chats": (list_chats, "List chats with their unread counts.", EMPTY_SCHEMA),
    "get_messages": (
        get_messages,
        "Read up to 20 recent messages in a chat.",
        {
            "type": "object",
            "properties": {"chat_id": {"type": "integer"}},
            "required": ["chat_id"],
        },
    ),
    "get_unread_count": (get_unread_count, "Count unread messages across chats.", EMPTY_SCHEMA),
}


def tool_error(text: str) -> types.CallToolResult:
    return types.CallToolResult(content=[types.TextContent(type="text", text=text)], is_error=True)


def create_server(core: DeltaChatRPC) -> Server:
    async def list_tools(_context, _params):
        core.audit("tools_listed")
        return types.ListToolsResult(tools=[
            types.Tool(name=name, description=description, input_schema=schema)
            for name, (_, description, schema) in TOOLS.items()
        ])

    async def call_tool(_context, params):
        core.audit("tool_requested")
        entry = TOOLS.get(params.name)
        if entry is None:
            core.audit("tool_unknown")
            raise MCPError(types.ErrorData(code=types.INVALID_PARAMS, message="Unknown tool"))
        try:
            payload = await core.run(entry[0], params.arguments or {})
        except ToolInputError as error:
            core.audit("tool_invalid")
            return tool_error(str(error))
        except (CoreError, JsonRpcError):
            core.audit("tool_core_failure")
            return tool_error("Delta Chat core could not complete the request")
        except asyncio.CancelledError:
            core.audit("tool_cancelled")
            raise
        except Exception:
            core.audit("tool_failed")
            return tool_error("Delta Chat could not complete the request")
        core.audit("tool_succeeded")
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload))],
            structured_content=payload,
        )

    return Server("deltachat-mcp", version="0.2.0", on_list_tools=list_tools, on_call_tool=call_tool)


def http_port() -> int:
    try:
        port = int(os.getenv("MCP_PORT", "8089"))
    except ValueError:
        port = 0
    if not 1 <= port <= 65535:
        raise CoreError("MCP_PORT must be an integer from 1 to 65535")
    return port


async def serve_http(server: Server, core: DeltaChatRPC, port: int):
    import uvicorn

    app = server.streamable_http_app(
        streamable_http_path="/tool", json_response=True, host="127.0.0.1"
    )
    session_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        # Close the core during ASGI shutdown before Uvicorn re-raises SIGTERM.
        try:
            async with session_lifespan(application):
                yield
        finally:
            await core.close()

    app.router.lifespan_context = lifespan
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=port,
        log_config=None,
        access_log=False,
        proxy_headers=False,
    )
    LOG.info("Starting MCP over loopback HTTP on port %d at /tool", port)
    await uvicorn.Server(config).serve()


async def run():
    mode = os.getenv("MCP_MODE", "http").lower()
    if mode not in {"http", "stdio"}:
        raise CoreError("MCP_MODE must be http or stdio")
    port = http_port() if mode == "http" else None

    default_dir = Path(os.environ.get("BASEDIR", "./dc-data")) / "accounts"
    accounts_dir = Path(os.getenv("DC_ACCOUNTS", str(default_dir))).expanduser()
    core = DeltaChatRPC(
        accounts_dir,
        address=os.getenv("DC_ADDR"),
        password=os.getenv("DC_MAIL_PW"),
        backup=os.getenv("BACKUP_STRING"),
    )
    try:
        await core.start()
        server = create_server(core)
        if port is not None:
            await serve_http(server, core, port)
        else:
            LOG.info("Serving MCP over stdio")
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await core.close()


def main():
    logs = SimpleQueue()
    queue_handler = QueueHandler(logs)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(name)s %(message)s"))
    listener = QueueListener(logs, handler)
    app_logger = logging.getLogger("deltachat_mcp")
    app_logger.setLevel(logging.INFO)
    app_logger.addHandler(queue_handler)
    # SDK diagnostics can contain session IDs or application payloads.
    sdk_logger = logging.getLogger("mcp")
    sdk_logger.addHandler(logging.NullHandler())
    sdk_logger.propagate = False
    listener.start()
    try:
        asyncio.run(run())
    except CoreError as error:
        LOG.error("%s", error)
        raise SystemExit(1) from None
    except KeyboardInterrupt:
        pass
    except (Exception, SystemExit):
        LOG.error("MCP server could not start or continue serving")
        raise SystemExit(1) from None
    finally:
        listener.stop()
        app_logger.removeHandler(queue_handler)


if __name__ == "__main__":
    main()
