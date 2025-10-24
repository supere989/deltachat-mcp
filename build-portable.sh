#!/bin/bash
# Delta Chat MCP Server - Portable Bundle Creator
# Creates a portable tarball that can run on any Linux system with Python

set -e

echo "📦 Creating portable Delta Chat MCP bundle..."
echo "This creates a self-contained tarball that runs without installation."
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root${NC}"
    exit 1
fi

APP_NAME="deltachat-mcp"
VERSION="0.2.0"
BUNDLE_NAME="${APP_NAME}-portable-${VERSION}"

echo -e "${BLUE}🧹 Cleaning previous builds...${NC}"
rm -rf "${BUNDLE_NAME}"
rm -f "${BUNDLE_NAME}.tar.gz"

echo -e "${BLUE}📁 Creating portable bundle structure...${NC}"
mkdir -p "${BUNDLE_NAME}"

# Copy all necessary files
echo -e "${BLUE}📋 Copying files...${NC}"

# Make Python files non-executable to avoid tar execution issues
chmod -x configure.py desktop_setup.py 2>/dev/null || true

cp -r deltachat_mcp "${BUNDLE_NAME}/"
cp -r examples "${BUNDLE_NAME}/"
cp README.md "${BUNDLE_NAME}/"
cp configure.py "${BUNDLE_NAME}/"
cp desktop_setup.py "${BUNDLE_NAME}/"
cp requirements.txt "${BUNDLE_NAME}/"
cp pyproject.toml "${BUNDLE_NAME}/"
cp launch.sh "${BUNDLE_NAME}/"

# Create portable launcher
cat > "${BUNDLE_NAME}/run.sh" << 'EOF'
#!/bin/bash
# Delta Chat MCP Server - Portable Launcher

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BUNDLE_DIR"

echo "🚀 Delta Chat MCP Server (Portable)"
echo "==================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found"
    echo "Please install Python 3 to use this portable version"
    exit 1
fi

# Check if configured
CONFIG_FILE="config.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "🔧 First-time setup needed..."
    echo ""
    echo "Please enter your Delta Chat credentials:"
    echo ""

    read -p "Delta Chat email address: " DC_ADDR
    read -s -p "Delta Chat app password: " DC_MAIL_PW
    echo ""
    read -p "MCP server port (default 8089): " MCP_PORT
    MCP_PORT=${MCP_PORT:-8089}

    cat > "$CONFIG_FILE" << CONFIG_EOF
DC_ADDR=$DC_ADDR
DC_MAIL_PW=$DC_MAIL_PW
MCP_MODE=http
MCP_PORT=$MCP_PORT
BASEDIR=$BUNDLE_DIR/data
CONFIG_EOF

    echo ""
    echo "✅ Configuration saved!"
    echo ""
fi

# Load configuration
set -a
source "$CONFIG_FILE"
set +a

# Create data directory
mkdir -p "$BASEDIR"

echo "📧 Delta Chat: $DC_ADDR"
echo "🌐 MCP Mode: $MCP_MODE"
echo "🔌 Port: $MCP_PORT"
echo "📁 Data: $BASEDIR"
echo ""

# Install dependencies if needed
echo "🔍 Checking dependencies..."
python3 -c "import deltachat_mcp" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "⚠️  Could not install with pip. Please install manually:"
        echo "   pip install -r requirements.txt"
        echo ""
    fi
fi

# Check Delta Chat RPC server
if ! command -v deltachat-rpc-server &> /dev/null; then
    echo "⚠️  Delta Chat RPC server not found!"
    echo ""
    echo "Please install Delta Chat desktop application or:"
    echo "pip install deltachat2"
    echo ""
    echo "The MCP server will still work, but you may need to start"
    echo "the RPC server manually in another terminal:"
    echo "deltachat-rpc-server --addr \$DC_ADDR --mail_pw \$DC_MAIL_PW"
    echo ""
fi

echo "🚀 Starting MCP server..."
echo "Press Ctrl+C to stop"
echo ""

# Start the server
exec python3 -m deltachat_mcp.server
EOF

chmod +x "${BUNDLE_NAME}/run.sh"

# Create desktop launcher
cat > "${BUNDLE_NAME}/install-desktop.sh" << EOF
#!/bin/bash
# Desktop Integration for Portable Delta Chat MCP

