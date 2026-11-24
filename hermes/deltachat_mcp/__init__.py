"""Register Delta Chat MCP transport in an isolated Hermes installation."""

import os

from .settings import Settings


def _configured(config=None) -> bool:
    try:
        Settings.load(config)
    except (OSError, ValueError):
        return False
    return True


def _enablement() -> dict | None:
    if not _configured():
        return None
    return {"mcp_url": os.environ["DELTACHAT_MCP_URL"]}


def _adapter(config):
    from .adapter import McpDeltaChatAdapter

    return McpDeltaChatAdapter(config, Settings.load(config))


def register(ctx) -> None:
    ctx.register_platform(
        name="deltachat",
        label="Delta Chat (MCP)",
        adapter_factory=_adapter,
        check_fn=_configured,
        validate_config=_configured,
        is_connected=_configured,
        required_env=["DELTACHAT_MCP_URL"],
        install_hint="Install the pinned Hermes MCP SDK from the release manifest.",
        env_enablement_fn=_enablement,
        allowed_users_env="DELTACHAT_ALLOWED_USERS",
        max_message_length=15000,
        emoji="📧",
        pii_safe=False,
        platform_hint="Use plain text in this encrypted Delta Chat conversation.",
    )
