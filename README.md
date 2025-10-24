# deltachat-mcp

**Let AI send/receive encrypted messages via Delta Chat using Model Context Protocol (MCP)**

[![PyPI](https://img.shields.io/pypi/v/deltachat-mcp)](https://pypi.org/project/deltachat-mcp/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> First MCP server for **Delta Chat** — privacy-first, E2EE, decentralized. **Compatible with latest MCP SDK v1.19.0**.

---

## Features

- Send messages to any email
- List chats & unread count
- Read recent messages
- Works with **Claude Desktop**, **Cursor**, **Windsurf**, **mcp-client-app**
- Zero plaintext exposure (Autocrypt E2EE)

---

## Quick Start

```bash
# 1. Install
pip install deltachat-mcp

# 2. Copy config
cp .env.example .env
# Edit .env with your email + app password

# 3. Start Delta Chat RPC server
deltachat-rpc-server --addr $DC_ADDR --mail_pw $DC_MAIL_PW &

# 4. Run MCP server
deltachat-mcp serve
```

Add to your MCP client:

```json
{
  "name": "deltachat",
  "url": "http://127.0.0.1:8089"
}
```

---

## AI Prompt

```text
Use `deltachat.send_message` to contact users. Always confirm sensitive actions.
```

---

## Development

```bash
pip install -e .[dev]
pytest
```

---

## License

MIT © 2025
