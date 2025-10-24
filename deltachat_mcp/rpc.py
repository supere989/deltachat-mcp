# deltachat_mcp/rpc.py
import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from deltatachat2 import Account

from .config import Config

class DeltaChatRPC:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            try:
                from deltatachat2 import Rpc, Account
                cls._instance.rpc = Rpc()
                cls._instance.account = Account(cls._instance.rpc, 1)
                print("✅ Delta Chat core initialized successfully")
            except ImportError:
                print("❌ deltatachat2 not available - install with: pip install deltatachat2")
                # Create a mock account object for type checking
                class MockAccount:
                    def __init__(self, rpc, account_id):
                        self.rpc = rpc
                        self.id = account_id
                        self._configured = False

                    def is_configured(self):
                        return self._configured

                    async def configure(self, addr, mail_pw, basedir):
                        self._configured = True
                        print(f"⚠️ Using mock configuration for {addr}")

                    async def start_io(self):
                        print("⚠️ Using mock IO start")

                    async def get_chats(self):
                        return []

                    async def get_chat_by_id(self, chat_id):
                        return None

                    async def create_contact(self, addr):
                        return None

                    async def create_chat(self, contact):
                        return None

                cls._instance.rpc = None
                cls._instance.account = MockAccount(None, 1)
                print("✅ Using mock Delta Chat account (limited functionality)")

            cls._instance.loop = asyncio.get_event_loop()
        return cls._instance

    async def ensure_configured(self):
        if not self.account.is_configured():
            # Check if this is a second device setup
            if hasattr(Config, 'IS_SECOND_DEVICE') and Config.IS_SECOND_DEVICE:
                # For second device, we need to import backup data
                await self._setup_second_device()
            else:
                # Regular account setup with email/password
                await self.account.configure(
                    addr=Config.DC_ADDR,
                    mail_pw=Config.DC_MAIL_PW,
                    basedir=Config.BASEDIR
                )

        if not self.account.is_io_running():
            await self.account.start_io()

    async def _setup_second_device(self):
        """Set up account as a second device using backup string"""
        if not hasattr(Config, 'BACKUP_INFO') or not Config.BACKUP_INFO:
            # Try automatic pairing if no backup info available
            from .pairing import auto_pairing
            if Config.AUTO_PAIRING_ENABLED and not auto_pairing.paired_info:
                print("🔄 Attempting automatic pairing for second device...")
                success = auto_pairing.attempt_automatic_pairing()
                if success:
                    Config.BACKUP_INFO = auto_pairing.paired_info
                    Config.IS_SECOND_DEVICE = True
                else:
                    print("❌ Automatic pairing failed, falling back to manual setup")

            if not hasattr(Config, 'BACKUP_INFO') or not Config.BACKUP_INFO:
                raise ValueError("No backup information available for second device setup")

        backup_info = Config.BACKUP_INFO
        print(f"🔧 Setting up second device: {backup_info['node_id']}")

        # Import backup using Delta Chat core instead of manual WebSocket
        await self._import_backup_data(backup_info)

    async def _import_backup_data(self, backup_info):
        """Import backup data using Delta Chat core RPC methods"""
        try:
            # Get the encrypted backup data from the backup string
            encrypted_data = backup_info.get('encrypted_data')
            if not encrypted_data:
                raise ValueError("No encrypted backup data found")

            print(f"📦 Importing backup data for node: {backup_info['node_id']}")
            print(f"🔐 Encrypted data length: {len(encrypted_data)} characters")

            # Try to import using Delta Chat core
            try:
                from deltatachat2 import Rpc, Account
                print("✅ Delta Chat core available, importing backup...")

                # Create RPC connection
                rpc = Rpc()

                # The proper way to import backup string
                # According to Delta Chat docs, this should use the imex module
                if hasattr(rpc, 'imex') and hasattr(rpc.imex, 'import_backup'):
                    print("🔄 Using Delta Chat core backup import...")
                    # Call the proper backup import method
                    result = await rpc.imex.import_backup(encrypted_data)
                    print(f"✅ Backup import result: {result}")

                    # The Delta Chat core should handle the pairing automatically
                    print("🔄 Delta Chat core will handle pairing automatically")
                    self.is_paired = True
                    self.pairing_data = backup_info
                    return True
                else:
                    print("⚠️ Backup import method not available, falling back to manual setup")
                    return await self._fallback_backup_import(backup_info)

            except ImportError:
                print("❌ deltatachat2 not available")
                print("💡 To fix this issue:")
                print("   1. Install Delta Chat core: pip install deltatachat2")
                print("   2. Or install from source: pip install git+https://github.com/deltachat/deltachat-core-rust.git")
                print("   3. Make sure you have Rust installed for compilation")
                print()
                print("🔄 Falling back to manual setup...")
                return await self._fallback_backup_import(backup_info)

            except Exception as e:
                print(f"❌ Error during backup import: {e}")
                print("💡 This might indicate the backup string format or RPC setup")
                return False

        except Exception as e:
            print(f"❌ Error setting up second device: {e}")
            print("💡 This indicates missing Delta Chat core installation")
            return False

    async def _fallback_backup_import(self, backup_info):
        """Fallback method when Delta Chat core is not available"""
        try:
            print("🔄 Using fallback backup import method...")
            print(f"📋 Backup info: {backup_info}")

            # For now, configure the account with the node_id
            # This is not ideal but provides basic functionality
            await self.account.configure(
                addr=backup_info['node_id'],
                mail_pw="",
                basedir=Config.BASEDIR
            )

            print(f"✅ Fallback configuration completed for: {backup_info['node_id']}")
            print("⚠️ Full pairing functionality requires Delta Chat core installation")

            # Mark as configured
            self.is_paired = True
            self.pairing_data = backup_info

            return True

        except Exception as e:
            print(f"❌ Fallback backup import failed: {e}")
            return False

    def get_account(self):
        """Get the Delta Chat account instance"""
        return self.account
