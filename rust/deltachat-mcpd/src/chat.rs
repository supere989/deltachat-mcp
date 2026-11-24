//! The chat tool contract and native Delta Chat field mappings.

use std::collections::{BTreeMap, BTreeSet};

use anyhow::{Result, bail, ensure};
use rmcp::{model::{CallToolResult, ContentBlock}, schemars};
use serde::{Deserialize, Serialize};
use serde_json::{Value, json};

use crate::rpc::Core;

const SELF: u32 = 1;
const ARCHIVED_ONLY: u8 = 0x01;
const NO_SPECIALS: u8 = 0x02;

#[derive(Debug, Deserialize, schemars::JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct ChatId {
    #[schemars(range(min = 1))]
    pub chat_id: u32,
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct History {
    #[schemars(range(min = 1))]
    pub chat_id: u32,
    #[serde(default = "default_limit")]
    #[schemars(range(min = 1))]
    pub limit: usize,
}

fn default_limit() -> usize {
    20
}

#[derive(Debug, Deserialize, schemars::JsonSchema)]
#[serde(deny_unknown_fields)]
pub struct SendMessage {
    /// Choose an existing chat by ID, or supply addr.
    #[schemars(range(min = 1))]
    pub chat_id: Option<u32>,
    /// Resolve an email address to a single eligible contact.
    pub addr: Option<String>,
    #[schemars(length(min = 1))]
    pub text: String,
    /// Require an encrypted chat before queuing the message.
    #[serde(default)]
    pub require_encryption: bool,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Chat {
    id: u32,
    name: String,
    chat_type: String,
    is_self_talk: bool,
    is_device_chat: bool,
    is_contact_request: bool,
    is_muted: bool,
    is_encrypted: bool,
    // Supplied by get_full_chat_by_id, omitted by get_basic_chat_info.
    #[serde(default)]
    contact_ids: Vec<u32>,
    #[serde(default)]
    mailing_list_address: Option<String>,
    #[serde(default)]
    fresh_message_counter: u32,
}

impl Chat {
    fn special(&self) -> bool {
        self.is_self_talk || self.is_device_chat
    }

