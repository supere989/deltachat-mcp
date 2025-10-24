# deltachat_mcp/config.py
import os
import sqlite3
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    # First try to load from environment
    DC_ADDR = os.getenv("DC_ADDR")
    DC_MAIL_PW = os.getenv("DC_MAIL_PW")
    MCP_MODE = os.getenv("MCP_MODE", "http").lower()  # http or stdio
    MCP_PORT = int(os.getenv("MCP_PORT", "8089"))
    BASEDIR = Path(os.getenv("BASEDIR", "./dc-data")).expanduser()
    BACKUP_STRING = os.getenv("BACKUP_STRING")

    # Second device configuration
    BACKUP_INFO = None
    IS_SECOND_DEVICE = False

    @staticmethod
    def _find_delta_chat_databases():
        """Find Delta Chat database files in common locations"""
        search_paths = [
            Path.home() / '.config' / 'deltachat',
            Path.home() / '.deltachat',
            Path.home() / 'dc-data',
            Path.home() / '.local' / 'share' / 'deltachat',
            Path.home() / 'Documents' / 'deltachat',
            Path.home() / 'Documents' / 'DeltaChat'
        ]

        db_files = []
        for search_path in search_paths:
            if search_path.exists():
                for file in search_path.glob('*.db'):
                    db_files.append(file)
                for file in search_path.glob('*.sqlite'):
                    db_files.append(file)

        # Also search recursively in home directory
        for root, dirs, files in os.walk(str(Path.home())):
            # Skip hidden directories and common exclusions
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['.cache', '.local', 'node_modules']]
            for file in files:
                if file.endswith('.db') or file.endswith('.sqlite'):
                    file_path = Path(root) / file
                    # Check if this looks like a Delta Chat database
                    if Config._is_delta_chat_db(file_path):
                        db_files.append(file_path)

        return db_files

    @staticmethod
    def _is_delta_chat_db(db_path):
        """Check if a database file looks like Delta Chat configuration"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Check for Delta Chat-specific tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            # Delta Chat typically has these tables
            delta_indicators = ['accounts', 'account', 'config', 'chats', 'msgs', 'contacts']
            table_matches = sum(1 for table in tables if any(indicator in table.lower() for indicator in delta_indicators))

            conn.close()
            return table_matches >= 2  # At least 2 matching tables

        except (sqlite3.Error, OSError):
            return False

    @staticmethod
    def _read_delta_chat_config(db_path):
        """Read configuration from a Delta Chat database"""
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # Try to read account configuration
            # Delta Chat stores config in the 'config' table with key-value pairs
            cursor.execute("SELECT key, value FROM config WHERE key IN ('addr', 'mail_pw', 'configured_addr')")
            config_rows = cursor.fetchall()

            conn.close()

            config = {}
            for key, value in config_rows:
                if key == 'configured_addr' and not config.get('addr'):
                    config['addr'] = value
                elif key == 'addr':
                    config['addr'] = value
                elif key == 'mail_pw':
                    config['mail_pw'] = value

            return config

        except (sqlite3.Error, OSError):
            return {}

    @classmethod
    def auto_detect_credentials(cls):
        """Auto-detect Delta Chat credentials from existing installation"""
        print("🔍 Searching for existing Delta Chat configuration...")

        # Find Delta Chat databases
        db_files = cls._find_delta_chat_databases()

        if not db_files:
            print("❌ No Delta Chat databases found")
            return False

        print(f"📊 Found {len(db_files)} potential Delta Chat databases")

        # Try to read configuration from each database
        for db_file in db_files:
            print(f"   Checking: {db_file.name}")
            config = cls._read_delta_chat_config(db_file)

            if config.get('addr') and config.get('mail_pw'):
                print(f"✅ Found credentials in: {db_file}")
                cls.DC_ADDR = config['addr']
                cls.DC_MAIL_PW = config['mail_pw']
                print(f"   Email: {cls.DC_ADDR}")
                print(f"   Data: {db_file.parent}")
                cls.BASEDIR = db_file.parent
                return True

        print("❌ No valid Delta Chat credentials found in existing databases")
        return False

    @staticmethod
    def validate():
        """Validate configuration, trying auto-detection first"""
        # Check for backup string first (second device mode)
        if Config.BACKUP_STRING:
            if Config.register_second_device(Config.BACKUP_STRING):
                print("✅ Using backup string for second device registration")
                return
            else:
                print("❌ Invalid backup string, falling back to regular configuration")

        # First try auto-detection
        if not Config.DC_ADDR or not Config.DC_MAIL_PW:
            if Config.auto_detect_credentials():
                print("✅ Using credentials from existing Delta Chat installation")
                return

        # Fall back to environment validation
        if not Config.DC_ADDR or not Config.DC_MAIL_PW:
            raise ValueError(
                "Delta Chat credentials not found. Please either:\n"
                "1. Set DC_ADDR and DC_MAIL_PW in .env file, or\n"
                "2. Set BACKUP_STRING in .env file for second device, or\n"
                "3. Install and configure Delta Chat desktop application, or\n"
                "4. Run: python configure.py to set up manually"
            )

    @classmethod
    def parse_backup_string(cls, backup_string):
        """Parse a Delta Chat backup string for second device registration"""
        try:
            if not backup_string.startswith('DCBACKUP3:'):
                raise ValueError("Invalid backup string format")

            # Split the backup string into data and metadata parts
            parts = backup_string.split('&', 1)
            if len(parts) != 2:
                raise ValueError("Backup string missing metadata section")

            encrypted_data = parts[0]
            metadata_json = parts[1]

            # Parse the metadata JSON
            import json
            metadata = json.loads(metadata_json)

            return {
                'encrypted_data': encrypted_data,
                'node_id': metadata.get('node_id'),
                'relay_url': metadata.get('relay_url'),
                'direct_addresses': metadata.get('direct_addresses', [])
            }

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            print(f"❌ Error parsing backup string: {e}")
            return None

    @classmethod
    def register_second_device(cls, backup_string):
        """Register as a second device using a backup string"""
        print("🔄 Registering as second device...")

        backup_info = cls.parse_backup_string(backup_string)
        if not backup_info:
            return False

        print(f"✅ Parsed backup string for node: {backup_info['node_id']}")
        print(f"📍 Direct addresses: {backup_info['direct_addresses']}")

        # Store the backup information for use during account setup
        cls.BACKUP_INFO = backup_info
        cls.IS_SECOND_DEVICE = True

        return True

    @classmethod
    def setup_second_device_account(cls):
        """Set up account as a second device using backup data"""
        if not hasattr(cls, 'BACKUP_INFO') or not cls.BACKUP_INFO:
            return False

        backup_info = cls.BACKUP_INFO

        # For second device, we use the backup data instead of email/password
        # The deltatachat2 library should handle the backup import
        print(f"🔧 Setting up second device account for node: {backup_info['node_id']}")

        # Note: The actual backup import would need to be implemented
        # based on the deltatachat2 library's backup handling capabilities

        return True
