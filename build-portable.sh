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
cp deltachat_mcp_gui.py "${BUNDLE_NAME}/"
cp requirements.txt "${BUNDLE_NAME}/"
cp pyproject.toml "${BUNDLE_NAME}/"
cp launch.sh "${BUNDLE_NAME}/"

chmod +x "${BUNDLE_NAME}/configure.py"
chmod +x "${BUNDLE_NAME}/desktop_setup.py"
chmod +x "${BUNDLE_NAME}/deltachat_mcp_gui.py"
chmod +x "${BUNDLE_NAME}/launch.sh"

# Create portable launcher
cat > "${BUNDLE_NAME}/run.sh" << 'EOF'
#!/bin/bash
# Delta Chat MCP Server - Portable Launcher

BUNDLE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BUNDLE_DIR"

echo "🚀 Delta Chat MCP Server (Portable)"
echo "==================================="
echo ""
echo "Choose interface:"
echo "1) 🖥️ Desktop GUI (recommended)"
echo "2) 💻 Command Line"
echo ""
read -p "Enter choice (1 or 2): " choice

case $choice in
    1)
        echo "🖥️ Starting Desktop GUI..."
        python3 deltachat_mcp_gui.py
        ;;
    2)
        echo "💻 Starting Command Line Interface..."
        if [ ! -f "config.env" ]; then
            echo "Please run: python configure.py"
            exit 1
        fi
        source config.env
        python3 -m deltachat_mcp.server
        ;;
    *)
        echo "Invalid choice. Starting GUI by default..."
        python3 deltachat_mcp_gui.py
        ;;
esac
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
Comment=AI-powered secure messaging with Delta Chat (Portable GUI)
Exec=\${BUNDLE_DIR}/deltachat_mcp_gui.py
Icon=mail
Terminal=false
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
2. **Run**: `cd deltachat-mcp-portable-${VERSION} && ./run.sh`
3. **Choose Interface**: Select GUI (recommended) or Command Line
4. **First run**: Enter your Delta Chat credentials when prompted
5. **Desktop integration** (optional): `./install-desktop.sh`

## Features

- ✅ **Desktop GUI Application** - User-friendly interface with real-time monitoring
- ✅ **Command Line Interface** - Traditional terminal-based operation
- ✅ **Automatic dependency installation**
- ✅ **First-run configuration wizard**
- ✅ **Desktop launcher creation**
- ✅ **No system installation required**

## Requirements

- Python 3.10+
- Delta Chat RPC server (auto-detected, or install with: `pip install deltachat2`)

## Files

- \`run.sh\` - Main launcher with GUI/CLI selection
- \`deltachat_mcp_gui.py\` - Desktop GUI application
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
