# deltachat-mcp

**Let AI send/receive encrypted messages via Delta Chat using Model Context Protocol (MCP)**

[![PyPI](https://img.shields.io/pypi/v/deltachat-mcp)](https://pypi.org/project/deltachat-mcp/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> **Standalone Delta Chat client** with MCP interface — privacy-first, E2EE, decentralized. **Compatible with latest MCP SDK v1.19.0**.

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
- 📝 **Live MCP Logging** - Monitor all AI interactions and requests
- ⚙️ **Configuration Management** - Change settings without editing files
- 🚀 **One-click Start/Stop** - Simple server control
- 🌐 **MCP Client Integration** - Ready-to-use connection settings

**Architecture:** Creates its own Delta Chat account - no existing Delta Chat installation required!

### Launch the GUI

```bash
# After setup, launch the desktop application
deltachat-gui

# Or from the portable bundle
./run.sh  # Choose GUI option
```

**Features:**
- ✅ **User-friendly interface** with tabs for Status, Configuration, and Logs
- ✅ **Real-time monitoring** of MCP requests and responses
- ✅ **Visual status indicators** for server and Delta Chat connections
- ✅ **Interactive configuration** with validation and testing
- ✅ **Desktop integration** - appears in your applications menu

---

## 🚀 Quick Start (One Command!)

```bash
# 1. Clone and setup in one command
git clone https://github.com/supere989/deltachat-mcp.git
cd deltachat-mcp
python configure.py
```

That's it! The setup script will:
- ✅ Configure your Delta Chat credentials
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

# 2. Copy config
cp .env.example .env
# Edit .env with your email + app password

# 3. Run MCP server (creates its own Delta Chat instance)
deltachat-mcp serve
```

**Note:** This creates its own Delta Chat account and doesn't require Delta Chat desktop to be installed.

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

**Features:** Desktop GUI + Command Line interfaces, automatic setup, no installation required!

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
deltachat-setup
deltachat-mcp serve
```

**Size:** Minimal | **Requirements:** Python environment

### 🔧 **Build from Source**

```bash
# Clone and setup
git clone https://github.com/supere989/deltachat-mcp.git
cd deltachat-mcp
python configure.py

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
