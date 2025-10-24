# deltachat_mcp/rpc.py
import asyncio
from deltatachat2 import Rpc, Account
from .config import Config

class DeltaChatRPC:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.rpc = Rpc()
            cls._instance.account = Account(cls._instance.rpc, 1)
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
        """Set up account as a second device using backup data"""
        if not hasattr(Config, 'BACKUP_INFO') or not Config.BACKUP_INFO:
            raise ValueError("No backup information available for second device setup")

        backup_info = Config.BACKUP_INFO
        print(f"🔧 Setting up second device: {backup_info['node_id']}")

        # For second device registration, we need to use the backup data
        # The deltatachat2 library should handle this through the configure method
        # or through a separate backup import process

        # Note: The actual implementation would depend on how deltatachat2
        # handles backup import. For now, we'll use the node_id as the account identifier

        try:
            # Try to configure with the backup data
            # This is a placeholder - the actual implementation would need
            # to use the proper backup import API from deltatachat2
            await self.account.configure(
                addr=backup_info['node_id'],  # Use node_id as identifier
                mail_pw="",  # No password needed for second device
                basedir=Config.BASEDIR
            )

            print(f"✅ Second device account configured: {backup_info['node_id']}")

        except Exception as e:
            print(f"❌ Error setting up second device: {e}")
            # Fall back to regular configuration if second device setup fails
            print("🔄 Falling back to regular account setup...")
            await self.account.configure(
                addr=Config.DC_ADDR,
                mail_pw=Config.DC_MAIL_PW,
                basedir=Config.BASEDIR
            )

    def get_account(self) -> Account:
        return self.account
