# deltachat_mcp/server.py
# Updated for latest MCP SDK (mcp v1.19.0)
import asyncio
import sys
from mcp.server import Server
from .tools import send_message, list_chats, get_messages, get_unread_count
from .rpc import DeltaChatRPC
from .config import Config

# Register tools using the class method API

# Create server instance for HTTP and stdio handling
server = Server()  # MCP SDK v1.19.0
Server.tool(send_message, name="send_message", schema={
    "type": "object",
    "properties": {
        "addr": {"type": ["string", "null"], "description": "Email address of contact"},
        "chat_id": {"type": ["integer", "null"], "description": "Existing chat ID"},
        "text": {"type": "string", "description": "Message text"}
    },
    "required": ["text"],
    "oneOf": [
        {"required": ["addr"]},
        {"required": ["chat_id"]}
    ]
})

Server.tool(list_chats, name="list_chats", schema={
    "type": "object",
    "properties": {}
})

Server.tool(get_messages, name="get_messages", schema={
    "type": "object",
    "properties": {
        "chat_id": {"type": "integer"}
    },
    "required": ["chat_id"]
})

Server.tool(get_unread_count, name="get_unread_count", schema={
    "type": "object",
    "properties": {}
})

async def start_http():
    from aiohttp import web
    app = web.Application()
    app.router.add_post("/tool", server.handle_http)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", Config.MCP_PORT)
    await site.start()
    print(f"MCP server running at http://127.0.0.1:{Config.MCP_PORT}/tool", file=sys.stderr)

async def stdio_loop():
    await DeltaChatRPC().ensure_configured()
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = server.parse_request(line.strip())
            result = await server.dispatch(req)
            resp = server.format_response(req, result)
        except Exception as e:
            resp = server.format_error(req, str(e))
        print(resp, flush=True)

async def main():
    Config.validate()
    rpc = DeltaChatRPC()
    await rpc.ensure_configured()

    if Config.MCP_MODE == "http":
        await start_http()
        await asyncio.Event().wait()  # keep alive
    else:
        await stdio_loop()

if __name__ == "__main__":
    asyncio.run(main())
