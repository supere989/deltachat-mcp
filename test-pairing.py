#!/usr/bin/env python3
"""
Delta Chat MCP - Automatic Pairing Test Script
Tests the automatic pairing functionality
"""

import sys
import os
from pathlib import Path

def test_automatic_pairing():
    """Test the automatic pairing functionality"""
    print("🧪 Testing Automatic Pairing Functionality")
    print("="*50)

    # Test 1: Import the pairing module
    try:
        from deltachat_mcp.pairing import auto_pairing, NetworkDiscovery
        print("✅ Successfully imported pairing modules")
    except ImportError as e:
        print(f"❌ Failed to import pairing modules: {e}")
        return False

    # Test 2: Test network discovery
    print("\n📡 Testing Network Discovery...")
    discovery = NetworkDiscovery()
    networks = discovery.get_local_networks()

    if networks:
        print(f"✅ Found local networks: {networks}")
    else:
        print("⚠️  No local networks found (this is normal in some environments)")

    # Test 3: Test configuration loading
    print("\n⚙️  Testing Configuration...")
    try:
        from deltachat_mcp.config import Config

        # Test automatic pairing config
        print(f"   Auto-pairing enabled: {Config.AUTO_PAIRING_ENABLED}")
        print(f"   Scan interval: {Config.AUTO_PAIRING_SCAN_INTERVAL}s")
        print(f"   Timeout: {Config.AUTO_PAIRING_TIMEOUT}s")

        # Test initialization
        if Config.AUTO_PAIRING_ENABLED:
            success = Config.initialize_auto_pairing()
            if success:
                print("✅ Automatic pairing service initialized")
            else:
                print("⚠️  Automatic pairing service initialization failed")
        else:
            print("🔇 Automatic pairing disabled in configuration")

    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

    # Test 4: Test backup string parsing
    print("\n🔧 Testing Backup String Parsing...")
    test_backup = "DCBACKUP3:test-data&{\"node_id\":\"test123\",\"direct_addresses\":[\"192.168.1.100:42654\"]}"

    try:
        backup_info = Config.parse_backup_string(test_backup)
        if backup_info:
            print("✅ Backup string parsing successful")
            print(f"   Node ID: {backup_info['node_id']}")
            print(f"   Direct addresses: {backup_info['direct_addresses']}")
        else:
            print("❌ Backup string parsing failed")
    except Exception as e:
        print(f"❌ Backup string parsing error: {e}")

    # Test 5: Test GUI imports (if available)
    print("\n🖥️  Testing GUI Integration...")
    try:
        import tkinter as tk
        print("✅ Tkinter available for GUI")
    except ImportError:
        print("⚠️  Tkinter not available (GUI features will not work)")

    print("\n🎉 Automatic Pairing Test Complete!")
    print("\n💡 Next Steps:")
    print("1. Run: python configure.py")
    print("2. Choose option 4 for automatic pairing")
    print("3. Start Delta Chat desktop client")
    print("4. Copy a backup string (DCBACKUP3:) to clipboard")
    print("5. Watch the automatic pairing in action!")

    return True

if __name__ == "__main__":
    success = test_automatic_pairing()
    sys.exit(0 if success else 1)
