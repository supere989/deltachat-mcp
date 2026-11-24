//! Owns a Delta Chat account and serves its chat tools and incoming events over MCP.
//!
//! MCP revision checked: 2026-07-28 (current), on 2026-11-23. Modern requests are served
//! statelessly; a legacy `initialize` (2025-11-25 and earlier) gets an `Mcp-Session-Id` session.
//!
//! The HTTP router shares one supervised native Core and one event buffer across MCP handlers.
//! SAI observes requests, tools, native RPC and event delivery in authenticated /status.
//! The redacted audit identifies timeouts, failed operations, event gaps and stream failures.
//! Chat and event routing are deterministic.

mod chat;
mod events;
pub mod rpc;

use std::collections::{BTreeMap, BTreeSet};
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use std::time::Duration;

use axum::{
    Json, Router,
    body::Body,
    extract::State,
    http::{Request, StatusCode, header},
    middleware::{self, Next},
    response::{IntoResponse, Response},
    routing::get,
};
use rmcp::{
    ErrorData as McpError, RoleServer, ServerHandler,
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::{
        CacheScope, CallToolResult, ContentBlock, Implementation, ListResourceTemplatesResult, ListResourcesResult,
        PaginatedRequestParams, ReadResourceRequestParams, ReadResourceResponse, ReadResourceResult,
        Resource, ResourceContents, ResourceTemplate, ResourceUpdatedNotificationParam,
        ServerCapabilities, ServerConfig, SubscribeRequestParams, SubscriptionFilter,
        UnsubscribeRequestParams,
    },
    schemars,
    service::{RequestContext, SubscriptionContext},
    tool, tool_handler, tool_router,
    transport::streamable_http_server::{
        StreamableHttpServerConfig, StreamableHttpService, session::local::LocalSessionManager,
    },
};
use serde_json::{Value, json};
use tokio::{sync::broadcast, time::timeout};
use tokio_util::sync::CancellationToken;

use crate::events::{CHAT_TEMPLATE, INCOMING, Scope};
use crate::rpc::Core;

/// SAI Observe counters.
#[derive(Default)]
pub struct Stats {
    pub mcp_requests: AtomicU64,
    pub auth_rejected: AtomicU64,
    pub tool_calls: AtomicU64,
    pub tool_ok: AtomicU64,
    pub tool_fail: AtomicU64,
    pub with_session: AtomicU64,
    pub without_session: AtomicU64,
    pub notify_sent: AtomicU64,
    pub notify_failed: AtomicU64,
    /// Modern `subscriptions/listen` streams opened / delivered / failed (stream-scoped sink).
    pub listen_opened: AtomicU64,
    pub listen_sent: AtomicU64,
    pub listen_failed: AtomicU64,
    pub listen_lagged: AtomicU64,
    pub by_tool: Mutex<BTreeMap<&'static str, ToolStats>>,
    /// /mcp requests by `MCP-Protocol-Version` header ("absent" when missing).
    pub by_version: Mutex<BTreeMap<String, u64>>,
    /// /mcp responses by HTTP status code.
    pub by_status: Mutex<BTreeMap<u16, u64>>,
}

#[derive(Default, serde::Serialize)]
pub struct ToolStats {
    calls: u64,
    ok: u64,
    failed: u64,
}

impl Stats {
    fn snapshot(&self) -> serde_json::Value {
        let g = |a: &AtomicU64| a.load(Ordering::Relaxed);
        serde_json::json!({
            "mcp_requests": g(&self.mcp_requests),
            "auth_rejected": g(&self.auth_rejected),
            "tool_calls": g(&self.tool_calls),
            "tool_ok": g(&self.tool_ok),
            "tool_fail": g(&self.tool_fail),
            "with_session": g(&self.with_session),
            "without_session": g(&self.without_session),
            "notify_sent": g(&self.notify_sent),
            "notify_failed": g(&self.notify_failed),
            "listen_opened": g(&self.listen_opened),
            "listen_sent": g(&self.listen_sent),
            "listen_failed": g(&self.listen_failed),
            "listen_lagged": g(&self.listen_lagged),
            "by_tool": *self.by_tool.lock().unwrap(),
            "by_version": *self.by_version.lock().unwrap(),
            "by_status": *self.by_status.lock().unwrap(),
        })
    }

