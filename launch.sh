#!/bin/bash
# Delta Chat MCP Server - Easy Launcher
# One-command launcher for development and testing

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Delta Chat MCP Server Launcher"
echo "================================="
echo ""

# Check if configured
if [ ! -f ".env" ]; then
    echo "🔧 Configuration needed!"
    echo "Run: python configure.py"
    echo ""
    echo "Or create .env file manually with:"
    echo "DC_ADDR=your-email@example.com"
    echo "DC_MAIL_PW=your-app-password"
    echo "MCP_MODE=http"
    echo "MCP_PORT=8089"
    echo "BASEDIR=./dc-data"
    exit 1
fi

# Load configuration
set -a
source .env
set +a

# Create data directory
mkdir -p "$BASEDIR"

echo "📧 Delta Chat: $DC_ADDR"
echo "🌐 MCP Mode: $MCP_MODE"
echo "🔌 Port: $MCP_PORT"
echo "📁 Data: $BASEDIR"
echo ""

# Check dependencies
echo "🔍 Checking dependencies..."
python3 -c "import deltachat_mcp, mcp, aiohttp, dotenv" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
fi

# Check Delta Chat RPC server
if ! command -v deltachat-rpc-server &> /dev/null; then
    echo "⚠️  Delta Chat RPC server not found!"
    echo ""
    echo "Please install it:"
    echo "   pip install deltachat2"
    echo ""
    echo "Or install Delta Chat desktop application"
    echo ""
fi

echo "🚀 Starting servers..."
echo ""
echo "MCP Server will be available at: http://127.0.0.1:$MCP_PORT"
echo ""
echo "Press Ctrl+C to stop all servers"
echo ""

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping servers..."
    kill $RPC_PID 2>/dev/null
    echo "✅ Done!"
    exit 0
}

# Set trap for cleanup
trap cleanup INT TERM

# Start Delta Chat RPC server in background
echo "🔄 Starting Delta Chat RPC server..."
deltachat-rpc-server --addr "$DC_ADDR" --mail_pw "$DC_MAIL_PW" &
RPC_PID=$!

# Wait for RPC to initialize
sleep 3

# Start MCP server
echo "🔌 Starting MCP server..."
python -m deltachat_mcp.server
