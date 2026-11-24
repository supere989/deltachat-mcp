//! Owns the one native account process and multiplexes its newline JSON-RPC.

use std::{
    collections::{BTreeMap, HashMap},
    path::PathBuf,
    process::Stdio,
    sync::{
        Arc, Mutex,
        atomic::{AtomicU64, Ordering::Relaxed},
    },
    time::Duration,
};

use anyhow::{Context, Result, anyhow, bail};
use serde::de::DeserializeOwned;
use serde_json::{Value, json};
use tokio::{
    io::{AsyncBufReadExt, AsyncWriteExt, BufReader},
    process::{Child, Command},
    sync::{Semaphore, mpsc, oneshot},
    time::{sleep, timeout},
};
use tokio_util::sync::CancellationToken;

use crate::{chat, events::Events};

const CALL_TIMEOUT: Duration = Duration::from_secs(15);
const MAX_PENDING: usize = 33; // At most 32 tool RPCs plus one event poll.
const MAX_RESTARTS: u64 = 5;
#[cfg(not(test))]
const RESTART_BACKOFF: Duration = Duration::from_secs(1);
#[cfg(test)]
const RESTART_BACKOFF: Duration = Duration::from_millis(10);

pub struct Config {
    pub executable: PathBuf,
    pub accounts_dir: PathBuf,
    pub account_id: u32,
    /// The bearer credential comes from this environment variable. Keep it out of Core.
    pub token_env: Option<String>,
}

#[derive(Clone)]
pub struct Core(Arc<State>);

struct State {
    account: u32,
    active: Mutex<Option<Connection>>,
    stats: Arc<RpcStats>,
    pub events: Arc<Events>,
}

#[derive(Default)]
struct RpcStats {
    pid: AtomicU64,
    calls: AtomicU64,
    ok: AtomicU64,
    failed: AtomicU64,
    timed_out: AtomicU64,
    unknown_disposition: AtomicU64,
    late_responses: AtomicU64,
    restarts: AtomicU64,
    pending: AtomicU64,
    by_method: Mutex<BTreeMap<&'static str, u64>>,
}

#[derive(Clone)]
struct Connection {
    queue: mpsc::Sender<Vec<u8>>,
    pending: Arc<Mutex<HashMap<u64, oneshot::Sender<Reply>>>>,
    permits: Arc<Semaphore>,
    id: Arc<AtomicU64>,
    stats: Arc<RpcStats>,
    closed: CancellationToken,
}

#[derive(serde::Deserialize)]
struct Reply {
    id: u64,
    #[serde(flatten)]
    body: ReplyBody,
}

#[derive(serde::Deserialize)]
#[serde(untagged)]
enum ReplyBody {
    Failure { #[serde(rename = "error")] _error: Value },
    Success { result: Value },
}

/// Removes pending IDs even when the HTTP request is cancelled or times out.
struct Pending<'a> {
    connection: &'a Connection,
    id: u64,
    method: &'static str,
    dispatched: bool,
    received: bool,
    mutation: bool,
}

impl Drop for Pending<'_> {
    fn drop(&mut self) {
        self.connection.pending.lock().unwrap().remove(&self.id);
        self.connection.stats.pending.fetch_sub(1, Relaxed);
        if self.dispatched && !self.received && self.mutation {
            self.connection.stats.unknown_disposition.fetch_add(1, Relaxed);
            tracing::warn!(method = self.method, "native mutation result unknown");
        }
    }
}

impl Connection {
    async fn call<T: DeserializeOwned>(&self, method: &'static str, params: Value) -> Result<T> {
        self.stats.calls.fetch_add(1, Relaxed);
        *self.stats.by_method.lock().unwrap().entry(method).or_default() += 1;
        let result = self.exchange(method, params).await;
        if result.is_ok() {
            self.stats.ok.fetch_add(1, Relaxed);
        } else {
            self.stats.failed.fetch_add(1, Relaxed);
            tracing::warn!(method, "native RPC failed");
        }
        result
    }

