"""Tool operations against the ID-based Delta Chat core RPC."""

from deltachat2 import ChatlistFlag, ChatType, Rpc, SpecialContactId


class ToolInputError(ValueError):
    """Tool argument error safe to return without its input values."""


def chat_id_from(params: dict) -> int:
    chat_id = params.get("chat_id")
    if type(chat_id) is not int or chat_id <= 0:
        raise ToolInputError("chat_id must be a positive integer")
    return chat_id


def send_message(rpc: Rpc, account_id: int, params: dict) -> dict:
    text = params.get("text")
    if not isinstance(text, str) or not text:
        raise ToolInputError("text is required")
    address = params.get("addr")
    if params.get("chat_id") is not None:
        if address is not None:
            raise ToolInputError("Provide either addr or chat_id")
        chat_id = chat_id_from(params)
    elif isinstance(address, str) and address.strip():
        contact_id = rpc.create_contact(account_id, address, None)
        chat_id = rpc.create_chat_by_contact_id(account_id, contact_id)
    else:
        raise ToolInputError("Provide either addr or chat_id")
    message_id = rpc.misc_send_text_message(account_id, chat_id, text)
    return {"message_id": message_id, "chat_id": chat_id, "text": text}


def chat_ids(rpc: Rpc, account_id: int) -> list[int]:
    return rpc.get_chatlist_entries(
        account_id, ChatlistFlag.NO_SPECIALS, None, None
    ) + rpc.get_chatlist_entries(
        account_id, ChatlistFlag.NO_SPECIALS | ChatlistFlag.ARCHIVED_ONLY, None, None
    )


def list_chats(rpc: Rpc, account_id: int, _: dict) -> dict:
    chats = []
    for chat_id in chat_ids(rpc, account_id):
        chat = rpc.get_full_chat_by_id(account_id, chat_id)
        if chat.is_self_talk:
            continue
        address = chat.mailing_list_address
        if chat.chat_type == ChatType.SINGLE and chat.contact_ids and not chat.is_device_chat:
            address = rpc.get_contact(account_id, chat.contact_ids[0]).address
        chats.append(
            {
                "id": chat.id,
                "name": chat.name or address or "Unnamed",
                "addr": address,
                "is_group": chat.chat_type == ChatType.GROUP,
                "unread_count": chat.fresh_message_counter,
            }
        )
    return {"chats": chats}


def get_messages(rpc: Rpc, account_id: int, params: dict) -> dict:
    chat_id = chat_id_from(params)
    # Confirm the ID still names a chat before querying its message history.
    rpc.get_basic_chat_info(account_id, chat_id)
    ids = rpc.get_message_ids(account_id, chat_id, False, False)[-20:]
    messages = []
    for message_id in ids:
        message = rpc.get_message(account_id, message_id)
        messages.append(
            {
                "id": message.id,
                "from": message.sender.address,
                "text": message.text,
                "timestamp": message.timestamp,
                "is_outgoing": message.from_id == SpecialContactId.SELF,
                "is_encrypted": message.show_padlock,
            }
        )
    return {"messages": messages}


def get_unread_count(rpc: Rpc, account_id: int, _: dict) -> dict:
    total = sum(rpc.get_fresh_msg_cnt(account_id, chat_id) for chat_id in chat_ids(rpc, account_id))
    return {"unread_count": total}
