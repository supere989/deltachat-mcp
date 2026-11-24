"""Hermes platform transport using a local Delta Chat MCP daemon."""

import asyncio
from collections import Counter
from contextlib import contextmanager, suppress
import json
import logging
from pathlib import Path
import sqlite3

import httpx2
from gateway.config import Platform
from gateway.platforms.base import BasePlatformAdapter, MessageEvent, MessageType, ProcessingOutcome, SendResult
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.client.subscriptions import ResourceUpdated
from mcp.types import TextResourceContents

from .settings import Settings

PROTOCOL = "2026-07-28"
INCOMING = "dc://events/incoming"
MAX_MESSAGE_LENGTH = 15000
logger = logging.getLogger(__name__)


class DeliveryLedger:
    """Persist per-message results in an account-specific, private directory."""

    def __init__(self, state_dir: Path):
        self.path = state_dir / "adapter-delivery.sqlite"

    def initialize(self) -> None:
        with self._db() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS delivery ("
                "chat_id INTEGER, message_id INTEGER, result TEXT NOT NULL, "
                "PRIMARY KEY (chat_id, message_id))"
            )

    @contextmanager
    def _db(self):
        # Settings.load validates ownership and permissions before opening SQLite.
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def claim(self, chat_id: int, message_id: int) -> str | None:
        with self._db() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO delivery VALUES (?, ?, 'pending')",
                (chat_id, message_id),
            ).rowcount
            if inserted == 1:
                return None
            return db.execute(
                "SELECT result FROM delivery WHERE chat_id = ? AND message_id = ?",
                (chat_id, message_id),
            ).fetchone()[0]

    def finish(self, chat_id: int, message_id: int, result: str) -> None:
        with self._db() as db:
            db.execute(
                "UPDATE delivery SET result = ? WHERE chat_id = ? AND message_id = ?",
                (result, chat_id, message_id),
            )


