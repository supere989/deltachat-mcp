# deltachat_mcp/pairing.py
"""
Automatic pairing functionality for Delta Chat MCP server
Handles network discovery and automatic second device pairing
"""
import asyncio
import json
import socket
import threading
import time
from typing import Optional, Dict, List, Tuple
import websockets
import subprocess
import os
from pathlib import Path
import sqlite3

class NetworkDiscovery:
    """Discover running Delta Chat clients on the local network"""

    def __init__(self):
        self.discovered_clients = []
        self.scan_running = False
        self._scan_thread = None

    def get_local_networks(self) -> List[str]:
        """Get local network interfaces and their subnets"""
        networks = []

        try:
            # Use system commands to get network interfaces
            if os.name == 'posix':  # Linux/Mac
                result = subprocess.run(['ip', 'route'], capture_output=True, text=True)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'src' in line and line.strip():
                            parts = line.split()
                            if len(parts) >= 3:
                                networks.append(parts[0])
            else:  # Windows
                result = subprocess.run(['ipconfig'], capture_output=True, text=True)
                # Parse Windows output (simplified)
                for line in result.stdout.split('\n'):
                    if 'Subnet Mask' in line:
                        networks.append("192.168.1.0/24")  # Default fallback
        except Exception as e:
            print(f"Warning: Could not detect networks: {e}")
            # Fallback to common private networks
            networks = ["192.168.1.0/24", "10.0.0.0/24", "172.16.0.0/24"]

        return list(set(networks))  # Remove duplicates

    def scan_network_for_deltachat(self, network: str) -> List[Dict]:
        """Scan a network for Delta Chat clients"""
        clients = []

        try:
            # Parse network CIDR
            if '/' in network:
                network_base, prefix = network.split('/')
                prefix = int(prefix)
            else:
                network_base = network
                prefix = 24

            # Generate IP range
            ip_parts = network_base.split('.')
            if len(ip_parts) != 4:
                return clients

            # Calculate range
            base_ip = int(ip_parts[3])
            mask = (0xffffffff << (32 - prefix)) & 0xffffffff
            network_int = sum(int(ip_parts[i]) << (24 - 8 * i) for i in range(4)) & mask
            broadcast_int = network_int | (~mask & 0xffffffff)

            start_ip = network_int + 1
            end_ip = broadcast_int - 1

            # Common Delta Chat ports
            ports_to_check = [9933, 9934, 42654, 42655]  # Delta Chat WebSocket ports

            # Scan for open ports (simplified - in production, use proper async scanning)
            for ip_int in range(start_ip, min(end_ip + 1, start_ip + 50)):  # Limit scan range
                ip = '.'.join(str((ip_int >> (24 - 8 * i)) & 0xff) for i in range(4))

                for port in ports_to_check:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(0.5)
                        result = sock.connect_ex((ip, port))
                        sock.close()

                        if result == 0:  # Port is open
                            client_info = {
                                'ip': ip,
                                'port': port,
                                'timestamp': time.time(),
                                'network': network
                            }
                            clients.append(client_info)
                            break  # Found one port, move to next IP

                    except Exception:
                        continue

        except Exception as e:
            print(f"Error scanning network {network}: {e}")

        return clients

    def start_continuous_scan(self, callback=None):
        """Start continuous network scanning in background thread"""
        if self.scan_running:
            return

        self.scan_running = True
        self._scan_thread = threading.Thread(target=self._scan_loop, args=(callback,), daemon=True)
        self._scan_thread.start()

    def stop_continuous_scan(self):
        """Stop continuous network scanning"""
        self.scan_running = False
        if self._scan_thread:
            self._scan_thread.join(timeout=1.0)

    def _scan_loop(self, callback=None):
        """Background scanning loop"""
        while self.scan_running:
            try:
                networks = self.get_local_networks()
                new_clients = []

                for network in networks:
                    clients = self.scan_network_for_deltachat(network)
                    new_clients.extend(clients)

                # Update discovered clients
                self.discovered_clients = new_clients

                # Notify callback if provided
                if callback and new_clients:
                    callback(new_clients)

                # Wait before next scan
                time.sleep(30)  # Scan every 30 seconds

            except Exception as e:
                print(f"Error in network scan loop: {e}")
                time.sleep(60)  # Wait longer on error

    def get_discovered_clients(self) -> List[Dict]:
        """Get currently discovered Delta Chat clients"""
        return self.discovered_clients.copy()

