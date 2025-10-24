#!/usr/bin/env python3
"""
Delta Chat MCP Server - Easy Setup Script
One-command setup for Delta Chat MCP integration
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Import config for auto-detection
try:
    from deltachat_mcp.config import Config
except ImportError:
    # Fallback if not installed yet
    Config = None

def run_command(cmd, cwd=None):
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def check_requirements():
    """Check if required tools are installed"""
    print("🔍 Checking requirements...")

    # Check Python version
    success, stdout, stderr = run_command("python3 --version")
    if not success:
        print("❌ Python 3 is required")
        return False

    # Check if pip is available
    success, stdout, stderr = run_command("pip3 --version")
    if not success:
        print("❌ pip is required")
        return False

    # Check if git is available (for cloning)
    success, stdout, stderr = run_command("git --version")
    if not success:
        print("❌ git is required")
        return False

    print("✅ All requirements satisfied")
    return True

def setup_environment():
    """Set up the environment and configuration"""
    print("🔧 Setting up environment...")

    # Try to auto-detect Delta Chat credentials first
    print("🔍 Checking for existing Delta Chat configuration...")
    if Config and Config.DC_ADDR and Config.DC_MAIL_PW:
        print(f"✅ Found existing Delta Chat account: {Config.DC_ADDR}")
        print(f"   Using data directory: {Config.BASEDIR}")
        use_existing = input("Use existing credentials? (Y/n): ").strip().lower()
        if use_existing in ['', 'y', 'yes']:
            print("✅ Using existing Delta Chat credentials")
            return

    # Create .env file if it doesn't exist or user wants manual setup
    env_file = Path(".env")
    if not env_file.exists():
        print("📝 Creating .env configuration file...")

        # Get user input for configuration
        dc_addr = input("Enter your Delta Chat email address: ").strip()
        dc_password = input("Enter your Delta Chat app password: ").strip()
        mcp_port = input("Enter MCP server port (default 8089): ").strip() or "8089"

        env_content = f"""DC_ADDR={dc_addr}
DC_MAIL_PW={dc_password}
MCP_MODE=http
MCP_PORT={mcp_port}
BASEDIR=./dc-data
"""

        env_file.write_text(env_content)
        print(f"✅ Created .env file with your configuration")
    else:
        print("✅ .env file already exists")

    # Create dc-data directory
    dc_data_dir = Path("dc-data")
    if not dc_data_dir.exists():
        dc_data_dir.mkdir()
        print("✅ Created dc-data directory")
    else:
        print("✅ dc-data directory already exists")

def install_package():
    """Install the package and dependencies"""
    print("📦 Installing Delta Chat MCP server...")

    # Install the package in development mode
    success, stdout, stderr = run_command("pip install -e .")
    if success:
        print("✅ Package installed successfully")
        return True
    else:
        print(f"❌ Installation failed: {stderr}")
        return False

def create_windsurf_config():
    """Create Windsurf configuration"""
    print("⚙️ Creating Windsurf configuration...")

    # Get port from .env file
    port = "8089"
    env_file = Path(".env")
    if env_file.exists():
        content = env_file.read_text()
        for line in content.split('\n'):
            if line.startswith('MCP_PORT='):
                port = line.split('=', 1)[1]

    config = {
        "name": "deltachat",
        "url": f"http://127.0.0.1:{port}",
        "description": "Delta Chat MCP Server - Send/receive encrypted messages"
    }

    # Save config to file
    config_file = Path("windsurf-config.json")
    config_file.write_text(json.dumps(config, indent=2))

    print("✅ Created Windsurf configuration file: windsurf-config.json")
    print(f"   Add this to Windsurf: {config}")
    return config

def create_launcher_script():
    """Create a launcher script for easy startup"""
    print("🚀 Creating launcher script...")

    script_content = '''#!/bin/bash
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
'''

    script_file = Path("launch.sh")
    script_file.write_text(script_content)
    script_file.chmod(0o755)  # Make executable

    print("✅ Created launcher script: launch.sh")
    print("   Run with: ./launch.sh")

def create_desktop_integration():
    """Create desktop integration"""
    print("🖥️ Setting up desktop integration...")

    # Create desktop launcher
    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    # Get current directory for Exec path
    current_dir = Path.cwd()

    desktop_content = f"""[Desktop Entry]
Version=1.0
Name=Delta Chat MCP Server
Comment=Start Delta Chat MCP server for AI integration
Exec={current_dir}/launch.sh
Icon=mail
Terminal=true
Type=Application
Categories=Network;Chat;
StartupNotify=true
"""

    desktop_file = desktop_dir / "deltachat-mcp.desktop"
    desktop_file.write_text(desktop_content)

    print(f"✅ Created desktop launcher: {desktop_file}")

    # Make scripts executable
    launch_script = Path("launch.sh")
    if launch_script.exists():
        launch_script.chmod(0o755)

    print("✅ Desktop integration complete!")
    print("   Find 'Delta Chat MCP Server' in your applications menu")

def show_success_message():
    """Show success message with next steps"""
    print("\n" + "="*50)
    print("🎉 SETUP COMPLETE!")
    print("="*50)
    print()

    # Check if we used auto-detection
    if Config and Config.DC_ADDR and Config.DC_MAIL_PW:
        print("✅ Using auto-detected Delta Chat credentials")
        print(f"   Email: {Config.DC_ADDR}")
        print(f"   Data: {Config.BASEDIR}")
    else:
        print("✅ Manual configuration completed")

    print()
    print("📋 Next Steps:")
    print()
    print("1️⃣  Start the GUI:")
    print("   python3 deltachat_mcp_gui.py")
    print()
    print("2️⃣  Or start the server:")
    print("   ./launch.sh")
    print()
    print("3️⃣  Add to MCP clients:")
    print("   Server will be available at: http://127.0.0.1:8089")
    print()
    print("🛠️  Available tools:")
    print("   - deltachat.send_message()")
    print("   - deltachat.list_chats()")
    print("   - deltachat.get_messages()")
    print("   - deltachat.get_unread_count()")
    print()

def main():
    """Main setup function"""
    print("🌟 Delta Chat MCP Server - Easy Setup")
    print("="*40)
    print()

    # Check requirements
    if not check_requirements():
        print("❌ Requirements not met. Please install Python 3, pip, and git.")
        sys.exit(1)

    # Setup environment
    setup_environment()

    # Install package
    if not install_package():
        print("❌ Package installation failed.")
        sys.exit(1)

    # Create configurations
    config = create_windsurf_config()
    create_launcher_script()

    # Ask about desktop integration
    desktop_setup = input("\n🖥️  Would you like to set up desktop integration? (y/N): ").strip().lower()
    if desktop_setup in ['y', 'yes']:
        create_desktop_integration()

    # Show success
    show_success_message()

    print("✅ Setup complete! Ready to use Delta Chat with AI tools!")

if __name__ == "__main__":
    main()
