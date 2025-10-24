#!/bin/bash
# Delta Chat MCP Server - Distribution Builder
# Creates multiple deployment formats for easy distribution

set -e

echo "📦 Delta Chat MCP Server - Distribution Builder"
echo "==============================================="
echo ""
echo "This script creates multiple deployment formats:"
echo "  • Portable tarball (Linux)"
echo "  • Development setup"
echo "  • PyPI package"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

APP_NAME="deltachat-mcp"
VERSION="0.2.0"

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root${NC}"
    exit 1
fi

echo -e "${BLUE}🔧 Building distribution packages...${NC}"

# Build Python package
echo -e "${BLUE}📦 Building Python package...${NC}"
python -m build

echo -e "${GREEN}✅ Python package built${NC}"
echo "   Files: dist/${APP_NAME}-${VERSION}.tar.gz"
echo "   Files: dist/${APP_NAME}-${VERSION}-py3-none-any.whl"

# Build portable version
echo -e "${BLUE}📦 Building portable tarball...${NC}"
./build-portable.sh

echo -e "${GREEN}✅ Portable bundle created${NC}"
echo "   File: ${APP_NAME}-portable-${VERSION}.tar.gz"

# Try to build AppImage (optional)
echo -e "${BLUE}🔧 Attempting AppImage build...${NC}"
if command -v appimagetool &> /dev/null && command -v pyinstaller &> /dev/null; then
    echo "   AppImage tools found, building..."
    ./build-appimage.sh
    echo -e "${GREEN}✅ AppImage created${NC}"
    echo "   File: ${APP_NAME}-${VERSION}-x86_64.AppImage"
else
    echo -e "${YELLOW}⚠️ AppImage tools not found, skipping AppImage build${NC}"
    echo "   Install with: pip install pyinstaller"
    echo "   And: sudo apt install appimagetool"
fi

echo ""
echo -e "${GREEN}🎉 All distributions built!${NC}"
echo ""
echo "📋 Distribution files created:"
echo ""

if [ -f "dist/${APP_NAME}-${VERSION}.tar.gz" ]; then
    echo "📦 PyPI Package:"
    echo "   dist/${APP_NAME}-${VERSION}.tar.gz"
    echo "   dist/${APP_NAME}-${VERSION}-py3-none-any.whl"
    echo ""
    echo "   Install with: pip install dist/${APP_NAME}-${VERSION}-py3-none-any.whl"
fi

if [ -f "${APP_NAME}-portable-${VERSION}.tar.gz" ]; then
    echo "🚀 Portable Bundle:"
    echo "   ${APP_NAME}-portable-${VERSION}.tar.gz"
    echo ""
    echo "   Run with: tar -xzf ${APP_NAME}-portable-${VERSION}.tar.gz && cd ${APP_NAME}-portable-${VERSION} && ./run.sh"
fi

if [ -f "${APP_NAME}-${VERSION}-x86_64.AppImage" ]; then
    echo "🖥️ AppImage:"
    echo "   ${APP_NAME}-${VERSION}-x86_64.AppImage"
    echo ""
    echo "   Run with: chmod +x ${APP_NAME}-${VERSION}-x86_64.AppImage && ./${APP_NAME}-${VERSION}-x86_64.AppImage"
fi

echo ""
echo -e "${BLUE}📚 Deployment Instructions:${NC}"
echo ""
echo "1️⃣ GitHub Releases:"
echo "   Upload files to: https://github.com/supere989/deltachat-mcp/releases"
echo ""
echo "2️⃣ PyPI Publishing:"
echo "   twine upload dist/*"
echo ""
echo "3️⃣ Direct Download:"
echo "   Users can download and run without installation"
echo ""
echo -e "${YELLOW}💡 Recommendation: Start with the portable tarball - it's the most reliable!${NC}"