    fn bump<K: Ord>(map: &Mutex<BTreeMap<K, u64>>, key: K) {
        *map.lock().unwrap().entry(key).or_insert(0) += 1;
    }

    fn tool_started(&self, name: &'static str) {
        self.tool_calls.fetch_add(1, Ordering::Relaxed);
        self.by_tool.lock().unwrap().entry(name).or_default().calls += 1;
    }

    fn tool_completed(&self, name: &'static str, ok: bool) {
        let mut stats = self.by_tool.lock().unwrap();
        let stats = stats.entry(name).or_default();
        if ok {
            self.tool_ok.fetch_add(1, Ordering::Relaxed);
            stats.ok += 1;
        } else {
            self.tool_fail.fetch_add(1, Ordering::Relaxed);
            stats.failed += 1;
            tracing::warn!(name, "chat tool failed");
        }
    }
}

#[derive(Debug, serde::Deserialize, schemars::JsonSchema)]
pub struct EchoRequest {
    #[schemars(description = "text to echo back")]
    pub text: String,
}

#[derive(Clone)]
pub struct Server {
    stats: Arc<Stats>,
    core: Option<Core>,
    cancel: CancellationToken,
    modern_events: Arc<Mutex<Option<broadcast::Receiver<Option<u32>>>>>,
    legacy: Arc<Mutex<BTreeMap<String, CancellationToken>>>,
    tool_router: ToolRouter<Self>,
}

const CHAT_TOOLS: [&str; 6] = [
    "list_chats", "get_messages", "get_unread_count", "send_message", "get_unread_digest", "mark_noticed",
];
const MAX_SUBSCRIPTIONS: usize = 32;
const STREAM_SEND_TIMEOUT: Duration = Duration::from_secs(5);

#[tool_router]
impl Server {
    fn new(stats: Arc<Stats>, core: Option<Core>, cancel: CancellationToken) -> Self {
        let mut tool_router = Self::tool_router();
        if core.is_some() {
            tool_router.remove_route("echo");
        } else {
            for name in CHAT_TOOLS {
                tool_router.remove_route(name);
            }
        }
        Self {
            stats, core, cancel, tool_router,
            modern_events: Arc::default(),
            legacy: Arc::default(),
        }
    }

    #[tool(description = "Echo text back in HTTP diagnostics mode")]
    fn echo(&self, Parameters(EchoRequest { text }): Parameters<EchoRequest>) -> String {
        self.stats.tool_started("echo");
        self.stats.tool_completed("echo", true);
        text
    }

    #[tool(description = "List Delta Chat conversations and their unread counts")]
    async fn list_chats(&self) -> CallToolResult {
        self.stats.tool_started("list_chats");
        self.tool_result("list_chats", chat::list_chats(self.core()).await)
    }

    #[tool(description = "Get recent messages in an existing Delta Chat conversation")]
    async fn get_messages(&self, Parameters(args): Parameters<chat::History>) -> CallToolResult {
        self.stats.tool_started("get_messages");
        self.tool_result("get_messages", chat::get_messages(self.core(), args).await)
    }

    #[tool(description = "Get the total unread count across Delta Chat conversations")]
    async fn get_unread_count(&self) -> CallToolResult {
        self.stats.tool_started("get_unread_count");
        self.tool_result("get_unread_count", chat::get_unread_count(self.core()).await)
    }

    #[tool(description = "Queue text in a chat selected by chat_id or addr")]
    async fn send_message(&self, Parameters(args): Parameters<chat::SendMessage>) -> CallToolResult {
        self.stats.tool_started("send_message");
        self.tool_result("send_message", chat::send_message(self.core(), args).await)
    }

