#!/bin/bash
# Delta Chat MCP Server - Development Launcher
# Starts the MCP server directly (standalone Delta Chat architecture)

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "🚀 Delta Chat MCP Server (Development)"
echo "======================================"
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

echo "🚀 Starting MCP server..."
echo ""
echo "MCP Server will be available at: http://127.0.0.1:$MCP_PORT"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the server directly (creates its own Delta Chat instance)
exec python3 -m deltachat_mcp.server