class McpDeltaChatAdapter(BasePlatformAdapter):
    MAX_MESSAGE_LENGTH = MAX_MESSAGE_LENGTH

    def __init__(self, config, settings: Settings):
        super().__init__(config=config, platform=Platform("deltachat"))
        self._settings = settings
        self._ledger = DeliveryLedger(settings.state_dir)
        self._chat_name: str | None = None
        self._verified_peer = False
        self._client: Client | None = None
        self._worker: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._completion: dict[str, asyncio.Future] = {}
        self._seen: dict[tuple[int, int], None] = {}
        self._gap: int | None = None
        self.mcp_counts: Counter[str] = Counter()

    def _record(self, reason: str, *, chat_id=None, message_id=None) -> None:
        self.mcp_counts[reason] += 1
        logger.info(
            "deltachat MCP decision=%s count=%d chat_id=%s message_id=%s",
            reason, self.mcp_counts[reason], chat_id, message_id,
        )

    async def connect(self, *, is_reconnect: bool = False) -> bool:
        if self._worker is None:
            await asyncio.to_thread(self._ledger.initialize)
            self._worker = asyncio.create_task(self._run(), name="deltachat-mcp-client")
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=30)
        except TimeoutError:
            self._record("connect_timeout")
            await self.disconnect()
            return False
        return True

    async def disconnect(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._worker
            self._worker = None
        await self.cancel_background_tasks()
        self._mark_disconnected()

    async def _run(self) -> None:
        delay = 1
        async with httpx2.AsyncClient(
            headers={"Authorization": f"Bearer {self._settings.token}"},
            trust_env=False,
            follow_redirects=False,
            timeout=httpx2.Timeout(25, connect=5, read=90),
        ) as http:
            while True:
                try:
                    transport = streamable_http_client(self._settings.url, http_client=http)
                    async with Client(transport, mode=PROTOCOL) as client:
                        self._client = client
                        async with client.listen(resource_subscriptions=[INCOMING]) as sub:
                            if INCOMING not in (sub.honored.resource_subscriptions or []):
                                raise RuntimeError("MCP subscription did not accept the incoming resource")
                            self._record("subscription_acknowledged")
                            self._mark_connected()
                            self._ready.set()
                            await self._refresh(client, catch_up=True)
                            delay = 1
                            async for event in sub:
                                if isinstance(event, ResourceUpdated) and str(event.uri) == INCOMING:
                                    self._record("message_event")
                                    await self._refresh(client, catch_up=False)
                            self._record("subscription_closed")
                except Exception as exc:
                    # HTTP and SDK errors can include headers or payloads. Record the class only.
                    self._record(f"subscription_error_{type(exc).__name__}")
                finally:
                    self._client = None
                    self._ready.clear()
                    self._mark_disconnected()
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def _refresh(self, client, *, catch_up: bool) -> None:
        resource = await asyncio.wait_for(client.read_resource(INCOMING), timeout=15)
        item, = resource.contents
        if not isinstance(item, TextResourceContents) or str(item.uri) != INCOMING:
            raise ValueError("unexpected incoming message resource")
        snapshot = json.loads(item.text)
        gap = snapshot["gap"]
        if self._gap is not None and gap != self._gap:
            self._record("incoming_event_gap")
            catch_up = True
        self._gap = gap
        messages = {(msg["chat_id"], msg["id"]): msg for msg in snapshot["messages"]}
        if catch_up:
            self._record("catch_up")
            digest = await asyncio.wait_for(client.call_tool("get_unread_digest", {}), timeout=15)
            if digest.is_error or not isinstance(digest.structured_content, dict):
                raise RuntimeError("unread digest failed")
            for chat in digest.structured_content["chats"]:
                for msg in chat["messages"]:
                    messages.setdefault((chat["chat_id"], msg["id"]), msg)
        for msg in sorted(messages.values(), key=lambda value: value["id"]):
            await self._dispatch(msg)

    async def _dispatch(self, msg: dict) -> None:
        chat_id, message_id = msg["chat_id"], msg["id"]
        if (chat_id, message_id) in self._seen:
            return
        prior = await asyncio.to_thread(self._ledger.claim, chat_id, message_id)
        if prior is not None:
            if prior in {"pending", "uncertain"}:
                self._record("ambiguous_prior_delivery", chat_id=chat_id, message_id=message_id)
            self._remember(chat_id, message_id)
            return

        decision = "uncertain"
        try:
            chat_type = str(msg.get("chat_type")).casefold()
            sender = msg.get("sender_addr") or ""
            if msg.get("is_info") or msg.get("is_outgoing"):
                decision = "self_or_info"
            elif (
                chat_id != self._settings.peer_chat_id
                or chat_type not in {"single", "100", "dm"}
                or sender.casefold() != self._settings.peer
                or msg.get("is_encrypted") is not True
                or msg.get("is_contact_request") is not False
            ):
                decision = "outside_accepted_peer"
            elif not (msg.get("text") or "").strip():
                decision = "empty"
            else:
                decision = await self._handle_incoming(msg, sender)
        except TimeoutError:
            self._record("handler_timeout", chat_id=chat_id, message_id=message_id)
        finally:
            self._completion.pop(str(message_id), None)
            await asyncio.to_thread(self._ledger.finish, chat_id, message_id, decision)
            self._remember(chat_id, message_id)
            self._record(decision, chat_id=chat_id, message_id=message_id)

    async def _handle_incoming(self, msg: dict, sender: str) -> str:
        chat_id, message_id = msg["chat_id"], msg["id"]
        if self._settings.help_only and msg["text"].strip() != "/help":
            return "help_only_filtered"
        self._chat_name = msg.get("chat_name")
        self._verified_peer = True
        event = MessageEvent(
            text=msg["text"],
            message_type=MessageType.TEXT,
            source=self.build_source(
                chat_id=chat_id,
                chat_name=self._chat_name,
                chat_type="dm",
                user_id=sender,
                user_name=msg.get("from"),
            ),
            message_id=str(message_id),
        )
        self._record("dispatch", chat_id=chat_id, message_id=message_id)
        done = self._completion[event.message_id] = asyncio.get_running_loop().create_future()
        await self.handle_message(event)
        if not event._gateway_accepted and not done.done():
            # Inline controls and gateway early returns do not produce a lifecycle
            # outcome. Audit them and never automatically replay an ambiguous send.
            return "uncertain"
        outcome = await asyncio.wait_for(done, timeout=45)
        return "complete" if outcome is ProcessingOutcome.SUCCESS else "uncertain"

    def _remember(self, chat_id: int, message_id: int) -> None:
        self._seen[(chat_id, message_id)] = None
        if len(self._seen) > 2048:
            self._seen.pop(next(iter(self._seen)))

    async def on_processing_complete(self, event, outcome) -> None:
        done = self._completion.get(event.message_id)
        if done is not None and not done.done():
            done.set_result(outcome)

    async def _send_with_retry(self, chat_id, content, reply_to=None, metadata=None, **kwargs):
        # A timeout can follow a successful native queue insert. Replays of
        # tools/call and Hermes' formatting fallback could both duplicate it.
        return await self.send(chat_id, content, reply_to=reply_to, metadata=metadata)

    async def get_chat_info(self, chat_id: str) -> dict:
        name = self._chat_name if str(chat_id) == str(self._settings.peer_chat_id) else None
        return {"name": name or chat_id, "type": "dm", "chat_id": chat_id}

    async def send(self, chat_id: str, content: str, reply_to=None, metadata=None) -> SendResult:
        if (metadata or {}).get("media_files"):
            return SendResult(success=False, error="Delta Chat MCP supports text only")
        client = self._client
        if client is None or not content or not content.strip():
            return SendResult(success=False, error="MCP client unavailable or empty message")
        if len(content) > self.MAX_MESSAGE_LENGTH:
            return SendResult(success=False, error="Delta Chat MCP message exceeds the size limit")
        target = self._settings.peer_chat_id
        if str(chat_id) != str(target):
            return SendResult(success=False, error="chat is outside the authorized peer conversation")
        if not self._verified_peer:
            return SendResult(success=False, error="no inbound message has verified this peer in the gateway")

        self._record("send_attempt", chat_id=target)
        try:
            result = await asyncio.wait_for(client.call_tool("send_message", {
                "chat_id": target,
                "text": content,
                "require_encryption": True,
            }), timeout=25)
            if result.is_error or not isinstance(result.structured_content, dict):
                raise RuntimeError("MCP send failed")
            message_id = result.structured_content["message_id"]
            if type(message_id) is not int or message_id <= 0:
                raise ValueError("invalid message ID in MCP send response")
        except Exception:
            self._record("send_unconfirmed", chat_id=target)
            return SendResult(success=False, error="MCP send was not confirmed")

        self._record("send_queued", chat_id=target, message_id=message_id)
        return SendResult(success=True, message_id=str(message_id))