    #[tool(description = "Read fresh inbound messages grouped by chat without marking them noticed")]
    async fn get_unread_digest(&self) -> CallToolResult {
        self.stats.tool_started("get_unread_digest");
        self.tool_result("get_unread_digest", chat::get_unread_digest(self.core()).await)
    }

    #[tool(description = "Mark a chat's unread messages as noticed without read receipts")]
    async fn mark_noticed(&self, Parameters(args): Parameters<chat::ChatId>) -> CallToolResult {
        self.stats.tool_started("mark_noticed");
        self.tool_result("mark_noticed", chat::mark_noticed(self.core(), args).await)
    }
}

impl Server {
    fn core(&self) -> &Core {
        self.core.as_ref().expect("chat tools are available only with a native account")
    }

    fn tool_result(&self, method: &'static str, outcome: anyhow::Result<CallToolResult>) -> CallToolResult {
        self.stats.tool_completed(method, outcome.is_ok());
        outcome.unwrap_or_else(|err| CallToolResult::error(vec![ContentBlock::text(err.to_string())]))
    }
}

#[tool_handler(router = self.tool_router)]
impl ServerHandler for Server {
    fn get_info(&self) -> ServerConfig {
        let builder = ServerCapabilities::builder().enable_tools();
        let capabilities = if self.core.is_some() {
            builder.enable_resources().enable_resources_subscribe().build()
        } else {
            builder.build()
        };
        ServerConfig::new(capabilities)
        .with_server_info(Implementation::new("deltachat-mcpd", env!("CARGO_PKG_VERSION")))
        .with_instructions("Delta Chat chat tools and incoming message resources")
    }

    async fn list_resources(
        &self, _: Option<PaginatedRequestParams>, _: RequestContext<RoleServer>,
    ) -> Result<ListResourcesResult, McpError> {
        Ok(ListResourcesResult::with_all_items(self.core.iter().map(|_| {
            Resource::new(INCOMING, "Incoming Delta Chat messages")
                .with_description("Recent incoming messages across this account")
                .with_mime_type("application/json")
        }).collect()))
    }

    async fn list_resource_templates(
        &self, _: Option<PaginatedRequestParams>, _: RequestContext<RoleServer>,
    ) -> Result<ListResourceTemplatesResult, McpError> {
        Ok(ListResourceTemplatesResult::with_all_items(self.core.iter().map(|_| {
            ResourceTemplate::new(CHAT_TEMPLATE, "Incoming messages for a Delta Chat conversation")
                .with_mime_type("application/json")
        }).collect()))
    }

    async fn read_resource(
        &self, request: ReadResourceRequestParams, _: RequestContext<RoleServer>,
    ) -> Result<ReadResourceResponse, McpError> {
        let scope = Scope::from_uri(&request.uri)
            .zip(self.core.as_ref())
            .ok_or_else(|| McpError::resource_not_found("Unknown Delta Chat resource", None))?;
        let contents = scope.1.events().read(scope.0).to_string();
        Ok(ReadResourceResult::new(vec![ResourceContents::text(contents, request.uri)
            .with_mime_type("application/json")])
            .with_ttl_ms(0).with_cache_scope(CacheScope::Private).into())
    }

    fn accepted_subscription_filter(&self, requested: &SubscriptionFilter) -> Option<SubscriptionFilter> {
        let core = self.core.as_ref()?;
        let mut seen = BTreeSet::new();
        let uris = requested.resource_subscriptions.iter().flatten()
            .filter(|uri| Scope::from_uri(uri).is_some() && seen.insert(uri.as_str()))
            .take(MAX_SUBSCRIPTIONS)
            .cloned()
            .collect::<Vec<_>>();
        // The stateless HTTP handler is per request. Subscribe before rmcp sends its ack.
        *self.modern_events.lock().unwrap() = Some(core.events().subscribe());
        Some(SubscriptionFilter::builder().resource_subscriptions(uris).build())
    }