    async fn exchange<T: DeserializeOwned>(&self, method: &'static str, params: Value) -> Result<T> {
        let polling = method == "get_next_event";
        let _permit = if polling {
            None
        } else {
            Some(self.deadline(method, self.permits.acquire()).await??)
        };
        let id = self.id.fetch_add(1, Relaxed);
        let mut request = serde_json::to_vec(&json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        }))?;
        request.push(b'\n');
        let (tx, rx) = oneshot::channel();
        self.pending.lock().unwrap().insert(id, tx);
        self.stats.pending.fetch_add(1, Relaxed);
        let mut pending = Pending {
            connection: self,
            id,
            method,
            dispatched: false,
            received: false,
            mutation: matches!(method, "misc_send_text_message" | "create_chat_by_contact_id" |
                "create_contact" | "marknoticed_chat"),
        };
        self.deadline(method, self.queue.send(request))
            .await?
            .map_err(|_| anyhow!("Delta Chat core is disconnected"))?;
        pending.dispatched = true;
        let response = async {
            tokio::select! {
                biased;
                response = rx => response.map_err(|_| anyhow!("Delta Chat core disconnected")),
                _ = self.closed.cancelled() => bail!("Delta Chat core disconnected"),
            }
        };
        let result = if polling { response.await } else { self.deadline(method, response).await? };
        let reply = result.map_err(|error| {
            if pending.mutation {
                anyhow!("Delta Chat did not confirm the operation. Check its result before retrying")
            } else {
                error
            }
        })?;
        pending.received = true;
        match reply.body {
            ReplyBody::Success { result } => {
                serde_json::from_value(result).map_err(|_| anyhow!("Unexpected Delta Chat RPC result"))
            }
            ReplyBody::Failure { .. } => bail!("Delta Chat rejected the operation"),
        }
    }

    async fn deadline<T>(
        &self,
        method: &'static str,
        work: impl Future<Output = T>,
    ) -> Result<T> {
        match timeout(CALL_TIMEOUT, work).await {
            Ok(result) => Ok(result),
            Err(_) => {
                self.stats.timed_out.fetch_add(1, Relaxed);
                tracing::warn!(method, "native RPC deadline elapsed");
                bail!("Delta Chat RPC timed out")
            }
        }
    }
}

impl Core {
    pub async fn open(
        mut config: Config,
        cancel: CancellationToken,
    ) -> Result<(Self, tokio::task::JoinHandle<Result<()>>)> {
        config.accounts_dir = tokio::fs::canonicalize(&config.accounts_dir)
            .await.context("resolve existing Delta Chat account directory")?;
        if !tokio::fs::metadata(config.accounts_dir.join("accounts.toml"))
            .await.context("expected an initialized Delta Chat account directory")?.is_file()
        {
            bail!("expected an initialized Delta Chat account directory");
        }
        config.executable = tokio::fs::canonicalize(&config.executable)
            .await.context("resolve native Delta Chat RPC executable")?;
        if config.account_id == 0 {
            bail!("account ID must be positive");
        }
        let core = Self(Arc::new(State {
            account: config.account_id,
            active: Mutex::new(None),
            stats: Arc::default(),
            events: Arc::default(),
        }));
        let (ready_tx, ready_rx) = oneshot::channel();
        let task = tokio::spawn(core.clone().supervise(config, cancel, ready_tx));
        ready_rx.await.context("native startup task ended")??;
        Ok((core, task))
    }

    pub fn account(&self) -> u32 {
        self.0.account
    }

    pub(crate) fn events(&self) -> &Arc<Events> {
        &self.0.events
    }

    pub(crate) async fn call<T: DeserializeOwned>(
        &self, method: &'static str, parameters: Value,
    ) -> Result<T> {
        let connection = self.0.active.lock().unwrap().clone()
            .ok_or_else(|| anyhow!("Delta Chat core is unavailable"))?;
        connection.call(method, parameters).await
    }

    pub(crate) fn status(&self) -> Value {
        let stats = &self.0.stats;
        let pid = stats.pid.load(Relaxed);
        json!({
            "ready": self.0.active.lock().unwrap().is_some(),
            "native_pid": (pid != 0).then_some(pid),
            "calls": stats.calls.load(Relaxed),
            "ok": stats.ok.load(Relaxed),
            "failed": stats.failed.load(Relaxed),
            "timed_out": stats.timed_out.load(Relaxed),
            "unknown_disposition": stats.unknown_disposition.load(Relaxed),
            "late_responses": stats.late_responses.load(Relaxed),
            "restarts": stats.restarts.load(Relaxed),
            "pending": stats.pending.load(Relaxed),
            "by_method": *stats.by_method.lock().unwrap(),
            "events": self.0.events.status(),
        })
    }