class AutoPairing:
    """Handle automatic pairing with Delta Chat clients"""

    def __init__(self):
        self.network_discovery = NetworkDiscovery()
        self.is_pairing = False
        self.paired_info = None
        self._pairing_thread = None

    def find_delta_chat_databases(self) -> List[Path]:
        """Find Delta Chat database files for auto-detection"""
        search_paths = [
            Path.home() / '.config' / 'deltachat',
            Path.home() / '.deltachat',
            Path.home() / 'dc-data',
            Path.home() / '.local' / 'share' / 'deltachat',
        ]

        db_files = []
        for search_path in search_paths:
            if search_path.exists():
                for pattern in ['*.db', '*.sqlite']:
                    db_files.extend(search_path.glob(pattern))

        return db_files

    def extract_backup_from_db(self, db_path: Path) -> Optional[str]:
        """Extract backup string from Delta Chat database"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Look for backup information in the database
            cursor.execute("SELECT key, value FROM config WHERE key LIKE '%backup%' OR key LIKE '%node%'")
            config_rows = cursor.fetchall()

            # Also check for device information
            cursor.execute("SELECT key, value FROM config WHERE key IN ('selfaddr', 'addr', 'configured_addr')")
            addr_rows = cursor.fetchall()

            conn.close()

            # If we found configuration, we might be able to reconstruct pairing info
            # This is a simplified approach - real implementation would need to handle
            # the actual backup string format properly

            return None  # Placeholder - would need proper backup string extraction

        except Exception as e:
            print(f"Error extracting backup from {db_path}: {e}")
            return None

    def monitor_clipboard_for_backup(self) -> Optional[str]:
        """Monitor clipboard for Delta Chat backup strings"""
        try:
            # Try to read from clipboard (Linux)
            if os.name == 'posix':
                result = subprocess.run(['xclip', '-o', '-selection', 'clipboard'],
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    clipboard_content = result.stdout.strip()
                    if clipboard_content.startswith('DCBACKUP3:'):
                        return clipboard_content

                # Try alternative clipboard tools
                result = subprocess.run(['xsel', '-o', '--clipboard'],
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    clipboard_content = result.stdout.strip()
                    if clipboard_content.startswith('DCBACKUP3:'):
                        return clipboard_content

        except Exception as e:
            print(f"Error monitoring clipboard: {e}")

        return None

    def attempt_automatic_pairing(self, backup_string: Optional[str] = None) -> bool:
        """Attempt automatic pairing with discovered clients"""
        if self.is_pairing:
            return False

        self.is_pairing = True

        try:
            # If no backup string provided, try to get one
            if not backup_string:
                backup_string = self._get_backup_string()

            if not backup_string:
                print("❌ No backup string available for pairing")
                return False

            print(f"🔄 Attempting automatic pairing with backup string...")
            print(f"   Backup node: {backup_string.split('&')[1] if '&' in backup_string else 'unknown'}")

            # Parse backup string
            from .config import Config
            backup_info = Config.parse_backup_string(backup_string)

            if not backup_info:
                print("❌ Invalid backup string format")
                return False

            # Try to pair with discovered clients
            success = self._try_pairing_with_clients(backup_info)

            if success:
                print("✅ Automatic pairing successful!")
                self.paired_info = backup_info
                return True
            else:
                print("❌ Automatic pairing failed")
                return False

        finally:
            self.is_pairing = False

    def _get_backup_string(self) -> Optional[str]:
        """Get backup string from various sources"""
        # First try clipboard
        clipboard_backup = self.monitor_clipboard_for_backup()
        if clipboard_backup:
            print("📋 Found backup string in clipboard")
            return clipboard_backup

        # Then try existing databases
        db_files = self.find_delta_chat_databases()
        for db_file in db_files:
            backup = self.extract_backup_from_db(db_file)
            if backup:
                print(f"💾 Found backup string in database: {db_file}")
                return backup

        return None

    def _try_pairing_with_clients(self, backup_info: Dict) -> bool:
        """Try to pair with discovered Delta Chat clients"""
        import asyncio

        # Get discovered clients
        clients = self.network_discovery.get_discovered_clients()

        if not clients:
            print("🔍 No Delta Chat clients discovered on network")
            print("💡 Make sure Delta Chat desktop is running and in pairing mode")
            return False

        print(f"📍 Found {len(clients)} potential Delta Chat clients")

        # Try to connect to each client
        for client in clients:
            print(f"🔌 Trying to pair with {client['ip']}:{client['port']}")

            try:
                # Attempt WebSocket connection and pairing handshake
                success = asyncio.run(self._attempt_single_pairing(client, backup_info))
                if success:
                    print(f"✅ Successfully paired with {client['ip']}:{client['port']}")
                    return True

            except Exception as e:
                print(f"❌ Failed to pair with {client['ip']}:{client['port']} - {e}")
                continue

        return False

    async def _attempt_single_pairing(self, client: Dict, backup_info: Dict) -> bool:
        """Attempt pairing with a single client"""
        try:
            uri = f"ws://{client['ip']}:{client['port']}/"

            async with websockets.connect(uri, timeout=10.0) as websocket:
                print(f"   Connected to {client['ip']}:{client['port']}")

                # Send pairing request
                handshake_message = {
                    "type": "pairing_request",
                    "node_id": backup_info['node_id'],
                    "version": "1.0"
                }

                await websocket.send(json.dumps(handshake_message))
                print(f"   Sent pairing request for node: {backup_info['node_id']}")

                # Wait for response
                response = await asyncio.wait_for(websocket.recv(), timeout=15.0)
                response_data = json.loads(response)

                if response_data.get("type") == "pairing_accepted":
                    print("   ✅ Pairing accepted by primary device")
                    return True
                else:
                    print(f"   ❌ Pairing rejected: {response_data.get('error', 'Unknown error')}")
                    return False

        except asyncio.TimeoutError:
            print(f"   ⏱️ Connection timeout to {client['ip']}:{client['port']}")
            return False
        except Exception as e:
            print(f"   ❌ Connection error: {e}")
            return False

    def start_auto_pairing_service(self):
        """Start the automatic pairing service"""
        print("🚀 Starting automatic pairing service...")

        # Start network discovery
        self.network_discovery.start_continuous_scan(callback=self._on_clients_discovered)

        # Start pairing attempts in background thread
        self._pairing_thread = threading.Thread(target=self._pairing_loop, daemon=True)
        self._pairing_thread.start()

    def stop_auto_pairing_service(self):
        """Stop the automatic pairing service"""
        print("🛑 Stopping automatic pairing service...")
        self.network_discovery.stop_continuous_scan()

    def _on_clients_discovered(self, clients: List[Dict]):
        """Callback when new clients are discovered"""
        if clients and not self.is_pairing:
            print(f"📱 Discovered {len(clients)} Delta Chat client(s)")
            for client in clients:
                print(f"   - {client['ip']}:{client['port']}")

            # Automatically attempt pairing if we have a backup string
            backup_string = self._get_backup_string()
            if backup_string:
                print("🔄 Auto-initiating pairing...")
                self.attempt_automatic_pairing(backup_string)

    def _pairing_loop(self):
        """Background loop for automatic pairing attempts"""
        while True:
            try:
                if not self.is_pairing and not self.paired_info:
                    # Try to get backup string and pair
                    backup_string = self._get_backup_string()
                    if backup_string:
                        self.attempt_automatic_pairing(backup_string)

                # Wait before next attempt
                time.sleep(60)  # Try every minute

            except Exception as e:
                print(f"Error in pairing loop: {e}")
                time.sleep(120)  # Wait longer on error

# Global instance
auto_pairing = AutoPairing()
