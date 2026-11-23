# deltachat-mcp

[![PyPI](https://img.shields.io/pypi/v/deltachat-mcp)](https://pypi.org/project/deltachat-mcp/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

An MCP server for managing Delta Chat conversations through a dedicated Delta
Chat account. The server starts a native Delta Chat core and offers four tools.

| Tool | Operation |
| --- | --- |
| `send_message` | Send text to an address or an existing chat ID |
| `list_chats` | List chats, their addresses where applicable, and unread counts |
| `get_messages` | Read the most recent 20 messages in a chat |
| `get_unread_count` | Count unread messages across chats |

Sending by address uses a unique matching contact with an available encryption
key. If the account requires encryption and the contact has no usable key,
scan the contact's SecureJoin QR code in Delta Chat before retrying. If more
than one key contact matches, choose the intended chat with `chat_id`.
Addresses without a key contact use classic mail only when the account allows it.
Sending to one of your own configured addresses opens Saved Messages.

## Install

With Python 3.11 or newer in an activated virtual environment, run
`pip install .` from the checkout. The `deltachat2[full]` dependency installs the
matching `deltachat-rpc-server` package. Keep the environment activated so the
shell can find the installed console script. The server first looks for the
native executable beside its Python interpreter, then on `PATH`.

## Start with a dedicated account

Set `DC_ACCOUNTS` to a private directory dedicated to this MCP server. It can
contain an existing configured MCP account. For a new test account, supply its
address and mail password through `DC_ADDR` and `DC_MAIL_PW`. On procreator,
create the corresponding KWallet folder and entry using KWallet Manager and
launch the command through `kwsecret`.

```bash
DC_ACCOUNTS="$PWD/dc-data/accounts-test" \
DC_ADDR="mcp-test@example.com" \
MCP_MODE=stdio \
kwsecret exec -e DC_MAIL_PW="Delta Chat/MCP test account" -- deltachat-mcp
```

For a configured account, set `DC_ACCOUNTS` and `MCP_MODE` and launch
`deltachat-mcp` directly. If `DC_ACCOUNTS` is unset, the path defaults to
`dc-data/accounts` relative to the working directory or `BASEDIR/accounts`
when `BASEDIR` is set. Use an account directory with a single owner. The server
uses an explicitly chosen account directory, and setup never searches existing
desktop profiles for credentials.

- **stdio** uses the program's standard input and output for MCP. Set
  `MCP_MODE=stdio` in the client and use an absolute account directory if the
  client launches the program from a different working directory.
- **HTTP** serves MCP Streamable HTTP at `http://127.0.0.1:8089/tool` by
  default. Set `MCP_MODE=http` and optionally change `MCP_PORT`. This interface
  grants local clients access to the account, including sending messages. Keep
  it on loopback and use stdio where local process isolation is needed.

The server supports MCP revision **2026-07-28** and the older initialize and
session flow through the MCP SDK. Versioning checked on **2026-11-22**.
[MCP versioning](https://modelcontextprotocol.io/specification/versioning)

## Configure by second-device transfer

With an empty dedicated accounts directory, the server can import an operator
supplied backup QR via `BACKUP_STRING`. Display **Add Second Device** on the
source Delta Chat client and leave it open during transfer. Treat the QR
contents as a credential. Where a ticket must be stored on procreator, keep it
in KWallet and inject it with `kwsecret exec -e BACKUP_STRING=FOLDER/ENTRY`.
Keep live tickets out of project files, command arguments, and diagnostic
output. Delta Chat Core classifies the QR and performs the transfer.

The server waits up to 120 seconds for the core to complete the backup
transfer. If it times out, check the receiving account's state before
restarting the server or retrying. The core may already have applied the backup.

The desktop GUI, discovery scripts, and portable and AppImage bundles come
from earlier versions. Use the package and command-line entry point above for
the current runtime.

## AI Prompt

Tell the assistant which Delta Chat account it is working with and ask it to
confirm sensitive actions before calling `send_message`. See the
[example prompt](examples/claude_prompt.md).

## Runtime map and diagnostics

`server.py` handles MCP transport and dispatch. `rpc.py` owns the native core
lifecycle and runs blocking RPCs in a worker. `tools.py` translates RPC results
into the four tool response shapes. The service writes startup, shutdown, and
tool outcome counters to stderr. Failed, cancelled, queued, and timed-out
operations have their own events. Logs omit credentials, chat content, and
raw RPC responses.

## Development

Install the source checkout with `pip install -e '.[dev]'` and run
`python -m pytest tests`. The isolated core tests use a temporary accounts
directory.

### Distribution and desktop tooling

The checkout retains the packaging scripts for
[portable tarballs](build-portable.sh), [AppImages](build-appimage.sh), and
[combined distributions](build-distribution.sh). The earlier desktop client
and integration entry points are in [deltachat_mcp_gui.py](deltachat_mcp_gui.py)
and [desktop-setup.sh](desktop-setup.sh). For command-line development,
[launch.sh](launch.sh) runs the MCP server with the supplied environment.

See [LICENSE](LICENSE) for the MIT license.