    async fn supervise(
        self, config: Config, cancel: CancellationToken, ready: oneshot::Sender<Result<()>>,
    ) -> Result<()> {
        let mut first = Some(ready);
        for attempt in 0..=MAX_RESTARTS {
            let result = self.run_child(&config, &cancel, &mut first).await;
            if let Some(ready) = first.take() {
                let _ = ready.send(result);
                return Ok(());
            }
            if cancel.is_cancelled() {
                return Ok(());
            }
            self.0.events.gap("native session ended");
            tracing::warn!("Delta Chat core unavailable");
            if attempt == MAX_RESTARTS {
                break;
            }
            tokio::select! {
                _ = cancel.cancelled() => return Ok(()),
                _ = sleep(RESTART_BACKOFF * (1 << attempt)) => {},
            }
            self.0.stats.restarts.fetch_add(1, Relaxed);
        }
        bail!("Delta Chat core restart limit reached");
    }

    async fn run_child(
        &self, config: &Config, cancel: &CancellationToken, first: &mut Option<oneshot::Sender<Result<()>>>,
    ) -> Result<()> {
        let mut command = Command::new(&config.executable);
        if let Some(variable) = &config.token_env {
            command.env_remove(variable);
        }
        let mut child = command
            .env("DC_ACCOUNTS_PATH", &config.accounts_dir)
            .stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::null())
            .kill_on_drop(true).spawn().context("start native Delta Chat RPC")?;
        self.0.stats.pid.store(u64::from(child.id().unwrap()), Relaxed);
        let (connection, mut io) = start_io_tasks(&mut child, self.0.stats.clone());
        let result = tokio::select! {
            _ = cancel.cancelled() => Err(anyhow!("Delta Chat startup cancelled")),
            _ = &mut io => Err(anyhow!("native Delta Chat RPC closed during startup")),
            result = self.start_account(&connection) => result,
        };
        // The same connection stays installed for the full event-worker lifetime.
        if result.is_ok() {
            *self.0.active.lock().unwrap() = Some(connection.clone());
            if let Some(ready) = first.take() {
                let _ = ready.send(Ok(()));
            }
            tokio::select! {
                _ = &mut io => {},
                _ = self.poll_events(&connection) => {},
                _ = cancel.cancelled() => {
                    let stopped = timeout(
                        Duration::from_secs(3),
                        connection.call::<Value>("stop_io", json!([self.account()])),
                    ).await;
                    if !matches!(stopped, Ok(Ok(_))) {
                        tracing::warn!("Delta Chat core did not acknowledge stop_io");
                    }
                },
            }
        }
        *self.0.active.lock().unwrap() = None;
        connection.closed.cancel();
        if !io.is_finished() {
            let _ = io.await;
        }
        drop(connection);
        if timeout(Duration::from_secs(3), child.wait()).await.is_err() {
            child.kill().await.context("reap native Delta Chat RPC")?;
        }
        self.0.stats.pid.store(0, Relaxed);
        result
    }

    async fn start_account(&self, connection: &Connection) -> Result<()> {
        let ids: Vec<u32> = connection.call("get_all_account_ids", json!([])).await?;
        if ids != [self.account()] {
            bail!("native account store must contain exactly the specified account ID");
        }
        let account: Value = connection.call("get_account_info", json!([self.account()])).await?;
        if account["kind"] != "Configured" {
            bail!("the specified native account is unconfigured");
        }
        connection.call::<Value>("start_io", json!([self.account()])).await?;
        Ok(())
    }

    async fn poll_events(&self, connection: &Connection) {
        loop {
            let event: Value = match connection.call("get_next_event", json!([])).await {
                Ok(event) => event,
                Err(_) => return,
            };
            let kind = event["event"]["kind"].as_str();
            if kind == Some("EventChannelOverflow") {
                self.0.events.gap("native event channel overflow");
                continue;
            }
            if kind != Some("IncomingMsg") {
                continue;
            }
            if event["contextId"].as_u64() != Some(u64::from(self.account())) {
                self.0.events.foreign();
                continue;
            }
            let decoded = serde_json::from_value::<Incoming>(event["event"].clone());
            let Ok(incoming) = decoded else {
                self.0.events.gap("invalid native incoming event");
                continue;
            };
            match chat::incoming_message(self, incoming.chat_id, incoming.msg_id).await {
                Ok(Some(message)) => self.0.events.push(message),
                Ok(None) => self.0.events.filtered(),
                Err(_) => self.0.events.gap("incoming message could not be read"),
            }
        }
    }
}

