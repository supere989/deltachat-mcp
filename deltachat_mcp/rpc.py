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
        """Set up account as a second device by connecting to primary device"""
        if not hasattr(Config, 'BACKUP_INFO') or not Config.BACKUP_INFO:
            raise ValueError("No backup information available for second device setup")

        backup_info = Config.BACKUP_INFO
        print(f"🔧 Setting up second device pairing: {backup_info['node_id']}")
        print(f"📍 Available connection endpoints: {backup_info['direct_addresses']}")

        # For proper pairing, we need to connect to the primary device
        # and complete the handshake process
        pairing_success = await self._complete_pairing_handshake(backup_info)

        if pairing_success:
            print(f"✅ Second device paired successfully: {backup_info['node_id']}")
            # Configure the account with the paired connection
            await self._configure_paired_account(backup_info)
        else:
            print("❌ Pairing failed, falling back to standalone mode")
            # Fall back to regular configuration
            await self.account.configure(
                addr=Config.DC_ADDR,
                mail_pw=Config.DC_MAIL_PW,
                basedir=Config.BASEDIR
            )

    async def _complete_pairing_handshake(self, backup_info):
        """Complete the pairing handshake with the primary device"""
        import websockets
        import json
        import asyncio

        node_id = backup_info['node_id']
        direct_addresses = backup_info['direct_addresses']

        print(f"🔗 Attempting to connect to primary device...")
        print(f"📍 Available endpoints: {len(direct_addresses)} addresses")

        # Try to connect to each direct address until one works
        for address in direct_addresses:
            try:
                print(f"   🔌 Connecting to: {address}")
                uri = f"ws://{address}/"

                # Set connection timeout
                try:
                    async with websockets.connect(uri, timeout=10.0) as websocket:
                        print(f"✅ Connected to: {address}")

                        # Send pairing handshake
                        handshake_message = {
                            "type": "pairing_request",
                            "node_id": node_id,
                            "version": "1.0"
                        }

                        await websocket.send(json.dumps(handshake_message))
                        print(f"📤 Sent pairing request for node: {node_id}")

                        # Wait for response with timeout
                        try:
                            response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                            response_data = json.loads(response)

                            if response_data.get("type") == "pairing_accepted":
                                print("✅ Pairing accepted by primary device")
                                print(f"   Account info: {response_data.get('account_info', 'N/A')}")

                                # Store pairing information for account configuration
                                self.pairing_data = {
                                    "primary_address": address,
                                    "node_id": node_id,
                                    "account_info": response_data.get("account_info", {})
                                }

                                return True
                            else:
                                error_msg = response_data.get('error', 'Unknown error')
                                print(f"❌ Pairing rejected: {error_msg}")

                        except asyncio.TimeoutError:
                            print(f"   ⏱️ Timeout waiting for pairing response from {address}")
                            continue

                except asyncio.TimeoutError:
                    print(f"   ⏱️ Connection timeout to {address}")
                    continue
                except Exception as e:
                    print(f"   ❌ WebSocket error for {address}: {e}")
                    continue

            except Exception as e:
                print(f"   ❌ Failed to connect to {address}: {e}")
                continue

        print("❌ Could not connect to any primary device endpoint")
        print("💡 Make sure:")
        print("   - Delta Chat desktop client is running and in pairing mode")
        print("   - The backup string is current and valid")
        print("   - Network connectivity is available")
        print("   - Firewall allows connections to the specified ports")
        return False

    async def _configure_paired_account(self, backup_info):
        """Configure the account for multi-device operation"""
        try:
            # For paired accounts, we use the node_id and pairing information
            # instead of regular email/password configuration
            node_id = backup_info['node_id']

            # The account should be configured to work in multi-device mode
            # using the established connection
            await self.account.configure(
                addr=node_id,  # Use node_id as the account identifier
                mail_pw="",  # No password needed for paired device
                basedir=Config.BASEDIR
            )

            print(f"✅ Paired account configured: {node_id}")

            # Mark that we're in paired mode
            self.is_paired = True
            self.primary_connection = self.pairing_data

        except Exception as e:
            print(f"❌ Error configuring paired account: {e}")
            raise

    def get_account(self) -> Account:
        return self.account
