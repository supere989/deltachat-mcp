#!/usr/bin/env python3
"""
Desktop Setup Module for Delta Chat MCP Server
Creates desktop shortcuts and system integration
"""

import os
import sys
from pathlib import Path

def create_desktop_launcher():
    """Create desktop launcher"""
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

    # Check if systemctl is available for system service
    success, stdout, stderr = run_command("which systemctl")
    if success:
        print("\n🔧 System service support detected!")
        print("   To install as system service:")
        print("   sudo cp scripts/deltachat-mcp.service /etc/systemd/system/")
        print("   sudo systemctl enable deltachat-mcp")
        print("   sudo systemctl start deltachat-mcp")
    else:
        print("\nℹ️ System service not available (systemctl not found)")

def run_command(cmd):
    """Run a command and return success status"""
    import subprocess
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        return False, "", str(e)

def main():
    """Main desktop setup function"""
    print("🖥️ Delta Chat MCP Desktop Integration")
    print("="*40)
    print()

    # Check if setup has been run
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ Please run setup first:")
        print("   python configure.py")
        print()
        print("This will configure your Delta Chat credentials.")
        sys.exit(1)

    create_desktop_launcher()

    print("\n🎉 Desktop integration complete!")
    print("   You can now find 'Delta Chat MCP Server' in your applications menu!")

if __name__ == "__main__":
    main()
