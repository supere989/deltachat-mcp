# deltachat_mcp/tools.py
from deltatachat2 import Account
from typing import List, Dict
from .rpc import DeltaChatRPC

async def send_message(params: dict) -> dict:
    account: Account = DeltaChatRPC().get_account()
    addr = params.get("addr")
    chat_id = params.get("chat_id")
    text = params["text"]

    if not text:
        raise ValueError("text is required")

    if chat_id:
        chat = await account.get_chat_by_id(int(chat_id))
    elif addr:
        contact = await account.create_contact(addr=addr)
        chat = await account.create_chat(contact=contact)
    else:
        raise ValueError("Need addr or chat_id")

    msg = await chat.send_text(text)
    return {"message_id": msg.id, "chat_id": chat.id, "text": text}

async def list_chats(_: dict) -> dict:
    account: Account = DeltaChatRPC().get_account()
    chats = await account.get_chats()
    return {
        "chats": [
            {
                "id": c.id,
                "name": c.name or c.addr or "Unnamed",
                "addr": c.addr,
                "is_group": c.is_group(),
                "unread_count": c.get_unread_message_count()
            }
            for c in chats
            if not c.is_self_talk()
        ]
    }

async def get_messages(params: dict) -> dict:
    account: Account = DeltaChatRPC().get_account()
    chat_id = params.get("chat_id")
    if not chat_id:
        raise ValueError("chat_id required")
    chat = await account.get_chat_by_id(int(chat_id))
    msgs = await chat.get_messages()
    return {
        "messages": [
            {
                "id": m.id,
                "from": m.sender.addr,
                "text": m.text,
                "timestamp": m.timestamp,
                "is_outgoing": m.is_outgoing,
                "is_encrypted": m.is_encrypted
            }
            for m in msgs[-20:]
        ]
    }

async def get_unread_count(_: dict) -> dict:
    account: Account = DeltaChatRPC().get_account()
    chats = await account.get_chats()
    total = sum(c.get_unread_message_count() for c in chats)
    return {"unread_count": total}