    async fn listen(&self, context: SubscriptionContext) -> Result<(), McpError> {
        self.stats.listen_opened.fetch_add(1, Ordering::Relaxed);
        let Some(mut updates) = self.modern_events.lock().unwrap().take() else {
            return Err(McpError::internal_error("No Delta Chat event receiver", None));
        };
        let uris: Vec<_> = context.accepted().resource_subscriptions.iter().flatten()
            .filter_map(|uri| Scope::from_uri(uri).map(|scope| (uri, scope))).collect();
        loop {
            let update = match tokio::select! {
                _ = self.cancel.cancelled() => return Ok(()),
                _ = context.cancelled() => return Ok(()),
                next = updates.recv() => next,
            } {
                Ok(chat) => chat,
                Err(broadcast::error::RecvError::Lagged(n)) => {
                    self.stats.listen_lagged.fetch_add(n, Ordering::Relaxed);
                    tracing::warn!(dropped = n, "modern subscription fell behind");
                    None
                }
                Err(broadcast::error::RecvError::Closed) => return Ok(()),
            };
            for (uri, scope) in &uris {
                if !scope.matches(update) {
                    continue;
                }
                let sent = tokio::select! {
                    _ = self.cancel.cancelled() => return Ok(()),
                    _ = context.cancelled() => return Ok(()),
                    sent = timeout(STREAM_SEND_TIMEOUT, context.sink().notify_resource_updated(*uri)) => sent,
                };
                if matches!(sent, Ok(Ok(()))) {
                    self.stats.listen_sent.fetch_add(1, Ordering::Relaxed);
                } else {
                    self.stats.listen_failed.fetch_add(1, Ordering::Relaxed);
                    tracing::warn!("modern subscription could not deliver update");
                    return Ok(());
                }
            }
        }
    }

    /// Legacy clients can subscribe on their negotiated MCP session.
    #[allow(deprecated)]
    async fn subscribe(
        &self,
        request: SubscribeRequestParams,
        context: RequestContext<RoleServer>,
    ) -> Result<(), McpError> {
        let (scope, core) = Scope::from_uri(&request.uri)
            .zip(self.core.as_ref())
            .ok_or_else(|| McpError::resource_not_found("Unknown Delta Chat resource", None))?;
        let mut subscriptions = self.legacy.lock().unwrap();
        if subscriptions.contains_key(&request.uri) {
            return Ok(());
        }
        if subscriptions.len() >= MAX_SUBSCRIPTIONS {
            return Err(McpError::invalid_params("Too many Delta Chat resource subscriptions", None));
        }
        let stop = self.cancel.child_token();
        subscriptions.insert(request.uri.clone(), stop.clone());
        let peer = context.peer;
        let stats = self.stats.clone();
        let uri = request.uri;
        let mut updates = core.events().subscribe();
        tokio::spawn(async move {
            let mut check = tokio::time::interval(Duration::from_secs(10));
            while !peer.is_transport_closed() {
                let update = tokio::select! {
                    _ = stop.cancelled() => break,
                    _ = check.tick() => continue,
                    update = updates.recv() => update,
                };
                match update {
                    Ok(chat) if !scope.matches(chat) => continue,
                    Err(broadcast::error::RecvError::Closed) => break,
                    Err(broadcast::error::RecvError::Lagged(n)) => {
                        stats.listen_lagged.fetch_add(n, Ordering::Relaxed);
                        tracing::warn!(dropped = n, "legacy subscription fell behind");
                    }
                    _ => {}
                }
                let sent = tokio::select! {
                    _ = stop.cancelled() => break,
                    sent = timeout(STREAM_SEND_TIMEOUT, peer.notify_resource_updated(
                        ResourceUpdatedNotificationParam::new(uri.clone())
                    )) => sent,
                };
                if matches!(sent, Ok(Ok(()))) {
                    stats.notify_sent.fetch_add(1, Ordering::Relaxed);
                } else {
                    stats.notify_failed.fetch_add(1, Ordering::Relaxed);
                    tracing::warn!("legacy subscription could not deliver update");
                    break;
                }
            }
        });
        Ok(())
    }

