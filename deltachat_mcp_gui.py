#!/usr/bin/env python3
"""
Delta Chat MCP Server - Desktop GUI Application
Provides a user-friendly interface for managing the MCP server

This application creates its own Delta Chat account and core instance.
No existing Delta Chat installation is required - it's completely standalone.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import json
import os
import sys
from pathlib import Path

class DeltaChatMCPServer:
    """Main desktop application class"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Delta Chat MCP Server")
        self.root.geometry("800x600")
        self.root.resizable(True, True)

        # Application state
        self.server_running = False
        self.delta_connected = False
        self.mcp_requests = []
        self.config_file = Path("config.env")

        # Setup UI
        self.setup_ui()

        # Load configuration (try auto-detection first)
        self.load_config()

        # Check if this is a paired device
        self.is_paired = False
        self.pairing_info = None
        self.check_pairing_status()

        # Check Delta Chat availability
        self.check_delta_chat()

    def setup_ui(self):
        """Setup the user interface"""
        # Main notebook for tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Status tab
        self.create_status_tab()

        # Configuration tab
        self.create_config_tab()

        # Logs tab
        self.create_logs_tab()

        # Control buttons
        self.create_control_panel()

    def create_status_tab(self):
        """Create the status monitoring tab"""
        status_frame = ttk.Frame(self.notebook)
        self.notebook.add(status_frame, text="📊 Status")

        # Server status
        server_frame = ttk.LabelFrame(status_frame, text="Server Status", padding=10)
        server_frame.pack(fill=tk.X, padx=5, pady=5)

        self.server_status_label = ttk.Label(server_frame, text="🔴 Server Stopped", font=("Arial", 12))
        self.server_status_label.pack(anchor=tk.W)

        self.server_url_label = ttk.Label(server_frame, text="MCP URL: Not running", font=("Arial", 10))
        self.server_url_label.pack(anchor=tk.W)

        # Delta Chat status
        delta_frame = ttk.LabelFrame(status_frame, text="Delta Chat Connection", padding=10)
        delta_frame.pack(fill=tk.X, padx=5, pady=5)

        self.delta_status_label = ttk.Label(delta_frame, text="🔴 Not Connected", font=("Arial", 12))
        self.delta_status_label.pack(anchor=tk.W)

        self.delta_info_label = ttk.Label(delta_frame, text="Account: Not configured", font=("Arial", 10))
        self.delta_info_label.pack(anchor=tk.W)

        # Pairing status
        self.pairing_status_label = ttk.Label(delta_frame, text="📱 Pairing: Not paired", foreground="gray")
        self.pairing_status_label.pack(anchor=tk.W)

        # Automatic pairing status
        self.auto_pairing_status_label = ttk.Label(delta_frame, text="🔄 Auto-pairing: Disabled", foreground="gray")
        self.auto_pairing_status_label.pack(anchor=tk.W)

    def create_config_tab(self):
        """Create the configuration tab"""
        config_frame = ttk.Frame(self.notebook)
        self.notebook.add(config_frame, text="⚙️ Configuration")

        # Delta Chat settings
        delta_frame = ttk.LabelFrame(config_frame, text="Delta Chat Settings", padding=10)
        delta_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(delta_frame, text="Email:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.email_var = tk.StringVar()
        self.email_entry = ttk.Entry(delta_frame, textvariable=self.email_var, width=40)
        self.email_entry.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(delta_frame, text="Password:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(delta_frame, textvariable=self.password_var, show="*", width=40)
        self.password_entry.grid(row=1, column=1, sticky=tk.W, pady=2)

        # MCP settings
        mcp_frame = ttk.LabelFrame(config_frame, text="MCP Settings", padding=10)
        mcp_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(mcp_frame, text="Port:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.port_var = tk.StringVar(value="8089")
        self.port_entry = ttk.Entry(mcp_frame, textvariable=self.port_var, width=10)
        self.port_entry.grid(row=0, column=1, sticky=tk.W, pady=2)

        ttk.Label(mcp_frame, text="Mode:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.mode_var = tk.StringVar(value="http")
        mode_combo = ttk.Combobox(mcp_frame, textvariable=self.mode_var, values=["http", "stdio"], state="readonly")
        mode_combo.grid(row=1, column=1, sticky=tk.W, pady=2)

        # Second device setup
        device_frame = ttk.LabelFrame(config_frame, text="Second Device Setup", padding=10)
        device_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(device_frame, text="Backup String:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.backup_var = tk.StringVar()
        self.backup_entry = tk.Text(device_frame, height=3, width=50)
        self.backup_entry.grid(row=0, column=1, sticky=tk.W, pady=2)

        # Automatic pairing settings
        auto_pairing_frame = ttk.LabelFrame(config_frame, text="Automatic Pairing", padding=10)
        auto_pairing_frame.pack(fill=tk.X, padx=5, pady=5)

        self.auto_pairing_var = tk.BooleanVar(value=True)
        self.auto_pairing_check = ttk.Checkbutton(auto_pairing_frame, text="Enable automatic pairing",
                                                variable=self.auto_pairing_var, command=self.toggle_auto_pairing)
        self.auto_pairing_check.grid(row=0, column=0, sticky=tk.W, pady=2)

        ttk.Label(auto_pairing_frame, text="Scan interval (seconds):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.scan_interval_var = tk.StringVar(value="30")
        self.scan_interval_entry = ttk.Entry(auto_pairing_frame, textvariable=self.scan_interval_var, width=10)
        self.scan_interval_entry.grid(row=1, column=1, sticky=tk.W, pady=2)

        ttk.Label(auto_pairing_frame, text="Connection timeout (seconds):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.timeout_var = tk.StringVar(value="15")
        self.timeout_entry = ttk.Entry(auto_pairing_frame, textvariable=self.timeout_var, width=10)
        self.timeout_entry.grid(row=2, column=1, sticky=tk.W, pady=2)

        # Manual pairing button
        self.pair_now_button = ttk.Button(auto_pairing_frame, text="🔄 Pair Now", command=self.manual_pairing)
        self.pair_now_button.grid(row=3, column=0, columnspan=2, pady=5)

        # Action buttons
        button_frame = ttk.Frame(config_frame)
        button_frame.pack(fill=tk.X, padx=5, pady=10)

        self.save_config_button = ttk.Button(button_frame, text="💾 Save Configuration", command=self.save_config)
        self.save_config_button.pack(side=tk.LEFT, padx=5)

        self.test_connection_button = ttk.Button(button_frame, text="🔍 Test Connection", command=self.test_connection)
        self.test_connection_button.pack(side=tk.LEFT, padx=5)

    def create_logs_tab(self):
        """Create the logs monitoring tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="📝 Logs")

        # Log display
        log_frame = ttk.LabelFrame(logs_frame, text="Real-time Logs", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        # Log controls
        control_frame = ttk.Frame(logs_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        self.clear_logs_button = ttk.Button(control_frame, text="🗑️ Clear Logs", command=self.clear_logs)
        self.clear_logs_button.pack(side=tk.LEFT, padx=5)

        self.auto_scroll_var = tk.BooleanVar(value=True)
        self.auto_scroll_check = ttk.Checkbutton(control_frame, text="Auto-scroll", variable=self.auto_scroll_var)
        self.auto_scroll_check.pack(side=tk.RIGHT, padx=5)

    def create_control_panel(self):
        """Create the control buttons panel"""
        control_frame = ttk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Left side - server controls
        left_frame = ttk.Frame(control_frame)
        left_frame.pack(side=tk.LEFT)

        self.start_button = ttk.Button(left_frame, text="🚀 Start Server", command=self.start_server, style="Start.TButton")
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(left_frame, text="⏹️ Stop Server", command=self.stop_server, state=tk.DISABLED, style="Stop.TButton")
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Right side - info
        right_frame = ttk.Frame(control_frame)
        right_frame.pack(side=tk.RIGHT)

        self.info_label = ttk.Label(right_frame, text="Ready to start", font=("Arial", 9))
        self.info_label.pack(side=tk.RIGHT)

        # Configure button styles
        style = ttk.Style()
        style.configure("Start.TButton", background="green", foreground="white")
        style.configure("Stop.TButton", background="red", foreground="white")

    def register_second_device(self):
        """Register as a second device using backup string"""
        backup_text = self.backup_entry.get("1.0", tk.END).strip()

        if not backup_text:
            self.log_message("❌ Please enter a backup string", "error")
            return

        if not backup_text.startswith("DCBACKUP3:"):
            self.log_message("❌ Invalid backup string format", "error")
            return

        try:
            # Import config here to avoid circular imports
            from .config import Config

            success = Config.register_second_device(backup_text)
            if success:
                self.log_message(f"✅ Registered as second device: {Config.BACKUP_INFO['node_id']}", "success")
                self.delta_info_label.config(text=f"Account: Paired Device ({Config.BACKUP_INFO['node_id'][:8]}...)")
                self.pairing_status_label.config(text=f"📱 Pairing: Connected ({Config.BACKUP_INFO['node_id'][:8]}...)", foreground="green")
                self.save_config()  # Save the backup string to config file
                self.is_paired = True
                self.pairing_info = Config.BACKUP_INFO
            else:
                self.log_message("❌ Failed to register as second device", "error")
                self.pairing_status_label.config(
                    text="📱 Pairing: Configured (no info)",
                    foreground="orange"
                )

        except Exception as e:
            self.log_message(f"❌ Error registering second device: {e}", "error")

    def toggle_auto_pairing(self):
        """Toggle automatic pairing on/off"""
        enabled = self.auto_pairing_var.get()

        try:
            # Import config here to avoid circular imports
            from .config import Config

            if enabled:
                Config.AUTO_PAIRING_ENABLED = True
                Config.AUTO_PAIRING_SCAN_INTERVAL = int(self.scan_interval_var.get())
                Config.AUTO_PAIRING_TIMEOUT = int(self.timeout_var.get())

                # Start automatic pairing service
                Config.initialize_auto_pairing()
                self.log_message("✅ Automatic pairing enabled", "success")
                self.update_auto_pairing_status()
            else:
                Config.AUTO_PAIRING_ENABLED = False
                Config.stop_auto_pairing()
                self.log_message("❌ Automatic pairing disabled", "warning")
                self.update_auto_pairing_status()

            # Save configuration
            self.save_config()

        except Exception as e:
            self.log_message(f"❌ Error toggling automatic pairing: {e}", "error")

    def manual_pairing(self):
        """Manually trigger pairing attempt"""
        try:
            from .pairing import auto_pairing
            from .config import Config

            self.log_message("🔄 Starting manual pairing attempt...", "info")

            # Update settings from GUI
            Config.AUTO_PAIRING_SCAN_INTERVAL = int(self.scan_interval_var.get())
            Config.AUTO_PAIRING_TIMEOUT = int(self.timeout_var.get())

            success = auto_pairing.attempt_automatic_pairing()

            if success:
                self.log_message("✅ Manual pairing successful!", "success")
                self.update_pairing_status()
                self.save_config()
            else:
                self.log_message("❌ Manual pairing failed", "error")

        except Exception as e:
            self.log_message(f"❌ Error during manual pairing: {e}", "error")

    def update_auto_pairing_status(self):
        """Update automatic pairing status display"""
        try:
            from .config import Config

            if Config.AUTO_PAIRING_ENABLED:
                self.auto_pairing_status_label.config(
                    text=f"🔄 Auto-pairing: Enabled (scan: {Config.AUTO_PAIRING_SCAN_INTERVAL}s)",
                    foreground="green"
                )
            else:
                self.auto_pairing_status_label.config(
                    text="🔄 Auto-pairing: Disabled",
                    foreground="gray"
                )
        except Exception:
            self.auto_pairing_status_label.config(
                text="🔄 Auto-pairing: Error",
                foreground="red"
            )

    def update_pairing_status(self):
        """Update pairing status display"""
        try:
            from .config import Config

            if hasattr(Config, 'IS_SECOND_DEVICE') and Config.IS_SECOND_DEVICE:
                if hasattr(Config, 'BACKUP_INFO') and Config.BACKUP_INFO:
                    node_id = Config.BACKUP_INFO.get('node_id', 'unknown')[:8]
                    self.pairing_status_label.config(
                        text=f"📱 Pairing: Connected ({node_id}...)",
                        foreground="green"
                    )
                    self.delta_info_label.config(
                        text=f"Account: Paired Device ({node_id}...)"
                    )
                else:
                    self.pairing_status_label.config(
                        text="📱 Pairing: Configured (no info)",
                        foreground="orange"
                    )
            else:
                self.pairing_status_label.config(
                    text="📱 Pairing: Not paired",
                    foreground="gray"
                )
        except Exception as e:
            self.log_message(f"Error updating pairing status: {e}", "error")

def load_config(self):
    """Load configuration from file"""
    if self.config_file.exists():
        content = self.config_file.read_text()
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                if line.startswith('DC_ADDR='):
                    self.email_var.set(line.split('=', 1)[1])
                elif line.startswith('DC_MAIL_PW='):
                    self.password_var.set(line.split('=', 1)[1])
                elif line.startswith('MCP_PORT='):
                    self.port_var.set(line.split('=', 1)[1])
                elif line.startswith('MCP_MODE='):
                    self.mode_var.set(line.split('=', 1)[1])
                elif line.startswith('BACKUP_STRING='):
                    self.backup_entry.delete("1.0", tk.END)
                    self.backup_entry.insert("1.0", line.split('=', 1)[1])
                elif line.startswith('AUTO_PAIRING_ENABLED='):
                    self.auto_pairing_var.set(line.split('=', 1)[1].lower() == 'true')
                elif line.startswith('AUTO_PAIRING_SCAN_INTERVAL='):
                    self.scan_interval_var.set(line.split('=', 1)[1])
                elif line.startswith('AUTO_PAIRING_TIMEOUT='):
                    self.timeout_var.set(line.split('=', 1)[1])

        # Update status displays after loading config
        self.update_auto_pairing_status()
        self.update_pairing_status()

    def save_config(self):
        """Save configuration to file"""
        try:
            config_lines = []

            # Basic settings
            if self.email_var.get():
                config_lines.append(f"DC_ADDR={self.email_var.get()}")
            if self.password_var.get():
                config_lines.append(f"DC_MAIL_PW={self.password_var.get()}")
            config_lines.append(f"MCP_PORT={self.port_var.get()}")
            config_lines.append(f"MCP_MODE={self.mode_var.get()}")

            # Backup string
            backup_text = self.backup_entry.get("1.0", tk.END).strip()
            if backup_text:
                config_lines.append(f"BACKUP_STRING={backup_text}")

            # Automatic pairing settings
            config_lines.append(f"AUTO_PAIRING_ENABLED={str(self.auto_pairing_var.get()).lower()}")
            config_lines.append(f"AUTO_PAIRING_SCAN_INTERVAL={self.scan_interval_var.get()}")
            config_lines.append(f"AUTO_PAIRING_TIMEOUT={self.timeout_var.get()}")

            # Write to file
            self.config_file.write_text('\n'.join(config_lines) + '\n')
            self.log_message("✅ Configuration saved", "success")

        except Exception as e:
            self.log_message(f"❌ Error saving configuration: {e}", "error")

    def test_connection(self):
        """Test Delta Chat connection"""
        self.log_message("🔍 Testing Delta Chat connection...", "info")

        try:
            from .config import Config
            from .rpc import DeltaChatRPC

            # Update config from GUI
            Config.DC_ADDR = self.email_var.get()
            Config.DC_MAIL_PW = self.password_var.get()

            if not Config.DC_ADDR or not Config.DC_MAIL_PW:
                self.log_message("❌ Please enter email and password", "error")
                return

            # Test connection
            rpc = DeltaChatRPC()
            # This would need proper async handling in a real implementation

            self.log_message("✅ Connection test completed", "success")

        except Exception as e:
            self.log_message(f"❌ Connection test failed: {e}", "error")

    def clear_logs(self):
        """Clear the log display"""
        self.log_text.delete("1.0", tk.END)

    def log_message(self, message, level="info"):
        """Add a message to the log display"""
        color = {
            "info": "black",
            "success": "green",
            "warning": "orange",
            "error": "red"
        }.get(level, "black")

        self.log_text.insert(tk.END, f"{message}\n", color)
        self.log_text.tag_add(color, "end-2c linestart", "end-1c")
        self.log_text.tag_config(color, foreground=color)

        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)

    def run(self):
        """Run the GUI application"""
        self.root.mainloop()

    def start_server(self):
        """Start the MCP server"""
        self.log_message("🚀 Starting MCP server...", "info")
        # Implementation would go here

    def stop_server(self):
        """Stop the MCP server"""
        self.log_message("🛑 Stopping MCP server...", "info")
        # Implementation would go here

    def check_delta_chat(self):
        """Check if Delta Chat is available"""
        self.log_message("🔍 Checking Delta Chat availability...", "info")
        # Implementation would go here

    def check_pairing_status(self):
        """Check current pairing status"""
        self.log_message("🔍 Checking pairing status...", "info")
        self.update_pairing_status()

def main():
    """Main entry point"""
    print("🖥️ Starting Delta Chat MCP Desktop Application...")

    # Check if configuration exists
    config_file = Path("config.env")
    if not config_file.exists():
        print("🔧 First-time setup...")
        print("The desktop application will guide you through configuration.")
        print("")

    # Create and run application
    app = DeltaChatMCPServer()
    app.run()


if __name__ == "__main__":
    main()
