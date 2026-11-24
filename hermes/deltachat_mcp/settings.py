"""Settings shared by plugin discovery and adapter construction."""

from dataclasses import dataclass, field
import os
from pathlib import Path
import stat
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    url: str
    state_dir: Path
    peer: str = field(repr=False)
    peer_chat_id: int
    token: str = field(repr=False)
    help_only: bool

    @classmethod
    def load(cls, config=None):
        extra = getattr(config, "extra", None) or {}
        if extra.get("accounts_dir") or os.environ.get("DELTACHAT_ACCOUNTS_DIR"):
            raise ValueError("Delta Chat MCP mode cannot open a native account directory")

        url = os.environ.get("DELTACHAT_MCP_URL", "")
        endpoint = urlsplit(url)
        if (
            endpoint.scheme != "http"
            or endpoint.hostname not in {"127.0.0.1", "::1"}
            or not endpoint.port
            or endpoint.username is not None
            or endpoint.password is not None
            or endpoint.path != "/mcp"
            or endpoint.query
            or endpoint.fragment
        ):
            raise ValueError("Delta Chat MCP requires an explicit loopback /mcp URL")

        state_dir = Path(os.environ.get("DELTACHAT_MCP_STATE_DIR", ""))
        if not state_dir.is_absolute():
            raise ValueError("DELTACHAT_MCP_STATE_DIR must be an absolute path")
        metadata = state_dir.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_uid != os.getuid()
            or stat.S_IMODE(metadata.st_mode) != 0o700
        ):
            raise ValueError("Delta Chat MCP state directory must be private and owned by the gateway")

        peer = os.environ.get("DELTACHAT_MCP_PEER_ADDR", "").strip().casefold()
        allowed = os.environ.get("DELTACHAT_ALLOWED_USERS", "").strip().casefold()
        if not peer or allowed != peer or any(c.isspace() or c == "," for c in peer):
            raise ValueError("Set the same single peer in DELTACHAT_MCP_PEER_ADDR and DELTACHAT_ALLOWED_USERS")
        peer_chat_id = os.environ.get("DELTACHAT_MCP_PEER_CHAT_ID", "")
        if (
            not peer_chat_id.isascii()
            or not peer_chat_id.isdecimal()
            or len(peer_chat_id) > 10
            or not 1 <= int(peer_chat_id) <= 2**32 - 1
        ):
            raise ValueError("DELTACHAT_MCP_PEER_CHAT_ID must identify the accepted peer chat")

        token_file = os.environ.get("DELTACHAT_MCP_TOKEN_FILE")
        token = Path(token_file).read_text(encoding="ascii").strip() if token_file else (
            os.environ.get("DELTACHAT_MCP_TOKEN", "")
        )
        if len(token) < 32 or any(not 33 <= ord(c) <= 126 for c in token):
            raise ValueError("Delta Chat MCP bearer credential is missing or invalid")
        return cls(
            url, state_dir, peer, int(peer_chat_id), token,
            os.environ.get("DELTACHAT_MCP_HELP_ONLY") == "1",
        )
