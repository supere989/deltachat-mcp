#!/bin/bash
# Delta Chat MCP Server - AppImage Builder
# Creates a portable AppImage that runs on any Linux system

set -e

echo "🚀 Building Delta Chat MCP Server AppImage..."
echo "This will create a portable application that runs without installation."
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory${NC}"
    exit 1
fi

# Check dependencies
echo -e "${BLUE}🔍 Checking dependencies...${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is required${NC}"
    exit 1
fi

# Check PyInstaller
if ! command -v pyinstaller &> /dev/null; then
    echo -e "${YELLOW}⚠️ PyInstaller not found. Installing...${NC}"
    pip install pyinstaller
fi

# Check AppImage tools
if ! command -v appimagetool &> /dev/null; then
    echo -e "${YELLOW}⚠️ AppImage tools not found. Installing...${NC}"
    sudo apt update
    sudo apt install -y appimagetool
fi

echo -e "${GREEN}✅ Dependencies check complete${NC}"

# Create AppDir structure
echo -e "${BLUE}📁 Creating AppImage structure...${NC}"

APP_NAME="deltachat-mcp"
VERSION="0.2.0"
APPDIR="${APP_NAME}.AppDir"

# Clean previous build
rm -rf "${APPDIR}"
rm -rf dist/
rm -rf build/

# Create AppDir
mkdir -p "${APPDIR}"
mkdir -p "${APPDIR}/usr/bin"
mkdir -p "${APPDIR}/usr/lib"
mkdir -p "${APPDIR}/usr/share/applications"
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${APPDIR}/usr/share/metainfo"

# Create desktop file
cat > "${APPDIR}/usr/share/applications/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Version=1.0
Name=Delta Chat MCP Server
Comment=AI-powered secure messaging with Delta Chat
Exec=deltachat-mcp
Icon=deltachat-mcp
Terminal=true
Type=Application
Categories=Network;Chat;AI;
Keywords=mcp;chat;messaging;ai;delta;
EOF

# Create AppStream metadata
cat > "${APPDIR}/usr/share/metainfo/${APP_NAME}.appdata.xml" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<component type="desktop-application">
  <id>com.deltachat.mcp</id>
  <metadata_license>CC0-1.0</metadata_license>
  <project_license>MIT</project_license>
  <name>Delta Chat MCP Server</name>
  <summary>AI-powered secure messaging with Delta Chat</summary>
  <description>
    <p>
      Connect AI assistants to Delta Chat's secure messaging network.
      Enable AI tools like Claude, Cursor, and Windsurf to send and receive
      encrypted messages through the Delta Chat protocol.
    </p>
  </description>
  <launchable type="desktop-id">deltachat-mcp.desktop</launchable>
  <url type="homepage">https://github.com/supere989/deltachat-mcp</url>
  <url type="bugtracker">https://github.com/supere989/deltachat-mcp/issues</url>
  <categories>
    <category>Network</category>
    <category>Chat</category>
    <category>AI</category>
  </categories>
  <keywords>
    <keyword>mcp</keyword>
    <keyword>chat</keyword>
    <keyword>messaging</keyword>
    <keyword>ai</keyword>
    <keyword>delta</keyword>
  </keywords>
  <provides>
    <binary>deltachat-mcp</binary>
  </provides>
  <developer_name>Raymond Johnson</developer_name>
  <releases>
    <release version="${VERSION}" date="2025-01-24" />
  </releases>
</component>
EOF

# Create main executable script
cat > "${APPDIR}/usr/bin/deltachat-mcp" << 'EOF'
#!/bin/bash
# Delta Chat MCP Server AppImage Launcher

APP_DIR="$(dirname "$(readlink -f "$0")")/.."
export PYTHONPATH="${APP_DIR}/usr/lib/python:${PYTHONPATH}"

# Check if configuration exists
CONFIG_FILE="${APP_DIR}/config.env"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "🔧 First run configuration needed..."
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
BASEDIR=$APP_DIR/data
CONFIG_EOF

    echo ""
    echo "✅ Configuration saved to $CONFIG_FILE"
    echo ""
