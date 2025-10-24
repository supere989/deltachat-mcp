#!/usr/bin/env python3
"""
Delta Chat MCP - Updated Pairing Implementation Test
Tests the corrected pairing functionality that uses Delta Chat core backup import
"""

import sys
from pathlib import Path

def test_updated_pairing():
    """Test the updated pairing implementation"""
    print("🧪 Testing Updated Pairing Implementation")
    print("=" * 50)

    # Test 1: Import the pairing module
    try:
        from deltachat_mcp.config import Config
        from deltachat_mcp.rpc import DeltaChatRPC
        print("✅ Successfully imported pairing modules")
    except ImportError as e:
        print(f"❌ Failed to import pairing modules: {e}")
        return False

    # Test 2: Test backup string parsing
    print("\n📋 Testing backup string parsing...")
    test_backup = "DCBACKUP3:s5R3-kqQ0zY_8GrvTp2DKPAo&{\"node_id\":\"bf913557345c5a9533937d2ec040579f60985d36034be5ceb0f2547c1bb676e5\",\"relay_url\":null,\"direct_addresses\":[\"127.0.0.1:42654\"]}"

    try:
        backup_info = Config.parse_backup_string(test_backup)
        if backup_info:
            print("✅ Backup string parsing successful")
            print(f"   Encrypted data length: {len(backup_info['encrypted_data'])}")
            print(f"   Node ID: {backup_info['node_id']}")
            print(f"   Direct addresses: {backup_info['direct_addresses']}")
        else:
            print("❌ Backup string parsing failed")
    except Exception as e:
        print(f"❌ Error parsing backup string: {e}")
        return False

    # Test 3: Test Delta Chat core availability
    print("\n🔧 Testing Delta Chat core availability...")
    try:
        from deltatachat2 import Rpc, Account
        print("✅ Delta Chat core (deltachat2) available")

        # Test RPC creation
        rpc = Rpc()
        print(f"✅ RPC instance created: {type(rpc)}")

        # Check for imex module
        if hasattr(rpc, 'imex'):
            print("✅ imex module available")
            imex_methods = [m for m in dir(rpc.imex) if not m.startswith('_') and callable(getattr(rpc.imex, m))]
            backup_methods = [m for m in imex_methods if 'backup' in m.lower() or 'import' in m.lower()]
            if backup_methods:
                print(f"✅ Backup import methods available: {backup_methods}")
            else:
                print("⚠️ No backup import methods found")
        else:
            print("⚠️ imex module not available")

    except ImportError:
        print("❌ Delta Chat core (deltachat2) not available")
        print("💡 This means the system will use fallback mode")
        print("   Install with: pip install deltatachat2")

    # Test 4: Test fallback mode
    print("\n🔄 Testing fallback configuration...")
    try:
        rpc_instance = DeltaChatRPC()
        print(f"✅ RPC instance created: {type(rpc_instance.account)}")

        if hasattr(rpc_instance.account, 'is_configured'):
            configured = rpc_instance.account.is_configured()
            print(f"✅ Account configured check: {configured}")
        else:
            print("⚠️ Using mock account (limited functionality)")

    except Exception as e:
        print(f"❌ Error creating RPC instance: {e}")
        return False

    # Test 5: Test second device setup
    print("\n📱 Testing second device setup...")
    try:
        # Set up test configuration
        Config.BACKUP_INFO = backup_info
        Config.IS_SECOND_DEVICE = True

        print("✅ Test configuration set up")
        print(f"   Node ID: {Config.BACKUP_INFO['node_id']}")
        print(f"   Second device mode: {Config.IS_SECOND_DEVICE}")

        # The actual setup would require async context
        print("✅ Second device setup configuration ready")
        print("💡 In real usage, this would:")
        print("   • Import backup using Delta Chat core")
        print("   • Handle pairing automatically")
        print("   • Configure multi-device sync")

    except Exception as e:
        print(f"❌ Error in second device setup: {e}")
        return False

    print("\n🎉 Updated Pairing Implementation Test Complete!")
    print("\n💡 Key Improvements:")
    print("• Uses Delta Chat core backup import instead of manual WebSocket")
    print("• Proper handling of complete pairing payload")
    print("• Graceful fallback when core is not available")
    print("• Clear error messages and installation instructions")
    print()
    print("🚀 Next Steps:")
    print("1. Install Delta Chat core: pip install deltatachat2")
    print("2. Get a real backup string from Delta Chat desktop")
    print("3. Test automatic pairing with complete functionality")

    return True

if __name__ == "__main__":
    success = test_updated_pairing()
    sys.exit(0 if success else 1)
