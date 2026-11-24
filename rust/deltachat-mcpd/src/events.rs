//! Bounded change notifications and a short, read-only message replay window.

use std::{
    collections::VecDeque,
    sync::{Arc, Mutex, atomic::{AtomicU64, Ordering::Relaxed}},
};

use serde_json::{Value, json};
use tokio::sync::broadcast;

use crate::chat::Message;

pub(crate) const INCOMING: &str = "dc://events/incoming";
pub(crate) const CHAT_TEMPLATE: &str = "dc://events/chat/{chat_id}";
const CHAT_PREFIX: &str = "dc://events/chat/";
const WINDOW: usize = 128;

#[derive(Clone, Copy)]
pub(crate) enum Scope {
    Incoming,
    Chat(u32),
}

impl Scope {
    pub fn from_uri(uri: &str) -> Option<Self> {
        if uri == INCOMING {
            return Some(Self::Incoming);
        }
        let raw = uri.strip_prefix(CHAT_PREFIX)?;
        let id: u32 = raw.parse().ok()?;
        if id > 0 && raw == id.to_string() {
            Some(Self::Chat(id))
        } else {
            None
        }
    }

    pub fn matches(self, chat: Option<u32>) -> bool {
        match (self, chat) {
            (_, None) | (Self::Incoming, _) => true,
            (Self::Chat(a), Some(b)) => a == b,
        }
    }
}

pub(crate) struct Events {
    updates: broadcast::Sender<Option<u32>>,
    recent: Mutex<VecDeque<Arc<Message>>>,
    delivered: AtomicU64,
    gap: AtomicU64,
    foreign: AtomicU64,
    filtered: AtomicU64,
    overwritten: AtomicU64,
    without_listeners: AtomicU64,
}

impl Default for Events {
    fn default() -> Self {
        Self {
            updates: broadcast::channel(WINDOW).0,
            recent: Mutex::new(VecDeque::with_capacity(WINDOW)),
            delivered: AtomicU64::new(0),
            gap: AtomicU64::new(0),
            foreign: AtomicU64::new(0),
            filtered: AtomicU64::new(0),
            overwritten: AtomicU64::new(0),
            without_listeners: AtomicU64::new(0),
        }
    }
}

impl Events {
    pub fn subscribe(&self) -> broadcast::Receiver<Option<u32>> {
        self.updates.subscribe()
    }

    pub fn push(&self, message: Message) {
        let chat_id = message.chat_id;
        let mut recent = self.recent.lock().unwrap();
        if recent.iter().any(|m| m.id == message.id) {
            self.filtered();
            return;
        }
        if recent.len() == WINDOW {
            recent.pop_front();
            self.overwritten.fetch_add(1, Relaxed);
            self.gap.fetch_add(1, Relaxed);
        }
        recent.push_back(Arc::new(message));
        drop(recent);
        self.delivered.fetch_add(1, Relaxed);
        if self.updates.send(Some(chat_id)).is_err() {
            self.without_listeners.fetch_add(1, Relaxed);
        }
    }

    pub fn gap(&self, reason: &'static str) {
        self.gap.fetch_add(1, Relaxed);
        tracing::warn!(reason, "incoming event gap");
        let _ = self.updates.send(None);
    }

    pub fn foreign(&self) {
        self.foreign.fetch_add(1, Relaxed);
        tracing::warn!("ignored incoming event outside configured account");
    }

    pub fn filtered(&self) {
        self.filtered.fetch_add(1, Relaxed);
    }

    pub fn read(&self, scope: Scope) -> Value {
        let recent = self.recent.lock().unwrap();
        let messages: Vec<_> = recent.iter()
            .filter(|m| scope.matches(Some(m.chat_id)))
            .map(Arc::clone)
            .collect();
        let gap = self.gap.load(Relaxed);
        drop(recent);
        json!({ "messages": messages.iter().map(Arc::as_ref).collect::<Vec<_>>(), "gap": gap })
    }

    pub fn status(&self) -> Value {
        json!({
            "incoming": self.delivered.load(Relaxed),
            "gap": self.gap.load(Relaxed),
            "foreign": self.foreign.load(Relaxed),
            "filtered": self.filtered.load(Relaxed),
            "overwritten": self.overwritten.load(Relaxed),
            "without_listeners": self.without_listeners.load(Relaxed),
        })
    }
}
