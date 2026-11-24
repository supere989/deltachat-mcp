"""Start the release daemon with a real Core and an offline test account."""

import argparse
import json
import os
from pathlib import Path
import secrets
import select
import socket
import subprocess
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

PROTOCOL = "2026-07-28"


def prepare_account(native: Path, accounts: Path) -> int:
    with subprocess.Popen(
        [native], env={**os.environ, "DC_ACCOUNTS_PATH": str(accounts)},
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
    ) as core:
        def rpc(request_id, method, params):
            request = json.dumps({
                "jsonrpc": "2.0", "id": request_id, "method": method, "params": params,
            })
            core.stdin.write(f"{request}\n".encode())
            core.stdin.flush()
            if not select.select([core.stdout], [], [], 10)[0]:
                raise TimeoutError(f"offline fixture RPC timed out: {method}")
            reply = json.loads(core.stdout.readline())
            if reply.get("id") != request_id or "result" not in reply:
                raise RuntimeError(f"offline fixture RPC failed: {method}")
            return reply["result"]

        try:
            aid = rpc(1, "add_account", [])
            rpc(2, "set_config", [aid, "configured_addr", "native-smoke@example.invalid"])
            # A configured address alone uses the offline fixture transport.
            if not rpc(3, "is_configured", [aid]):
                raise RuntimeError("offline fixture account did not configure")
            return aid
        finally:
            core.stdin.close()
            try:
                core.wait(timeout=5)
            except subprocess.TimeoutExpired:
                core.terminate()
                try:
                    core.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    core.kill()
                    core.wait(timeout=5)


def check_daemon(daemon: Path, native: Path, accounts: Path, account_id: int) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
    base = f"http://{host}:{port}"
    token = secrets.token_hex(32)
    auth = {"Authorization": f"Bearer {token}"}

    with subprocess.Popen([
        daemon, "--listen", f"{host}:{port}", "--rpc-bin", native,
        "--accounts-dir", accounts, "--account-id", str(account_id),
        "--token-env", "RUST_MCP_SMOKE_TOKEN",
    ], env={**os.environ, "RUST_MCP_SMOKE_TOKEN": token}) as process:
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("daemon exited before becoming ready")
                try:
                    with urlopen(Request(f"{base}/status", headers=auth), timeout=1) as response:
                        status = json.load(response)
                    if status["core"]["ready"] and status["core"]["native_pid"] > 0:
                        break
                except URLError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("real native Core never reported ready")

            name = "get_unread_count"
            body = json.dumps({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": name, "arguments": {}, "_meta": {
                    "io.modelcontextprotocol/protocolVersion": PROTOCOL,
                    "io.modelcontextprotocol/clientInfo": {"name": "native-smoke", "version": "1"},
                    "io.modelcontextprotocol/clientCapabilities": {},
                }},
            }).encode()
            headers = {
                **auth, "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json", "MCP-Protocol-Version": PROTOCOL,
                "Mcp-Method": "tools/call", "Mcp-Name": name,
            }
            with urlopen(Request(f"{base}/mcp", data=body, headers=headers), timeout=5) as response:
                if response.headers.get_content_type() == "text/event-stream":
                    records = (line.partition(b":")[2] for line in response if line.startswith(b"data:"))
                    reply = next(item for item in map(json.loads, records) if item.get("id") == 1)
                else:
                    reply = json.load(response)
            result = reply.get("result", {})
            if result.get("isError") or result.get("structuredContent", {}).get("unread_count") != 0:
                raise RuntimeError("real native MCP tool did not return an empty unread count")
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
                raise
        if process.returncode != 0:
            raise RuntimeError("daemon did not shut down cleanly")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("daemon", type=Path)
    parser.add_argument("native", type=Path)
    args = parser.parse_args()
    daemon, native = args.daemon.resolve(strict=True), args.native.resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="deltachat-mcp-native-smoke-") as tmp:
        accounts = Path(tmp) / "accounts"
        check_daemon(daemon, native, accounts, prepare_account(native, accounts))
    print("Real Delta Chat Core startup and authenticated MCP read passed")
