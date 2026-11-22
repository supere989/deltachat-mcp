#!/bin/bash
# Use operator-supplied environment and let the MCP server own its core process.
exec python -m deltachat_mcp.server "$@"
