# Running the Delta Chat MCP release

This release runs the Rust MCP daemon and a dedicated Hermes gateway instance.
The daemon supervises the native Delta Chat Core process that exclusively opens
the account. Hermes connects to the daemon over authenticated loopback HTTP.

```text
Delta Chat peer ↔ native Core ↔ Rust MCP daemon ↔ Hermes Delta Chat plugin ↔ Hermes gateway
```

The MCP implementation targets `2026-07-28` and retains the older
initialize-based HTTP flow. The current protocol revision was checked on
2026-11-23. [MCP versioning](https://modelcontextprotocol.io/specification/versioning)

## Build and promote a release

After CI passes and the changes land on `main`, tag that commit as
`deltachat-mcpd-v<version>` using the version in `rust/deltachat-mcpd/Cargo.toml`.
CI runs Python, Hermes adapter and Rust checks. The publish job verifies that
the tag points to a commit in `main` history and publishes the archive already
tested with its bundled native Core. Download both release assets and verify
the SHA-256 before extracting. Keep the checksum and `release.json` as the
deployment record. The manifest identifies the tag, commit, compiler, protocol,
native Core input and the hashes of packaged files.

## Prepare an isolated instance

Examples use the systemd user instance name `staging`. Create the instance's
configuration and state directories with mode `0700`. These paths assume the
default systemd user state root, `~/.local/state`.

| Purpose | Path |
| --- | --- |
| Release archive contents | `~/.local/share/deltachat-mcpd/staging/releases/<tag>/` |
| Selected release | `~/.local/share/deltachat-mcpd/staging/current` symlink |
| Config files | `~/.config/deltachat-mcpd/staging/daemon.env` and `gateway.env` |
| Staging account | `~/.local/state/deltachat-mcpd/staging/accounts/` |
| Staging gateway profile | `~/.local/state/deltachat-mcpd/staging/hermes/` |
| Adapter delivery ledger | `~/.local/state/deltachat-mcpd/staging/adapter/` |

```sh
sha256sum -c deltachat-mcpd-linux-x86_64.tar.gz.sha256
tar -xzf deltachat-mcpd-linux-x86_64.tar.gz -C "$release_directory"
```

Prepare exactly one configured account in the instance's `accounts` directory
using a compatible native Core. Confirm the account ID. Stop any previous
staging account owner and check that the kernel account lock is free before
copying or transferring its data. Keep a consistent backup of staging state.

Prepare a Hermes installation with the compatible Hermes plugin registration
API and MCP SDK `2.0.0`. Copy the bundled `hermes/deltachat_mcp/` directory into
the staging profile at `hermes/plugins/platforms/deltachat/`. Enable
`platforms/deltachat` under `plugins.enabled` and set
`gateway.multiplex_profiles: false` in the private Hermes profile configuration.
Keep the `deltachat` platform name for routing, and verify that the profile
loader selects the packaged plugin as its one Delta Chat registration. Leave
unrelated transports disabled. The launcher gives the normal
`hermes gateway run` entry point its own home and gateway lock directory.

`daemon.env` holds the instance bind, native account ID and credential name.
Use site-specific values for the bind port and account ID.

```ini
DELTACHAT_MCP_LISTEN=127.0.0.1:19228
DELTACHAT_MCP_ACCOUNT_ID=1
DELTACHAT_MCP_KEY_DESCRIPTION=example-deltachat-staging-bearer
```

`gateway.env` holds the entry point and authorized staging peer settings. Pin
the peer's verified address and the accepted chat ID from this account.

```ini
HERMES_PYTHON=/absolute/path/to/hermes/venv/bin/python
HERMES_SOURCE=/absolute/path/to/hermes/source
DELTACHAT_MCP_URL=http://127.0.0.1:19228/mcp
DELTACHAT_MCP_PEER_ADDR=peer@example.invalid
DELTACHAT_ALLOWED_USERS=peer@example.invalid
DELTACHAT_MCP_PEER_CHAT_ID=11
DELTACHAT_MCP_HELP_ONLY=1
DELTACHAT_MCP_KEY_DESCRIPTION=example-deltachat-staging-bearer
```

The launcher reads a credential named `deltachat-bearer` from the service's
systemd credential directory when provisioned. On a user manager with supported
encrypted credentials, install an instance drop-in using
`LoadCredentialEncrypted=deltachat-bearer:/path/to/encrypted/credential` for both
units. With a kernel keyring, provision the same bearer as a `user` key in `@u`
and reference only the key name in both `.env` files. That key must remain
available for any service restart. A kernel key alone does not supply the
bearer after reboot. Provision a persistent credential before accepting
unattended boot as a deployment requirement. Store no bearer, backup ticket,
or mail password in a unit, environment file or release asset.

## Start and verify

Install `systemd/deltachat-mcpd@.service` and
`systemd/hermes-deltachat-mcp@.service` in `~/.config/systemd/user/` and point
the `current` symlink at the verified release. The gateway service pulls in the
daemon. Enable the gateway at boot only after validating its credential source.

```sh
systemctl --user daemon-reload
systemctl --user start hermes-deltachat-mcp@staging.service
systemctl --user restart deltachat-mcpd@staging.service hermes-deltachat-mcp@staging.service
```

Check authenticated `/status` for `core.ready`, `core.native_pid` and an open
listener. On the host, match the staging `accounts.lock` by device and inode to
its kernel write-lock holder. That holder must be the daemon's native Core
child. Confirm the Hermes process has connected to MCP and has no native Core
child. Ask the controlled peer to send `/help` after subscription readiness.
Verify the encrypted response in that peer's client. Record the release hash,
unit identity, lock owner, message receipt and the before/after result.

## Upgrade, diagnose and recover

Retain the previous verified release and a separately protected staging state
backup. Stop the gateway and daemon, verify lock release, then change `current`
to the new matching release and start both units. Check that the Hermes plugin
files and unit definitions match that release. Restore the prior symlink and
profile plugin together if startup or delivery fails. Confirm native Core
account format compatibility before reopening a profile with an older version.

Use systemd's unit state and the authenticated `/status` counters to observe
native calls, failed calls, timeouts, events, missed notifications and tool
outcomes. The gateway journals subscription, routing, dispatch and ambiguous
send decisions using chat and message IDs. An ambiguous send requires peer or
native history reconciliation before retry. Event recovery combines the
in-memory event window with a fresh unread digest and a persistent adapter
ledger. Exercise disconnect and catch-up with the controlled peer. Record
unread-digest limits for muted and unaccepted chats. Routing decisions are
deterministic.