fi

# Load configuration
set -a
source "$CONFIG_FILE"
set +a

# Create data directory
mkdir -p "$BASEDIR"

echo "🚀 Starting Delta Chat MCP Server..."
echo "📧 Delta Chat: $DC_ADDR"
echo "🌐 MCP Mode: $MCP_MODE"
echo "🔌 Port: $MCP_PORT"
echo "📁 Data: $BASEDIR"
echo ""

# Check if Delta Chat RPC server is available
if ! command -v deltachat-rpc-server &> /dev/null; then
    echo "⚠️  Delta Chat RPC server not found in PATH"
    echo "   Please install Delta Chat desktop application"
    echo "   or ensure deltachat-rpc-server is available"
    echo ""
    echo "   You can install it with:"
    echo "   pip install deltachat2"
    echo ""
fi

# Start MCP server
exec "${APP_DIR}/usr/lib/python/deltachat_mcp/server.py" "$@"
EOF

chmod +x "${APPDIR}/usr/bin/deltachat-mcp"

# Create PyInstaller spec file
cat > "${APP_NAME}.spec" << EOF
# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

# Add all Python modules to bundle
hidden_imports = [
    'deltachat2',
    'mcp',
    'aiohttp',
    'python_dotenv',
    'yarl',
    'multidict',
    'async_timeout',
    'charset_normalizer',
    'idna',
    'certifi',
]

a = Analysis(
    ['deltachat_mcp/server.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('deltachat_mcp', 'deltachat_mcp'),
        ('README.md', '.'),
        ('examples', 'examples'),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOF

echo -e "${BLUE}📦 Bundling Python application...${NC}"

# Build with PyInstaller
python -m PyInstaller "${APP_NAME}.spec" --clean

# Copy executable to AppDir
cp "dist/server" "${APPDIR}/usr/lib/python/deltachat_mcp/server.py"

echo -e "${GREEN}✅ PyInstaller bundle created${NC}"

# Create AppImage
echo -e "${BLUE}🏗️ Creating AppImage...${NC}"

# Download appimagetool if not available
if ! command -v appimagetool &> /dev/null; then
    wget -O /tmp/appimagetool "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"
    chmod +x /tmp/appimagetool
    APPIMAGE_TOOL="/tmp/appimagetool"
else
    APPIMAGE_TOOL="appimagetool"
fi

# Create AppImage
$APPIMAGE_TOOL "${APPDIR}" "${APP_NAME}-${VERSION}-x86_64.AppImage"

echo -e "${GREEN}✅ AppImage created: ${APP_NAME}-${VERSION}-x86_64.AppImage${NC}"

# Make executable
chmod +x "${APP_NAME}-${VERSION}-x86_64.AppImage"

# Clean up
rm -rf "${APPDIR}"
rm -rf dist/
rm -rf build/
rm -f "${APP_NAME}.spec"

echo ""
echo -e "${GREEN}🎉 AppImage build complete!${NC}"
echo ""
echo "📦 AppImage created: ${APP_NAME}-${VERSION}-x86_64.AppImage"
echo ""
echo "🚀 To use:"
echo "   1. Download the AppImage file"
echo "   2. Make it executable: chmod +x ${APP_NAME}-${VERSION}-x86_64.AppImage"
echo "   3. Run: ./${APP_NAME}-${VERSION}-x86_64.AppImage"
echo ""
echo "✨ Features:"
echo "   - Portable (no installation needed)"
echo "   - Self-contained (includes Python + dependencies)"
echo "   - First-run configuration wizard"
echo "   - Desktop integration ready"
echo "   - Compatible with any Linux distribution"
echo ""
echo -e "${YELLOW}Note: Make sure deltachat-rpc-server is installed on the target system${NC}"
echo -e "${YELLOW}or install it with: pip install deltachat2${NC}"
