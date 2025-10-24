#!/bin/bash
# Delta Chat MCP Desktop Integration
# Creates desktop shortcuts and system integration

echo "🖥️ Setting up desktop integration..."

# Create desktop launcher
cat > ~/.local/share/applications/deltachat-mcp.desktop << EOF
[Desktop Entry]
Version=1.0
Name=Delta Chat MCP Server
Comment=Start Delta Chat MCP server for AI integration
Exec=$PWD/launch.sh
Icon=mail
Terminal=true
Type=Application
Categories=Network;Chat;
StartupNotify=true
EOF

echo "✅ Created desktop launcher"

# Create system service (optional)
if command -v systemctl &> /dev/null; then
    echo "🔧 System service support detected"
    echo "   To install as system service:"
    echo "   sudo cp deltachat-mcp.service /etc/systemd/system/"
    echo "   sudo systemctl enable deltachat-mcp"
    echo "   sudo systemctl start deltachat-mcp"
else
    echo "ℹ️ System service not available (systemctl not found)"
fi

echo ""
echo "🎉 Desktop integration complete!"
echo "   Find 'Delta Chat MCP Server' in your applications menu"
