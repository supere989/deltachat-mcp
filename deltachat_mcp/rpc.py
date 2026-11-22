"""Own one Delta Chat core process and serialize its operations off the MCP loop."""

import logging
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from threading import Event

import anyio
from deltachat2 import EnteredLoginParam, IOTransport, JsonRpcError, QrBackup2, Rpc

LOG = logging.getLogger(__name__)
RPC_TIMEOUT = 15
SETUP_TIMEOUT = 120
SETUP_METHODS = {"add_or_update_transport", "get_backup"}


class CoreError(RuntimeError):
    """A user-facing core error whose message contains no RPC payload."""


class PendingResponse:
    def __init__(self):
        self.ready = Event()
        self.value = None

    def set(self, value):
        self.value = value
        self.ready.set()


class CoreTransport(IOTransport):
    """Bound waits around the SDK's request queue so a dead core cannot hang MCP."""

    def __init__(self, accounts_dir: Path, audit):
        env = os.environ.copy()
        env.pop("DC_MAIL_PW", None)
        env.pop("BACKUP_STRING", None)
        binary = "deltachat-rpc-server.exe" if os.name == "nt" else "deltachat-rpc-server"
        installed_binary = Path(sys.executable).with_name(binary)
        if installed_binary.is_file() and os.access(installed_binary, os.X_OK):
            binary = str(installed_binary)
        super().__init__(
            accounts_dir=str(accounts_dir),
            rpc_executable=binary,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        self.audit = audit
        self.failed = False

    def call(self, method, *args):
        if self.failed or self.process.poll() is not None:
            self.failed = True
            self.audit("core_unavailable")
            raise CoreError("Delta Chat core is unavailable")
        request_id = next(self.id_iterator)
        pending = self.pending_results[request_id] = PendingResponse()
        deadline = time.monotonic() + (SETUP_TIMEOUT if method in SETUP_METHODS else RPC_TIMEOUT)
        self.request_queue.put({
            "jsonrpc": "2.0",
            "id": request_id,
            "method": method,
            "params": args,
        })

        while not pending.ready.wait(0.1):
            if self.process.poll() is not None or not (
                self.reader_thread.is_alive() and self.writer_thread.is_alive()
            ):
                self.failed = True
                self.audit("core_disconnected")
                raise CoreError("Delta Chat core disconnected")
            if time.monotonic() >= deadline:
                # A mutating call may already have taken effect. Fail closed and
                # require a new core process before accepting another operation.
                self.failed = True
                self.audit("core_timeout")
                raise CoreError("Delta Chat core timed out. Restart the server before retrying.")

        response = pending.value
        if "error" in response:
            raise JsonRpcError("Delta Chat core rejected the operation")
        return response.get("result")

    def close(self):
        try:
            if not self.failed and self.process.poll() is None:
                try:
                    self.call("stop_io_for_all_accounts")
                except (JsonRpcError, CoreError):
                    self.audit("core_stop_failed")
        finally:
            self.request_queue.put(None)
            if self.failed and self.process.poll() is None:
                self.process.terminate()
            self.writer_thread.join(timeout=2)
            if not self.writer_thread.is_alive() and self.process.stdin:
                self.process.stdin.close()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.audit("core_force_stop")
                self.process.kill()
                self.process.wait(timeout=3)
            self.reader_thread.join(timeout=2)
            self.writer_thread.join(timeout=2)
            if self.reader_thread.is_alive() or self.writer_thread.is_alive():
                self.audit("core_thread_pending")
            elif self.process.stdout:
                self.process.stdout.close()
            self.pending_results.clear()


class DeltaChatRPC:
    def __init__(self, accounts_dir: Path, address=None, password=None, backup=None):
        self.accounts_dir = accounts_dir
        self.address = address
        self.password = password
        self.backup = backup
        self._transport = None
        self._rpc = None
        self._account_id = None
        self._lock = anyio.Lock()
        self.counts = Counter()

    def audit(self, outcome: str):
        self.counts[outcome] += 1
        LOG.info("%s count=%d", outcome, self.counts[outcome])

    def _start(self):
        accounts_dir = self.accounts_dir.resolve()
        accounts_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        transport = CoreTransport(accounts_dir, self.audit)
        # The SDK can otherwise log malformed responses including RPC input.
        transport.logger.disabled = True
        try:
            transport.start()
        except OSError:
            raise CoreError("Could not start deltachat-rpc-server") from None
        self._transport = transport
        rpc = Rpc(transport)

        account_ids = rpc.get_all_account_ids()
        if len(account_ids) > 1:
            raise CoreError("Use a dedicated directory containing at most one Delta Chat account")
        if self.backup and (self.address or self.password):
            raise CoreError("Select one account configuration method")
        if not account_ids and not (self.backup or (self.address and self.password)):
            raise CoreError("Provide DC_ADDR and DC_MAIL_PW, BACKUP_STRING, or a configured account directory")
        account_id = account_ids[0] if account_ids else rpc.add_account()

        configured = rpc.is_configured(account_id)
        if configured and self.backup:
            raise CoreError("Use an unconfigured account directory for a second-device transfer")
        if configured and self.address:
            configured_address = rpc.get_account_info(account_id).addr
            if not configured_address or configured_address.casefold() != self.address.casefold():
                raise CoreError("DC_ADDR does not match the configured account")
        if not configured:
            if self.backup:
                if not isinstance(rpc.check_qr(account_id, self.backup), QrBackup2):
                    raise CoreError("BACKUP_STRING must be an Add Second Device QR")
                rpc.get_backup(account_id, self.backup)
            elif self.address and self.password:
                rpc.add_or_update_transport(
                    account_id, EnteredLoginParam(addr=self.address, password=self.password)
                )
            else:
                raise CoreError("The selected account directory is not configured")

        if not rpc.is_configured(account_id):
            raise CoreError("Delta Chat account configuration did not complete")
        rpc.start_io(account_id)
        self._rpc = rpc
        self._account_id = account_id

    async def start(self):
        self.audit("startup_requested")
        try:
            await anyio.to_thread.run_sync(self._start)
        except (JsonRpcError, OSError):
            self.audit("startup_failed")
            raise CoreError("Could not open or configure the Delta Chat account") from None
        except BaseException:
            self.audit("startup_failed")
            raise
        finally:
            self.password = None
            self.backup = None
        self.audit("startup_succeeded")

    async def run(self, operation, params):
        if self._lock.locked():
            self.audit("tool_queued")
        async with self._lock:
            if self._rpc is None:
                raise CoreError("Delta Chat core is unavailable")
            return await anyio.to_thread.run_sync(operation, self._rpc, self._account_id, params)

    async def close(self):
        with anyio.CancelScope(shield=True):
            async with self._lock:
                if self._transport is None:
                    return
                self._rpc = None
                self._account_id = None
                transport, self._transport = self._transport, None
                try:
                    await anyio.to_thread.run_sync(transport.close)
                except (OSError, subprocess.TimeoutExpired):
                    self.audit("shutdown_failed")
                else:
                    self.audit("shutdown_succeeded")
