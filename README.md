# deltachat-mcp

**Let AI send/receive encrypted messages via Delta Chat using Model Context Protocol (MCP)**

[![PyPI](https://img.shields.io/pypi/v/deltachat-mcp)](https://pypi.org/project/deltachat-mcp/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> **Standalone Delta Chat client** with MCP interface — privacy-first, E2EE, decentralized. **Auto-detects your existing Delta Chat configuration!** **Compatible with latest MCP SDK v1.19.0**.

---

## Features

- Send messages to any email
- List chats & unread count
- Read recent messages
- **🖥️ Desktop GUI Application** - Real-time monitoring and configuration
- Works with **Claude Desktop**, **Cursor**, **Windsurf**, **mcp-client-app**
- Zero plaintext exposure (Autocrypt E2EE)

---

## 🖥️ **Desktop GUI Application (Recommended)**

The easiest way to use Delta Chat MCP Server! A beautiful desktop application with:

- 📊 **Real-time Status Monitoring** - See server and Delta Chat connection status
- 🔐 **Secure Configuration** - Easy setup with credential validation
- 🔍 **Auto-Detection** - Automatically finds your existing Delta Chat credentials
- 📝 **Live MCP Logging** - Monitor all AI interactions and requests
- ⚙️ **Configuration Management** - Change settings without editing files
- 🚀 **One-click Start/Stop** - Simple server control
- 🌐 **MCP Client Integration** - Ready-to-use connection settings

**Architecture:** Auto-detects existing Delta Chat configuration - seamless integration!

---

## 🔍 **Auto-Detection Feature**

The application automatically detects and uses your existing Delta Chat configuration:

### ✅ **What It Finds:**
- **Delta Chat databases** in standard locations (`~/.config/deltachat`, `~/.deltachat`, etc.)
- **Account credentials** (email, password, data directory)
- **Existing chat data** and contact information
- **Configuration settings** from your local Delta Chat client

### 🚀 **How It Works:**
1. **Scans** your system for Delta Chat databases
2. **Validates** database structure and credentials
3. **Auto-configures** the MCP server with your existing account
4. **Preserves** all your chat history and contacts
5. **Integrates** seamlessly with your current Delta Chat setup

### 📱 **Second Device Support:**
The application also supports registering as a **second device** using Delta Chat's backup string:

1. **On your primary device:** Settings → Add Second Device
2. **Copy the backup string** that starts with `DCBACKUP3:`
3. **Paste it in the GUI** or use during setup
4. **Automatic registration** as a second device with full sync

### 💡 **Benefits:**
- ✅ **Zero configuration** if you already use Delta Chat
- ✅ **Preserves chat history** and contacts
- ✅ **No duplicate accounts** or data
- ✅ **Seamless integration** with existing workflow
- ✅ **Multi-device support** with second device registration

---

## 🚀 Quick Start (One Command!)

```bash
# 1. Clone and setup in one command
git clone https://github.com/supere989/deltachat-mcp.git
cd deltachat-mcp
python configure.py
```

That's it! The setup script will:
- ✅ **Auto-detect existing Delta Chat credentials** from your local installation
- ✅ Install all dependencies
- ✅ Create Windsurf configuration
- ✅ Generate launcher script
- ✅ Set up desktop GUI application

**Then simply run:**
```bash
deltachat-gui  # Launch the desktop application!
```

---

## 🖥️ Daily Usage

**Desktop GUI (Recommended):**
```bash
deltachat-gui  # Beautiful desktop application
```

**Command Line:**
```bash
# Start the server (includes both Delta Chat and MCP)
./launch.sh

# Or use the installed commands
deltachat-mcp serve
deltachat-setup  # Reconfigure settings
deltachat-desktop  # Desktop integration
```

**From Portable Bundle:**
```bash
./run.sh  # Choose GUI or CLI interface
```

The setup script generates:
- **`.env`** - Your configuration
- **`launch.sh`** - Easy server launcher

---

## Manual Setup (Alternative)

```bash
# 1. Install
pip install deltachat-mcp

# 2. Copy config (auto-detects from existing Delta Chat)
cp .env.example .env
# Edit .env with your email + app password (if auto-detection fails)

# 3. Run MCP server (creates its own Delta Chat instance)
deltachat-mcp serve
```

**Note:** The application automatically detects and uses credentials from your existing Delta Chat installation!

Add to your MCP client:

```json
{
  "name": "deltachat",
  "url": "http://127.0.0.1:8089"
}
```

---

## 🖥️ Desktop Integration (Optional)

For easier access, run:

```bash
# Create desktop launcher and system integration
./desktop-setup.sh
```

This adds:
- 🖥️ **Desktop shortcut** in your applications menu
- ⚡ **System service** option (if supported)
- 🚀 **One-click startup** from your desktop environment

---

## 📦 One-Line Installation

```bash
# Install directly from GitHub (without cloning)
pip install git+https://github.com/supere989/deltachat-mcp.git
deltachat-setup
```

---

## AI Prompt

```text
Use `deltachat.send_message` to contact users. Always confirm sensitive actions.
```

---

## Development

```bash
pip install -e .[dev]
pytest
```

---

## 🚀 Deployment Options

### 📦 **Portable Bundle (Recommended)**
*Smallest and easiest - just download and run!*

```bash
# Download and extract
wget https://github.com/supere989/deltachat-mcp/releases/download/v0.2.0/deltachat-mcp-portable-0.2.0.tar.gz
tar -xzf deltachat-mcp-portable-0.2.0.tar.gz
cd deltachat-mcp-portable-0.2.0

# First-time setup
python configure.py

# Start server
./run.sh
```

**Size:** ~8.6KB | **Requirements:** Python 3.10+ only

**Features:** Desktop GUI + Command Line interfaces, **auto-detects Delta Chat credentials**, no installation required!

### 🖥️ **AppImage (Advanced)**
*Self-contained application for any Linux distribution*

```bash
# Download AppImage
wget https://github.com/supere989/deltachat-mcp/releases/download/v0.2.0/deltachat-mcp-0.2.0-x86_64.AppImage

# Make executable and run
chmod +x deltachat-mcp-0.2.0-x86_64.AppImage
./deltachat-mcp-0.2.0-x86_64.AppImage
```

**Size:** ~50MB | **Requirements:** None (self-contained)

### 🐍 **PyPI Installation**
*Traditional Python package installation*

```bash
pip install deltachat-mcp
deltachat-setup  # Auto-detects existing Delta Chat credentials
deltachat-gui    # Launch GUI
```

**Size:** Minimal | **Requirements:** Python environment

### 🔧 **Build from Source**

```bash
# Clone and setup
git clone https://github.com/supere989/deltachat-mcp.git
cd deltachat-mcp
python configure.py  # Auto-detects Delta Chat credentials

# Or build distributions
./build-distribution.sh  # Creates all formats
./build-portable.sh     # Creates portable tarball only
```

### 🔧 **Build Scripts Available**

- **`./configure.py`** - Interactive setup wizard
- **`./deltachat_mcp_gui.py`** - Desktop GUI application
- **`./build-portable.sh`** - Create portable tarball
- **`./build-appimage.sh`** - Create AppImage (requires PyInstaller)
- **`./build-distribution.sh`** - Create all distribution formats
- **`./launch.sh`** - Development server launcher

---

## License