BUNDLE_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="deltachat-mcp"

echo "🖥️ Setting up desktop integration for portable Delta Chat MCP..."
echo ""

# Create desktop file
mkdir -p ~/.local/share/applications

cat > ~/.local/share/applications/\${APP_NAME}.desktop << DESKTOP_EOF
[Desktop Entry]
Version=1.0
Name=Delta Chat MCP Server (Portable)
Comment=AI-powered secure messaging with Delta Chat (Portable)
Exec=\${BUNDLE_DIR}/run.sh
Icon=mail
Terminal=true
Type=Application
Categories=Network;Chat;AI;
Keywords=mcp;chat;messaging;ai;delta;
DESKTOP_EOF

echo "✅ Created desktop launcher"
echo "Look for 'Delta Chat MCP Server (Portable)' in your applications menu"
echo ""
echo "To remove desktop integration:"
echo "rm ~/.local/share/applications/\${APP_NAME}.desktop"
EOF

chmod +x "${BUNDLE_NAME}/install-desktop.sh"

# Create README for portable version
cat > "${BUNDLE_NAME}/README-PORTABLE.md" << EOF
# Delta Chat MCP Server (Portable)

This is a portable version that runs on any Linux system with Python 3.

## Quick Start

1. **Extract**: `tar -xzf deltachat-mcp-portable-${VERSION}.tar.gz`
2. **Configure**: `cd deltachat-mcp-portable-${VERSION} && ./run.sh`
3. **First run**: Enter your Delta Chat credentials when prompted
4. **Desktop integration** (optional): `./install-desktop.sh`

## What's Included

- ✅ Complete MCP server implementation
- ✅ Automatic dependency installation
- ✅ First-run configuration wizard
- ✅ Desktop launcher creation
- ✅ No system installation required

## Requirements

- Python 3.10+
- Delta Chat RPC server (auto-detected, or install with: `pip install deltachat2`)

## Files

- \`run.sh\` - Main launcher script
- \`install-desktop.sh\` - Desktop integration
- \`deltachat_mcp/\` - Python source code
- \`examples/\` - Usage examples
- \`configure.py\` - Configuration script

## Support

GitHub: https://github.com/supere989/deltachat-mcp
Issues: https://github.com/supere989/deltachat-mcp/issues
EOF

# Create installation script
cat > "${BUNDLE_NAME}/install.sh" << EOF
#!/bin/bash
# System-wide installation script

BUNDLE_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"

echo "📦 Installing Delta Chat MCP Server system-wide..."
echo ""

# Install Python package
echo "🔧 Installing Python package..."
pip install -e .

echo ""
echo "✅ Installation complete!"
echo ""
echo "Usage:"
echo "  deltachat-mcp serve    # Start MCP server"
echo "  deltachat-setup        # Configure settings"
echo "  deltachat-desktop      # Desktop integration"
echo ""
echo "Configuration file: ~/.config/deltachat-mcp/config.env"
EOF

chmod +x "${BUNDLE_NAME}/install.sh"

# Create tarball
echo -e "${BLUE}📦 Creating tarball...${NC}"
tar --no-same-owner --no-same-permissions -czf "${BUNDLE_NAME}.tar.gz" --exclude='*.pyc' --exclude='__pycache__' --exclude='.git' "${BUNDLE_NAME}"

# Clean up
rm -rf "${BUNDLE_NAME}"

echo ""
echo -e "${GREEN}🎉 Portable bundle created!${NC}"
echo ""
echo "📦 Bundle: ${BUNDLE_NAME}.tar.gz"
echo "📏 Size: $(du -h ${BUNDLE_NAME}.tar.gz | cut -f1)"
echo ""
echo "🚀 To use:"
echo "   tar -xzf ${BUNDLE_NAME}.tar.gz"
echo "   cd ${BUNDLE_NAME}"
echo "   ./run.sh"
echo ""
echo "🖥️ Desktop integration:"
echo "   ./install-desktop.sh"
echo ""
echo "📦 System installation:"
echo "   ./install.sh"
echo ""
echo -e "${YELLOW}Note: Make sure deltachat-rpc-server is available on the target system${NC}"
echo -e "${YELLOW}or install it with: pip install deltachat2${NC}"
