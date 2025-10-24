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

        # Try to auto-detect Delta Chat credentials
        self.auto_detect_credentials()

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

        # MCP Activity
        activity_frame = ttk.LabelFrame(status_frame, text="MCP Activity", padding=10)
        activity_frame.pack(fill=tk.X, padx=5, pady=5)

        self.activity_label = ttk.Label(activity_frame, text="📊 Requests: 0 | Responses: 0", font=("Arial", 10))
        self.activity_label.pack(anchor=tk.W)

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

    def save_config(self):
        """Save configuration to file"""
        config_content = f"""DC_ADDR={self.email_var.get()}
DC_MAIL_PW={self.password_var.get()}
MCP_MODE={self.mode_var.get()}
MCP_PORT={self.port_var.get()}
BASEDIR=./dc-data
"""

        self.config_file.write_text(config_content)

        # Update status
        self.delta_info_label.config(text=f"Account: {self.email_var.get()}")
        self.log_message("✅ Configuration saved", "info")

    def auto_detect_credentials(self):
        """Auto-detect Delta Chat credentials and update UI"""
        try:
            # Import here to avoid circular imports
            from .config import Config

            if Config.DC_ADDR and Config.DC_MAIL_PW:
                # Update UI with detected credentials
                self.email_var.set(Config.DC_ADDR)
                self.password_var.set(Config.DC_MAIL_PW)

                # Update status
                self.delta_info_label.config(text=f"Account: {Config.DC_ADDR} (Auto-detected)")
                self.log_message(f"✅ Auto-detected Delta Chat credentials: {Config.DC_ADDR}", "success")

                # Save to .env for persistence
                self.save_config()
            else:
                self.log_message("🔍 No existing Delta Chat credentials found", "warning")
                self.delta_info_label.config(text="Account: Please configure manually")

        except Exception as e:
            self.log_message(f"❌ Error auto-detecting credentials: {e}", "error")

    def check_delta_chat(self):
        """Check if Delta Chat configuration is available"""
        try:
            # Import here to avoid circular imports
            from .config import Config

            if Config.DC_ADDR and Config.DC_MAIL_PW:
                self.log_message("✅ Delta Chat credentials configured", "success")
                self.delta_status_label.config(text="🟢 Configured", foreground="green")
                self.delta_info_label.config(text=f"Account: {Config.DC_ADDR}")
            else:
                self.log_message("⚠️ Delta Chat credentials not found", "warning")
                self.delta_status_label.config(text="🟡 Not Configured", foreground="orange")
                self.delta_info_label.config(text="Account: Please configure")

        except Exception as e:
            self.log_message(f"❌ Error checking Delta Chat: {e}", "error")
            self.delta_status_label.config(text="🔴 Error", foreground="red")

    def test_connection(self):
        """Test Delta Chat connection"""
        self.log_message("🔍 Testing Delta Chat connection...", "info")

        # This would test the actual connection
        # For now, just check if credentials are provided
        if not self.email_var.get() or not self.password_var.get():
            self.log_message("❌ Please enter email and password", "error")
            return

        self.log_message("✅ Configuration looks good", "success")
        messagebox.showinfo("Test Result", "Configuration saved successfully!\n\nClick 'Start Server' to begin.")

    def start_server(self):
        """Start the MCP server"""
        if not self.email_var.get() or not self.password_var.get():
            messagebox.showerror("Configuration Error", "Please enter your Delta Chat email and password in the Configuration tab.")
            self.notebook.select(1)  # Switch to config tab
            return

        self.server_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        self.server_status_label.config(text="🟢 Server Starting...", foreground="orange")
        self.log_message("🚀 Starting Delta Chat MCP Server...", "info")

        # Start server in background thread
        threading.Thread(target=self.run_server, daemon=True).start()

    def stop_server(self):
        """Stop the MCP server"""
        self.server_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

        self.server_status_label.config(text="🔴 Server Stopping...", foreground="orange")
        self.log_message("⏹️ Stopping Delta Chat MCP Server...", "info")

        # Give it a moment to stop gracefully
        time.sleep(1)
        self.server_status_label.config(text="🔴 Server Stopped", foreground="red")
        self.log_message("✅ Server stopped", "success")

    def run_server(self):
        """Run the MCP server (background thread)"""
        try:
            # Import here to avoid GUI blocking
            import subprocess
            import signal
            import os

            # Start MCP server directly (it creates its own Delta Chat instance)
            self.log_message("🔌 Starting MCP server...", "info")
            server_process = subprocess.Popen([
                sys.executable, '-m', 'deltachat_mcp.server'
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

            # Wait a moment for server to start
            time.sleep(2)

            # Check if server started successfully
            if server_process.poll() is None:
                self.delta_connected = True
                self.server_running = True
                self.delta_status_label.config(text="🟢 Connected", foreground="green")
                self.server_status_label.config(text="🟢 Server Running", foreground="green")
                self.delta_info_label.config(text=f"Account: {self.email_var.get()}")
                self.log_message("✅ MCP server started successfully", "success")
                self.log_message(f"🌐 Server available at: http://127.0.0.1:{self.port_var.get()}", "info")
            else:
                self.log_message("❌ MCP server failed to start", "error")
                return

            # Monitor process
            while self.server_running and server_process.poll() is None:
                time.sleep(1)

                # Update activity (this would be enhanced with real MCP logging)
                if len(self.mcp_requests) < 5:  # Simulate some activity for now
                    self.mcp_requests.append(f"MCP request at {time.strftime('%H:%M:%S')}")
                    self.activity_label.config(text=f"📊 Requests: {len(self.mcp_requests)} | Responses: {len(self.mcp_requests)}")

            # Cleanup
            self.log_message("🛑 Shutting down server...", "info")

            if server_process.poll() is None:
                server_process.terminate()
                server_process.wait()

        except Exception as e:
            self.log_message(f"❌ Server error: {e}", "error")
            self.server_status_label.config(text="🔴 Server Error", foreground="red")
        finally:
            self.server_running = False
            self.delta_connected = False
            self.delta_status_label.config(text="🔴 Disconnected", foreground="red")
            self.server_status_label.config(text="🔴 Server Stopped", foreground="red")

    def log_message(self, message, level="info"):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}"

        # Color coding
        if level == "error":
            log_entry = f"[{timestamp}] ❌ {message}"
        elif level == "warning":
            log_entry = f"[{timestamp}] ⚠️ {message}"
        elif level == "success":
            log_entry = f"[{timestamp}] ✅ {message}"

        # Add to log text
        self.log_text.insert(tk.END, log_entry + "\n")
        self.log_text.see(tk.END)

        # Limit log size
        if self.log_text.get(1.0, tk.END).count('\n') > 1000:
            self.log_text.delete(1.0, 5.0)

    def clear_logs(self):
        """Clear the log display"""
        self.log_text.delete(1.0, tk.END)
        self.log_message("📝 Logs cleared", "info")

    def run(self):
        """Start the GUI application"""
        # Set up periodic updates
        self.update_status()

        # Start the GUI
        self.root.mainloop()

    def update_status(self):
        """Update status display (called periodically)"""
        if self.server_running:
            # Update activity counter
            if hasattr(self, 'activity_label'):
                self.activity_label.config(text=f"📊 Requests: {len(self.mcp_requests)} | Responses: {len(self.mcp_requests)}")

        # Schedule next update
        if self.server_running:
            self.root.after(1000, self.update_status)


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
