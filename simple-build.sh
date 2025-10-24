#!/bin/bash
# Simple Portable Bundle Creator - Manual Version
# Creates portable bundle without complex build scripts

set -e

echo "📦 Creating simple portable bundle..."

APP_NAME="deltachat-mcp"
VERSION="0.2.0"
BUNDLE_NAME="${APP_NAME}-portable-${VERSION}"

# Clean up
rm -rf "${BUNDLE_NAME}"
rm -f "${BUNDLE_NAME}.tar.gz"

# Create bundle directory
mkdir -p "${BUNDLE_NAME}"

# Copy files (simple approach)
cp -r deltachat_mcp "${BUNDLE_NAME}/"
cp -r examples "${BUNDLE_NAME}/"
cp README.md "${BUNDLE_NAME}/"
cp configure.py "${BUNDLE_NAME}/"
cp desktop_setup.py "${BUNDLE_NAME}/"
cp deltachat_mcp_gui.py "${BUNDLE_NAME}/"
cp requirements.txt "${BUNDLE_NAME}/"
cp pyproject.toml "${BUNDLE_NAME}/"
cp launch.sh "${BUNDLE_NAME}/"

# Make scripts executable in the bundle
chmod +x "${BUNDLE_NAME}/configure.py"
chmod +x "${BUNDLE_NAME}/desktop_setup.py"
chmod +x "${BUNDLE_NAME}/deltachat_mcp_gui.py"
chmod +x "${BUNDLE_NAME}/launch.sh"

# Create the run.sh script
cat > "${BUNDLE_NAME}/run.sh" << 'EOF'
#!/bin/bash
# Simple Portable Launcher

echo "🚀 Delta Chat MCP Server (Portable)"
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

# Create simple tarball
echo "📦 Creating tarball..."
tar -czf "${BUNDLE_NAME}.tar.gz" "${BUNDLE_NAME}"

# Clean up
rm -rf "${BUNDLE_NAME}"

echo ""
echo "✅ Portable bundle created: ${BUNDLE_NAME}.tar.gz"
echo ""
echo "To use:"
echo "  tar -xzf ${BUNDLE_NAME}.tar.gz"
echo "  cd ${BUNDLE_NAME}"
echo "  python configure.py  # First time setup"
echo "  ./run.sh             # Start server"
echo ""
