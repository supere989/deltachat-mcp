#!/bin/bash
# Delta Chat MCP Server Launcher

echo "🚀 Starting Delta Chat MCP Server..."
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "Please run: python configure.py"
    exit 1
fi

# Load environment variables
set -a
source .env
set +a

echo "📧 Delta Chat: $DC_ADDR"
echo "🌐 MCP Mode: $MCP_MODE"
echo "🔌 MCP Port: $MCP_PORT"
echo ""

# Start Delta Chat RPC server in background
echo "🔄 Starting Delta Chat RPC server..."
deltachat-rpc-server --addr "$DC_ADDR" --mail_pw "$DC_MAIL_PW" &
RPC_PID=$!

# Wait a moment for RPC to start
sleep 2

# Start MCP server
echo "🔌 Starting MCP server on port $MCP_PORT..."
python -m deltachat_mcp.server

# Cleanup on exit
echo ""
echo "🛑 Shutting down..."
kill $RPC_PID 2>/dev/null
