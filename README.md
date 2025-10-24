# deltachat-mcp

**Let AI send/receive encrypted messages via Delta Chat using Model Context Protocol (MCP)**

[![PyPI](https://img.shields.io/pypi/v/deltachat-mcp)](https://pypi.org/project/deltachat-mcp/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

> First MCP server for **Delta Chat** — privacy-first, E2EE, decentralized. **Compatible with latest MCP SDK v1.19.0**.

---

## Features

- Send messages to any email
- List chats & unread count
- Read recent messages
- Works with **Claude Desktop**, **Cursor**, **Windsurf**, **mcp-client-app**
- Zero plaintext exposure (Autocrypt E2EE)

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

---

## 🖥️ Daily Usage

After setup, simply run:

```bash
# Start the server (includes both Delta Chat and MCP)
./launch.sh

# Or use the installed command
deltachat-mcp serve
```

The setup script generates:
- **`.env`** - Your configuration
- **`launch.sh`** - Easy server launcher
- **`windsurf-config.json`** - Ready-to-use Windsurf config

---

## Manual Setup (Alternative)

```bash
# 1. Install
pip install deltachat-mcp

# 2. Copy config
cp .env.example .env
# Edit .env with your email + app password

# 3. Start Delta Chat RPC server
deltachat-rpc-server --addr $DC_ADDR --mail_pw $DC_MAIL_PW &

# 4. Run MCP server
deltachat-mcp serve
```

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

**Size:** ~7KB | **Requirements:** Python 3 + Delta Chat RPC server

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
- **`./build-portable.sh`** - Create portable tarball
- **`./build-appimage.sh`** - Create AppImage (requires PyInstaller)
- **`./build-distribution.sh`** - Create all distribution formats
- **`./launch.sh`** - Development server launcher

---

## License