#[derive(serde::Deserialize)]
#[serde(rename_all = "camelCase")]
struct Incoming {
    chat_id: u32,
    msg_id: u32,
}

fn start_io_tasks(
    child: &mut Child, stats: Arc<RpcStats>,
) -> (Connection, tokio::task::JoinHandle<()>) {
    let mut stdin = child.stdin.take().unwrap();
    let mut lines = BufReader::new(child.stdout.take().unwrap()).lines();
    let (queue, mut outbound) = mpsc::channel::<Vec<u8>>(MAX_PENDING);
    let connection = Connection {
        queue,
        pending: Arc::default(),
        permits: Arc::new(Semaphore::new(MAX_PENDING - 1)),
        id: Arc::new(AtomicU64::new(1)),
        stats,
        closed: CancellationToken::new(),
    };
    let closed = connection.closed.clone();
    let pending = connection.pending.clone();
    let stats = connection.stats.clone();
    let writer = async move {
        while let Some(request) = outbound.recv().await {
            stdin.write_all(&request).await?;
        }
        Ok::<_, std::io::Error>(())
    };
    let reader = async move {
        while let Some(line) = lines.next_line().await? {
            let reply: Reply = serde_json::from_str(&line).map_err(std::io::Error::other)?;
            if let Some(sender) = pending.lock().unwrap().remove(&reply.id) {
                let _ = sender.send(reply);
            } else {
                stats.late_responses.fetch_add(1, Relaxed);
                tracing::warn!("late or unsolicited native RPC response");
            }
        }
        Ok::<_, std::io::Error>(())
    };
    let io = tokio::spawn(async move {
        tokio::select! {
            result = reader => if result.is_err() {
                tracing::warn!("Delta Chat RPC reader failed");
            },
            result = writer => if result.is_err() {
                tracing::warn!("Delta Chat RPC writer failed");
            },
            _ = closed.cancelled() => {},
        }
        closed.cancel();
    });
    (connection, io)
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;
    use std::{fs, os::unix::fs::PermissionsExt, time::{SystemTime, UNIX_EPOCH}};

    struct Fixture(PathBuf);

    impl Drop for Fixture {
        fn drop(&mut self) {
            let _ = fs::remove_file(self.0.join("core"));
            let _ = fs::remove_file(self.0.join("accounts.toml"));
            let _ = fs::remove_dir(&self.0);
        }
    }

    #[tokio::test]
    async fn exhausted_core_restart_budget_is_a_failure() {
        let serial = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos();
        let directory = std::env::temp_dir().join(format!("deltachat-supervisor-{}-{serial}", std::process::id()));
        fs::create_dir(&directory).unwrap();
        let fixture = Fixture(directory);
        let executable = fixture.0.join("core");
        fs::write(fixture.0.join("accounts.toml"), "").unwrap();
        fs::write(&executable, include_str!("../tests/fixtures/core.py")).unwrap();
        fs::set_permissions(&executable, fs::Permissions::from_mode(0o700)).unwrap();
        let config = Config {
            executable: executable.clone(),
            accounts_dir: fixture.0.clone(),
            account_id: 1,
            token_env: None,
        };
        let (core, supervisor) = Core::open(config, CancellationToken::new()).await.unwrap();
        // The current child has loaded its script. Absent executable blocks each reopen.
        fs::remove_file(executable).unwrap();
        assert!(core.call::<u32>("misc_send_text_message", json!([1, 12, "disconnect"])).await.is_err());
        let failure = timeout(Duration::from_secs(5), supervisor).await.unwrap().unwrap().unwrap_err();
        assert!(failure.to_string().contains("restart limit reached"));
        assert_eq!(core.status()["restarts"], MAX_RESTARTS);
        assert_eq!(core.status()["ready"], false);
    }
}
