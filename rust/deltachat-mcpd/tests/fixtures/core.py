#!/usr/bin/env python3
"""Native RPC wire fixture. Deliberately leaves the idle event poll pending."""

import json
import os
import sys
from collections import deque

pending_event = None
events = deque()


def respond(request_id, result):
    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": result}), flush=True)


def respond_to_event_poll():
    global pending_event
    if pending_event is not None and events:
        respond(pending_event, events.popleft())
        pending_event = None


def contact(contact_id, address):
    return {
        "id": contact_id,
        "address": address,
        "displayName": "Fixture sender",
        "isKeyContact": True,
        "isBlocked": False,
        "e2eeAvail": True,
    }


def chat(chat_id):
    return {
        "id": chat_id,
        "name": "Fixture chat",
        "chatType": "Single",
        "isSelfTalk": False,
        "isDeviceChat": False,
        "isContactRequest": False,
        "isMuted": False,
        "isEncrypted": chat_id == 12,
        "freshMessageCounter": 1,
        "contactIds": [10],
    }


def result_for(method, params):
    if method == "get_all_account_ids":
        return [1]
    if method == "get_account_info":
        return {"kind": "Configured"}
    if method in {"start_io", "stop_io"}:
        return None
    if method == "get_chatlist_entries":
        return [12] if params[1] == 2 else []
    if method in {"get_basic_chat_info", "get_full_chat_by_id"}:
        return chat(params[1])
    if method == "get_contact":
        return contact(10, "fixture@example.test")
    if method in {"get_message_ids", "get_fresh_msgs"}:
        return [42]
    if method == "get_message":
        return {
            "id": 42,
            "chatId": 12,
            "fromId": 10,
            "sender": contact(10, "fixture@example.test"),
            "timestamp": 1,
            "text": "real fixture input",
            "showPadlock": True,
            "isInfo": False,
        }
    if method == "get_fresh_msg_cnt":
        return 1
    if method == "check_email_validity":
        return "@" in params[0]
    if method == "lookup_contact_id_by_addr":
        return None
    if method == "get_contacts":
        address = params[2]
        if address == "ambiguous@example.test":
            return [contact(10, address), contact(11, address)]
        return [contact(10, address)] if address == "fixture@example.test" else []
    if method == "get_blocked_contacts":
        return []
    if method == "get_config":
        assert params[1] == "force_encryption"
        return "1"
    if method == "create_chat_by_contact_id":
        assert params[1] == 10
        return 12
    if method == "misc_send_text_message":
        if params[2] == "disconnect":
            os._exit(0)
        return 43
    if method == "marknoticed_chat":
        for account, message in [(2, 41), (1, 42)]:
            events.append({
                "contextId": account,
                "event": {"kind": "IncomingMsg", "chatId": 12, "msgId": message},
            })
        respond_to_event_poll()
        return None
    raise ValueError("Unexpected fixture method")


for line in sys.stdin:
    req = json.loads(line)
    if req["method"] == "get_next_event":
        assert pending_event is None
        pending_event = req["id"]
        respond_to_event_poll()
    else:
        respond(req["id"], result_for(req["method"], req["params"]))