    #[allow(deprecated)]
    async fn unsubscribe(
        &self,
        request: UnsubscribeRequestParams,
        _: RequestContext<RoleServer>,
    ) -> Result<(), McpError> {
        if let Some(cancel) = self.legacy.lock().unwrap().remove(&request.uri) {
            cancel.cancel();
        }
        Ok(())
    }
}

/// Runtime settings for the HTTP shell.
#[derive(Clone)]
pub struct Settings {
    /// Bearer token; every /mcp and /status request must present it.
    pub token: String,
    /// Allowed `Host` values (DNS-rebinding defence), e.g. ["127.0.0.1", "127.0.0.1:9122"].
    pub allowed_hosts: Vec<String>,
}

#[derive(Clone)]
struct AppState {
    settings: Arc<Settings>,
    stats: Arc<Stats>,
    core: Option<Core>,
}

async fn auth(State(st): State<AppState>, req: Request<Body>, next: Next) -> Response {
    let ok = req
        .headers()
        .get(header::AUTHORIZATION)
        .and_then(|v| v.to_str().ok())
        .and_then(|v| v.strip_prefix("Bearer "))
        .is_some_and(|t| constant_time_eq(t.as_bytes(), st.settings.token.as_bytes()));
    if !ok {
        st.stats.auth_rejected.fetch_add(1, Ordering::Relaxed);
        if req.uri().path().starts_with("/mcp") {
            Stats::bump(&st.stats.by_status, 401);
        }
        return (StatusCode::UNAUTHORIZED, [(header::WWW_AUTHENTICATE, "Bearer")], "unauthorized")
            .into_response();
    }
    if !req.uri().path().starts_with("/mcp") {
        return next.run(req).await;
    }
    st.stats.mcp_requests.fetch_add(1, Ordering::Relaxed);
    let version = req
        .headers()
        .get("mcp-protocol-version")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("absent")
        .to_string();
    Stats::bump(&st.stats.by_version, version);
    if req.headers().contains_key("mcp-session-id") {
        st.stats.with_session.fetch_add(1, Ordering::Relaxed);
    } else {
        st.stats.without_session.fetch_add(1, Ordering::Relaxed);
    }
    let resp = next.run(req).await;
    Stats::bump(&st.stats.by_status, resp.status().as_u16());
    resp
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    a.len() == b.len() && a.iter().zip(b).fold(0u8, |acc, (x, y)| acc | (x ^ y)) == 0
}

async fn status(State(st): State<AppState>) -> Json<Value> {
    Json(json!({
        "service": "deltachat-mcpd",
        "version": env!("CARGO_PKG_VERSION"),
        "mcp_revision_checked": "2026-07-28",
        "mcp_revision_checked_on": "2026-11-23",
        "core": st.core.as_ref().map(Core::status),
        "stats": st.stats.snapshot(),
    }))
}

/// Build the full router: /mcp (dual-era MCP) and /status, both behind bearer auth.
pub fn router(settings: Settings, stats: Arc<Stats>, cancel: CancellationToken) -> Router {
    router_with_account(settings, stats, cancel, None)
}

pub fn router_with_account(
    settings: Settings, stats: Arc<Stats>, cancel: CancellationToken, core: Option<Core>,
) -> Router {
    let config = StreamableHttpServerConfig::default()
        .with_legacy_session_mode(true) // legacy initialize -> session; 2026-07-28 always stateless
        .with_json_response(true)
        .with_allowed_hosts(settings.allowed_hosts.clone())
        .enforce_origin_validation() // non-browser clients send no Origin; any present Origin -> 403
        .with_cancellation_token(cancel.clone());
    let svc_stats = stats.clone();
    let svc_core = core.clone();
    let service: StreamableHttpService<Server, LocalSessionManager> = StreamableHttpService::new(
        move || Ok(Server::new(svc_stats.clone(), svc_core.clone(), cancel.clone())),
        Default::default(),
        config,
    );
    let state = AppState { settings: Arc::new(settings), stats, core };
    Router::new()
        .nest_service("/mcp", service)
        .route("/status", get(status))
        .layer(middleware::from_fn_with_state(state.clone(), auth))
        .with_state(state)
}