    fn display_name(&self) -> String {
        if self.name.is_empty() { format!("Chat {}", self.id) } else { self.name.clone() }
    }
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Contact {
    id: u32,
    address: String,
    is_key_contact: bool,
    is_blocked: bool,
    e2ee_avail: bool,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct Sender {
    address: String,
    display_name: String,
}

#[derive(Deserialize)]
#[serde(rename_all = "camelCase")]
struct NativeMessage {
    id: u32,
    chat_id: u32,
    from_id: u32,
    sender: Sender,
    text: String,
    timestamp: i64,
    is_info: bool,
    #[serde(default)]
    is_bot: bool,
    show_padlock: bool,
}

#[derive(Clone, Serialize)]
pub(crate) struct Message {
    pub id: u32,
    pub chat_id: u32,
    chat_name: String,
    chat_type: String,
    #[serde(rename = "from")]
    sender_name: String,
    sender_addr: String,
    sender_id: u32,
    text: String,
    timestamp: i64,
    is_outgoing: bool,
    is_info: bool,
    is_bot: bool,
    is_encrypted: bool,
    is_contact_request: bool,
    is_muted: bool,
}

impl NativeMessage {
    fn inbound(&self) -> bool {
        self.from_id != SELF && !self.is_info
    }

    fn summary(self, chat: &Chat) -> Message {
        let sender_name = if self.sender.display_name.is_empty() {
            self.sender.address.clone()
        } else {
            self.sender.display_name
        };
        Message {
            id: self.id,
            chat_id: self.chat_id,
            chat_name: chat.display_name(),
            chat_type: chat.chat_type.clone(),
            sender_name,
            sender_addr: self.sender.address,
            sender_id: self.from_id,
            text: self.text,
            timestamp: self.timestamp,
            is_outgoing: self.from_id == SELF,
            is_info: self.is_info,
            is_bot: self.is_bot,
            is_encrypted: self.show_padlock,
            is_contact_request: chat.is_contact_request,
            is_muted: chat.is_muted,
        }
    }
}

async fn basic_chat(core: &Core, chat_id: u32) -> Result<Chat> {
    ensure!(chat_id > 0, "chat_id must be a positive integer");
    core.call("get_basic_chat_info", json!([core.account(), chat_id])).await
}

async fn chat_ids(core: &Core) -> Result<Vec<u32>> {
    let mut result = Vec::new();
    let mut seen = BTreeSet::new();
    for flags in [NO_SPECIALS, NO_SPECIALS | ARCHIVED_ONLY] {
        let ids: Vec<u32> = core.call(
            "get_chatlist_entries", json!([core.account(), flags, null, null]),
        ).await?;
        result.extend(ids.into_iter().filter(|id| seen.insert(*id)));
    }
    Ok(result)
}

pub(crate) async fn list_chats(core: &Core) -> Result<CallToolResult> {
    let mut chats = Vec::new();
    let account = core.account();
    for id in chat_ids(core).await? {
        let chat: Chat = core.call("get_full_chat_by_id", json!([account, id])).await?;
        if chat.special() {
            continue;
        }
        let addr = match (chat.chat_type.as_str(), chat.contact_ids.first()) {
            ("Single", Some(contact_id)) => {
                let contact: Contact = core.call("get_contact", json!([account, contact_id])).await?;
                Some(contact.address)
            }
            _ => chat.mailing_list_address.clone(),
        };
        chats.push(json!({
            "id": id,
            "name": chat.display_name(),
            "addr": addr,
            "is_group": chat.chat_type == "Group",
            "chat_type": chat.chat_type,
            "unread_count": chat.fresh_message_counter,
        }));
    }
    Ok(CallToolResult::structured(json!({ "chats": chats })))
}

pub(crate) async fn get_messages(core: &Core, args: History) -> Result<CallToolResult> {
    ensure!(args.limit > 0, "limit must be at least 1");
    let chat = basic_chat(core, args.chat_id).await?;
    let account = core.account();
    let ids: Vec<u32> = core.call(
        "get_message_ids", json!([account, args.chat_id, false, false]),
    ).await?;
    let mut messages = Vec::new();
    for id in &ids[ids.len().saturating_sub(args.limit)..] {
        let msg: NativeMessage = core.call("get_message", json!([account, id])).await?;
        messages.push(msg.summary(&chat));
    }
    Ok(CallToolResult::structured(json!({ "chat_id": args.chat_id, "messages": messages })))
}

pub(crate) async fn get_unread_count(core: &Core) -> Result<CallToolResult> {
    let mut unread_count = 0;
    for id in chat_ids(core).await? {
        if !basic_chat(core, id).await?.special() {
            unread_count += core.call::<u64>("get_fresh_msg_cnt", json!([core.account(), id])).await?;
        }
    }
    Ok(CallToolResult::structured(json!({ "unread_count": unread_count })))
}

async fn contact_id_for_address(core: &Core, address: &str, require_encryption: bool) -> Result<u32> {
    let normalized = address.trim().to_lowercase();
    let normalized = normalized.strip_prefix("mailto:").unwrap_or(&normalized);
    ensure!(
        !normalized.starts_with("mailto:") && core.call::<bool>("check_email_validity", json!([normalized])).await?,
        "Provide a valid email address",
    );
    let account = core.account();
    // Use the single-ID lookup only for self. A remote address can have several keys.
    let lookup: Option<u32> = core.call("lookup_contact_id_by_addr", json!([account, normalized])).await?;
    if lookup == Some(SELF) {
        return Ok(SELF);
    }
    let contacts: Vec<Contact> = core.call("get_contacts", json!([account, 0, normalized])).await?;
    let blocked: Vec<Contact> = core.call("get_blocked_contacts", json!([account])).await?;
    let blocked = blocked.into_iter()
        .filter(|contact| contact.address.to_lowercase() == normalized)
        .collect::<Vec<_>>();
    let mut keys = contacts.iter()
        .chain(&blocked)
        .filter(|contact| contact.is_key_contact && contact.address.to_lowercase() == normalized);
    if let Some(contact) = keys.next() {
        ensure!(keys.next().is_none(), "Multiple key contacts match this address. Choose a chat_id.");
        ensure!(!contact.is_blocked, "The matching contact is blocked");
        ensure!(contact.e2ee_avail, "The contact's encryption key is missing. Complete SecureJoin in Delta Chat first.");
        return Ok(contact.id);
    }
    ensure!(blocked.is_empty(), "The matching contact is blocked");
    let forced: Option<String> = core.call("get_config", json!([account, "force_encryption"])).await?;
    if require_encryption || forced.as_deref() != Some("0") {
        bail!("No encryption key is available for this address. Scan the contact's SecureJoin QR code in Delta Chat, then retry with the address or chat_id.");
    }
    core.call("create_contact", json!([account, normalized, null])).await
}

pub(crate) async fn send_message(core: &Core, args: SendMessage) -> Result<CallToolResult> {
    ensure!(!args.text.is_empty(), "text is required");
    let account = core.account();
    let chat_id = match (args.chat_id, args.addr) {
        (Some(id), None) if id > 0 => id,
        (None, Some(addr)) if !addr.trim().is_empty() => {
            let contact_id = contact_id_for_address(core, &addr, args.require_encryption).await?;
            core.call("create_chat_by_contact_id", json!([account, contact_id])).await?
        }
        _ => bail!("Provide either a positive chat_id or addr"),
    };
    if args.require_encryption {
        let chat = basic_chat(core, chat_id).await?;
        ensure!(chat.is_encrypted, "The chat is unencrypted. Complete SecureJoin in Delta Chat first.");
    }
    let message_id: u32 = core.call(
        "misc_send_text_message", json!([account, chat_id, args.text]),
    ).await?;
    Ok(CallToolResult::structured(json!({
        "message_id": message_id,
        "chat_id": chat_id,
        "text": args.text,
        "status": "queued",
    })))
}

#[derive(Serialize)]
struct ChatDigest {
    chat_id: u32,
    name: String,
    messages: Vec<Message>,
}

pub(crate) async fn get_unread_digest(core: &Core) -> Result<CallToolResult> {
    let account = core.account();
    let mut ids: Vec<u32> = core.call("get_fresh_msgs", json!([account])).await?;
    ids.sort_unstable();
    let mut chats = BTreeMap::<u32, Chat>::new();
    let mut chat_positions = BTreeMap::new();
    let mut digest: Vec<ChatDigest> = Vec::new();
    for id in ids {
        let msg: NativeMessage = core.call("get_message", json!([account, id])).await?;
        if !msg.inbound() {
            continue;
        }
        let chat_id = msg.chat_id;
        let chat = match chats.entry(chat_id) {
            std::collections::btree_map::Entry::Occupied(e) => e.into_mut(),
            std::collections::btree_map::Entry::Vacant(e) => e.insert(basic_chat(core, chat_id).await?),
        };
        if chat.special() {
            continue;
        }
        let index = *chat_positions.entry(chat_id).or_insert_with(|| {
            let index = digest.len();
            digest.push(ChatDigest { chat_id, name: chat.display_name(), messages: Vec::new() });
            index
        });
        digest[index].messages.push(msg.summary(chat));
    }
    // Preserve the Python digest array for text-only consumers.
    let mut result = CallToolResult::structured(json!({ "chats": &digest }));
    result.content = vec![ContentBlock::text(serde_json::to_string(&digest)?)];
    Ok(result)
}

pub(crate) async fn mark_noticed(core: &Core, args: ChatId) -> Result<CallToolResult> {
    ensure!(args.chat_id > 0, "chat_id must be a positive integer");
    core.call::<Value>("marknoticed_chat", json!([core.account(), args.chat_id])).await?;
    Ok(CallToolResult::structured(json!({ "chat_id": args.chat_id, "status": "noticed" })))
}

pub(crate) async fn incoming_message(core: &Core, chat_id: u32, msg_id: u32) -> Result<Option<Message>> {
    let msg: NativeMessage = core.call("get_message", json!([core.account(), msg_id])).await?;
    ensure!(msg.chat_id == chat_id && msg.id == msg_id, "native incoming event disagrees with message");
    if !msg.inbound() {
        return Ok(None);
    }
    let chat = basic_chat(core, chat_id).await?;
    Ok((!chat.special()).then(|| msg.summary(&chat)))
}
