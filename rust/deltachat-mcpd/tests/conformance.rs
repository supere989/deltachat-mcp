//! P0 conformance suite: raw HTTP against a real server on a loopback port.
//! Checks the MCP 2026-07-28 Streamable HTTP MUSTs and the legacy (initialize) fallback.

use std::{
    sync::Arc,
    time::Duration,
};

use deltachat_mcpd::rpc::Core;
use serde_json::{Value, json};
use tokio_util::sync::CancellationToken;

const TOKEN: &str = "test-token-0123456789abcdef0123456789abcdef";
const MODERN: &str = "2026-07-28";

struct Srv {
    url: String,
    status_url: String,
    http: reqwest::Client,
    _cancel: CancellationToken,
}

async fn spawn() -> Srv {
    spawn_with_core(None, CancellationToken::new()).await
}

async fn spawn_with_core(core: Option<Core>, cancel: CancellationToken) -> Srv {
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    let app = deltachat_mcpd::router_with_account(
        deltachat_mcpd::Settings {
            token: TOKEN.into(),
            allowed_hosts: vec!["127.0.0.1".into(), addr.to_string()],
        },
        Arc::new(deltachat_mcpd::Stats::default()),
        cancel.clone(),
        core,
    );
    let c = cancel.clone();
    tokio::spawn(async move {
        axum::serve(listener, app).with_graceful_shutdown(c.cancelled_owned()).await.unwrap();
    });
    Srv {
        url: format!("http://{addr}/mcp"),
        status_url: format!("http://{addr}/status"),
        http: reqwest::Client::new(),
        _cancel: cancel,
    }
}

fn meta(version: &str) -> Value {
    json!({
        "io.modelcontextprotocol/protocolVersion": version,
        "io.modelcontextprotocol/clientInfo": {"name": "conformance", "version": "0"},
        "io.modelcontextprotocol/clientCapabilities": {}
    })
}

/// Parse a JSON or SSE (`data:` lines) response body into the final JSON-RPC message.
async fn body_json(resp: reqwest::Response) -> Value {
    let sse = resp
        .headers()
        .get("content-type")
        .and_then(|v| v.to_str().ok())
        .is_some_and(|v| v.starts_with("text/event-stream"));
    let text = resp.text().await.unwrap();
    if !sse {
        return serde_json::from_str(&text).unwrap_or(Value::Null);
    }
    text.lines()
        .filter_map(|l| l.strip_prefix("data:"))
        .filter_map(|d| serde_json::from_str::<Value>(d.trim()).ok())
        .filter(|v| v.get("id").is_some())
        .last()
        .unwrap_or(Value::Null)
}

impl Srv {
    fn post(&self) -> reqwest::RequestBuilder {
        self.http
            .post(&self.url)
            .bearer_auth(TOKEN)
            .header("Content-Type", "application/json")
            .header("Accept", "application/json, text/event-stream")
    }

    /// A fully conforming modern tools/call for `echo`.
    async fn modern_echo(&self, text: &str, version: &str, name_header: &str) -> reqwest::Response {
        self.post()
            .header("MCP-Protocol-Version", version)
            .header("Mcp-Method", "tools/call")
            .header("Mcp-Name", name_header)
            .json(&json!({
                "jsonrpc": "2.0", "id": 7, "method": "tools/call",
                "params": {"name": "echo", "arguments": {"text": text}, "_meta": meta(version)}
            }))
            .send()
            .await
            .unwrap()
    }

    async fn call(&self, name: &str, args: Value) -> Value {
        let r = self.post()
            .header("MCP-Protocol-Version", MODERN)
            .header("Mcp-Method", "tools/call")
            .header("Mcp-Name", name)
            .json(&json!({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                    "params": {"name": name, "arguments": args, "_meta": meta(MODERN)}}))
            .send().await.unwrap();
        assert_eq!(r.status(), 200);
        body_json(r).await["result"].clone()
    }
}

impl Drop for Srv {
    fn drop(&mut self) {
        self._cancel.cancel();
    }
}

#[tokio::test]
async fn missing_or_wrong_token_is_401() {
    let s = spawn().await;
    let r = s.http.post(&s.url).json(&json!({})).send().await.unwrap();
    assert_eq!(r.status(), 401);
    let r = s.http.get(&s.status_url).bearer_auth("wrong").send().await.unwrap();
    assert_eq!(r.status(), 401);
}

#[tokio::test]
async fn modern_tools_call_is_stateless_and_works() {
    let s = spawn().await;
    let r = s.modern_echo("hello", MODERN, "echo").await;
    assert_eq!(r.status(), 200);
    assert!(r.headers().get("mcp-session-id").is_none(), "2026-07-28 must not mint sessions");
    let v = body_json(r).await;
    assert_eq!(v["result"]["content"][0]["text"], "hello", "{v}");
}

#[tokio::test]
async fn header_body_mismatch_is_400_header_mismatch() {
    let s = spawn().await;
    let r = s.modern_echo("x", MODERN, "not-echo").await;
    assert_eq!(r.status(), 400);
    let v = body_json(r).await;
    assert_eq!(v["error"]["code"], -32020, "{v}");
}

#[tokio::test]
async fn missing_mcp_method_header_is_rejected() {
    let s = spawn().await;
    let r = s
        .post()
        .header("MCP-Protocol-Version", MODERN)
        .header("Mcp-Name", "echo")
        .json(&json!({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "echo", "arguments": {"text": "x"}, "_meta": meta(MODERN)}}))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 400);
    assert_eq!(body_json(r).await["error"]["code"], -32020);
}

#[tokio::test]
async fn unsupported_version_lists_supported() {
    let s = spawn().await;
    let r = s.modern_echo("x", "1900-01-01", "echo").await;
    assert_eq!(r.status(), 400);
    let v = body_json(r).await;
    assert_eq!(v["error"]["code"], -32022, "{v}");
    let supported = v["error"]["data"]["supported"].as_array().expect("supported list").clone();
    assert!(supported.contains(&json!(MODERN)), "{v}");
    assert!(supported.contains(&json!("2025-11-25")), "{v}");
}

#[tokio::test]
async fn server_discover_reports_versions_and_tools() {
    let s = spawn().await;
    let r = s
        .post()
        .header("MCP-Protocol-Version", MODERN)
        .header("Mcp-Method", "server/discover")
        .json(&json!({"jsonrpc": "2.0", "id": 1, "method": "server/discover", "params": {"_meta": meta(MODERN)}}))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    let v = body_json(r).await;
    let text = v.to_string();
    assert!(text.contains(MODERN) && text.contains("2025-11-25"), "{v}");
    assert!(text.contains("deltachat-mcpd"), "{v}");
}

#[tokio::test]
async fn legacy_initialize_gets_a_session_and_can_call_tools() {
    let s = spawn().await;
    let r = s
        .post()
        .header("MCP-Protocol-Version", "2025-06-18")
        .json(&json!({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "legacy", "version": "0"}}}))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    let sid = r.headers().get("mcp-session-id").expect("legacy session id").to_str().unwrap().to_string();
    let init = body_json(r).await;
    assert_eq!(init["result"]["protocolVersion"], "2025-06-18", "{init}");

    let r = s
        .post()
        .header("Mcp-Session-Id", &sid)
        .header("MCP-Protocol-Version", "2025-06-18")
        .json(&json!({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 202);

    let r = s
        .post()
        .header("Mcp-Session-Id", &sid)
        .header("MCP-Protocol-Version", "2025-06-18")
        .json(&json!({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                      "params": {"name": "echo", "arguments": {"text": "legacy-ok"}}}))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    assert_eq!(body_json(r).await["result"]["content"][0]["text"], "legacy-ok");
}

#[tokio::test]
async fn foreign_origin_is_403() {
    let s = spawn().await;
    let r = s
        .post()
        .header("Origin", "https://evil.example")
        .header("MCP-Protocol-Version", MODERN)
        .header("Mcp-Method", "tools/call")
        .header("Mcp-Name", "echo")
        .json(&json!({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "echo", "arguments": {"text": "x"}, "_meta": meta(MODERN)}}))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 403);
}

#[tokio::test]
async fn foreign_host_is_rejected() {
    let s = spawn().await;
    let r = s
        .post()
        .header("Host", "attacker.example")
        .header("MCP-Protocol-Version", MODERN)
        .header("Mcp-Method", "tools/call")
        .header("Mcp-Name", "echo")
        .json(&json!({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "echo", "arguments": {"text": "x"}, "_meta": meta(MODERN)}}))
        .send()
        .await
        .unwrap();
    assert!(r.status().is_client_error(), "got {}", r.status());
}

#[tokio::test]
async fn get_without_session_is_not_a_stream() {
    let s = spawn().await;
    let r = s
        .http
        .get(&s.url)
        .bearer_auth(TOKEN)
        .header("Accept", "text/event-stream")
        .send()
        .await
        .unwrap();
    assert!(r.status().is_client_error(), "got {}", r.status());
}

#[cfg(unix)]
#[tokio::test]
async fn modern_listen_stream_delivers_only_real_native_incoming_events() {
    let fixture = NativeFixture::new();
    let cancel = CancellationToken::new();
    let (core, native) = Core::open(fixture.config(), cancel.clone()).await.unwrap();
    let s = spawn_with_core(Some(core), cancel).await;
    let uri = "dc://events/incoming";
    let mut r = s
        .post()
        .header("MCP-Protocol-Version", MODERN)
        .header("Mcp-Method", "subscriptions/listen")
        .json(&json!({"jsonrpc": "2.0", "id": 9, "method": "subscriptions/listen", "params": {
            "_meta": meta(MODERN), "notifications": {"resourceSubscriptions": [uri, "dc://events/chat/99", "https://invalid.test"]}}}))
        .send()
        .await
        .unwrap();
    assert_eq!(r.status(), 200);
    let ct = r.headers().get("content-type").unwrap().to_str().unwrap().to_string();
    assert!(ct.starts_with("text/event-stream"), "listen must stream, got {ct}");
    assert!(r.headers().get("mcp-session-id").is_none());
    let mut seen = String::new();
    let deadline = tokio::time::Instant::now() + Duration::from_secs(5);
    while !seen.contains("notifications/subscriptions/acknowledged") {
        let bytes = tokio::time::timeout_at(deadline, r.chunk()).await.unwrap().unwrap().unwrap();
        seen.push_str(&String::from_utf8_lossy(&bytes));
    }
    assert!(!seen.contains("https://invalid.test"));
    // An idle long poll shouldn't obstruct tools or generate a timed placeholder update.
    assert_eq!(s.call("get_unread_count", json!({})).await["structuredContent"]["unread_count"], 1);
    assert!(!seen.contains("notifications/resources/updated"));
    assert!(tokio::time::timeout(Duration::from_millis(600), r.chunk()).await.is_err());
    assert_eq!(
        s.call("mark_noticed", json!({"chat_id": 12})).await["structuredContent"]["status"],
        "noticed",
    );
    while !seen.contains("notifications/resources/updated") {
        let chunk = tokio::time::timeout_at(deadline, r.chunk()).await.expect("timed out waiting for update");
        match chunk.unwrap() {
            Some(b) => seen.push_str(&String::from_utf8_lossy(&b)),
            None => break,
        }
    }
    let ack = seen.find("notifications/subscriptions/acknowledged").expect(&seen);
    let upd = seen.find("notifications/resources/updated").expect(&seen);
    assert!(ack < upd, "ack must precede the update: {seen}");
    let update = &seen[upd..];
    assert!(update.contains(uri), "{seen}");
    assert!(!update.contains("dc://events/chat/99"), "{seen}");
    let data = s.post()
        .header("MCP-Protocol-Version", MODERN)
        .header("Mcp-Method", "resources/read")
        .header("Mcp-Name", uri)
        .json(&json!({"jsonrpc": "2.0", "id": 10, "method": "resources/read", "params": {
            "_meta": meta(MODERN), "uri": uri,
        }})).send().await.unwrap();
    let response = body_json(data).await;
    let value: Value = serde_json::from_str(response["result"]["contents"][0]["text"].as_str().expect(&response.to_string())).unwrap();
    assert_eq!(value["messages"][0]["id"], 42);
    assert_eq!(value["messages"][0]["is_encrypted"], true);
    assert_eq!(value["messages"][0]["sender_addr"], "fixture@example.test");
    drop(r); // closing the stream cancels the subscription
    let v: Value = s.http.get(&s.status_url).bearer_auth(TOKEN).send().await.unwrap().json().await.unwrap();
    assert_eq!(v["stats"]["listen_opened"], 1, "{v}");
    assert_eq!(v["stats"]["listen_sent"], 1, "{v}");
    assert_eq!(v["core"]["events"]["incoming"], 1);
    assert_eq!(v["core"]["events"]["foreign"], 1);
    drop(s);
    native.await.unwrap().unwrap();
}

#[cfg(unix)]
#[tokio::test]
async fn native_tools_enforce_address_and_encryption_contract() {
    let fixture = NativeFixture::new();
    let cancel = CancellationToken::new();
    let (core, native) = Core::open(fixture.config(), cancel.clone()).await.unwrap();
    let s = spawn_with_core(Some(core), cancel).await;
    let r = s.call("list_chats", json!({})).await;
    assert_eq!(r["structuredContent"]["chats"][0]["addr"], "fixture@example.test");
    let r = s.call("get_messages", json!({"chat_id": 12, "limit": 1})).await;
    assert_eq!(r["structuredContent"]["messages"][0]["id"], 42);
    let r = s.call("get_unread_digest", json!({})).await;
    assert_eq!(r["structuredContent"]["chats"][0]["messages"][0]["id"], 42);
    let r = s.call("send_message", json!({"addr": "no-key@example.test", "text": "reply"})).await;
    assert_eq!(r["isError"], true);
    assert!(r["content"][0]["text"].as_str().unwrap().contains("SecureJoin"));
    let r = s.call("send_message", json!({
        "addr": "ambiguous@example.test", "text": "reply",
    })).await;
    assert_eq!(r["isError"], true);
    assert!(r["content"][0]["text"].as_str().unwrap().contains("Multiple key contacts"));
    let r = s.call("send_message", json!({
        "chat_id": 13, "text": "reply", "require_encryption": true,
    })).await;
    assert_eq!(r["isError"], true);
    let r = s.call("send_message", json!({
        "addr": "mailto:Fixture@Example.Test", "text": "reply", "require_encryption": true,
    })).await;
    assert_eq!(r["structuredContent"]["message_id"], 43);
    assert_eq!(r["structuredContent"]["status"], "queued");
    let v: Value = s.http.get(&s.status_url).bearer_auth(TOKEN)
        .send().await.unwrap().json().await.unwrap();
    assert_eq!(v["core"]["by_method"]["misc_send_text_message"], 1);
    assert_eq!(v["stats"]["by_tool"]["send_message"]["failed"], 3);
    drop(s);
    native.await.unwrap().unwrap();
}

#[cfg(unix)]
#[tokio::test]
async fn reconnects_native_process_without_replaying_unconfirmed_send() {
    let fixture = NativeFixture::new();
    let cancel = CancellationToken::new();
    let (core, native) = Core::open(fixture.config(), cancel.clone()).await.unwrap();
    let s = spawn_with_core(Some(core), cancel).await;
    let r = s.call("send_message", json!({"chat_id": 12, "text": "disconnect"})).await;
    assert_eq!(r["isError"], true);
    assert!(r["content"][0]["text"].as_str().unwrap().contains("did not confirm"));
    let v = tokio::time::timeout(Duration::from_secs(8), async {
        loop {
            let status: Value = s.http.get(&s.status_url).bearer_auth(TOKEN)
                .send().await.unwrap().json().await.unwrap();
            if status["core"]["restarts"] == 1 && status["core"]["ready"] == true {
                break status;
            }
            tokio::time::sleep(Duration::from_millis(60)).await;
        }
    }).await.unwrap();
    assert_eq!(v["core"]["by_method"]["misc_send_text_message"], 1);
    assert_eq!(v["core"]["unknown_disposition"], 1);
    assert_eq!(v["core"]["events"]["gap"], 1);
    assert_eq!(s.call("get_unread_count", json!({})).await["structuredContent"]["unread_count"], 1);
    drop(s);
    native.await.unwrap().unwrap();
}

#[cfg(unix)]
struct NativeFixture(std::path::PathBuf);

#[cfg(unix)]
impl NativeFixture {
    fn new() -> Self {
        use std::{fs, os::unix::fs::PermissionsExt};
        let serial = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos();
        let dir = std::env::temp_dir().join(format!("deltachat-mcp-test-{}-{serial}", std::process::id()));
        fs::create_dir(&dir).unwrap();
        fs::write(dir.join("accounts.toml"), "").unwrap();
        let program = dir.join("core");
        fs::write(&program, include_str!("fixtures/core.py")).unwrap();
        fs::set_permissions(&program, fs::Permissions::from_mode(0o700)).unwrap();
        Self(dir)
    }

    fn config(&self) -> deltachat_mcpd::rpc::Config {
        deltachat_mcpd::rpc::Config {
            executable: self.0.join("core"),
            accounts_dir: self.0.clone(),
            account_id: 1,
            token_env: None,
        }
    }
}

#[cfg(unix)]
impl Drop for NativeFixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_file(self.0.join("core"));
        let _ = std::fs::remove_file(self.0.join("accounts.toml"));
        let _ = std::fs::remove_dir(&self.0);
    }
}

#[tokio::test]
async fn status_counts_eras_sessions_and_statuses() {
    let s = spawn().await;
    s.modern_echo("m", MODERN, "echo").await; // modern, stateless, 200
    let r = s
        .post()
        .header("MCP-Protocol-Version", "2025-06-18")
        .json(&json!({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "legacy", "version": "0"}}}))
        .send()
        .await
        .unwrap();
    let sid = r.headers().get("mcp-session-id").unwrap().to_str().unwrap().to_string();
    s.post()
        .header("Mcp-Session-Id", &sid)
        .header("MCP-Protocol-Version", "2025-06-18")
        .json(&json!({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        .send()
        .await
        .unwrap();
    s.post().header("Origin", "https://evil.example").header("MCP-Protocol-Version", MODERN)
        .json(&json!({})).send().await.unwrap(); // 403
    s.http.post(&s.url).send().await.unwrap(); // 401
    let v: Value = s.http.get(&s.status_url).bearer_auth(TOKEN).send().await.unwrap().json().await.unwrap();
    let st = &v["stats"];
    assert_eq!(st["by_version"][MODERN], 2, "{v}");
    assert_eq!(st["by_version"]["2025-06-18"], 2, "{v}");
    assert_eq!(st["with_session"], 1, "{v}");
    assert_eq!(st["by_status"]["403"], 1, "{v}");
    assert_eq!(st["by_status"]["401"], 1, "{v}");
    assert_eq!(st["by_status"]["202"], 1, "{v}");
    assert!(st["by_status"]["200"].as_u64().unwrap() >= 2, "{v}");
}

#[tokio::test]
async fn status_counts_requests_and_rejects() {
    let s = spawn().await;
    s.modern_echo("a", MODERN, "echo").await;
    s.http.post(&s.url).send().await.unwrap(); // unauthenticated
    let v: Value = s.http.get(&s.status_url).bearer_auth(TOKEN).send().await.unwrap().json().await.unwrap();
    assert_eq!(v["mcp_revision_checked"], MODERN);
    assert!(v["stats"]["mcp_requests"].as_u64().unwrap() >= 1, "{v}");
    assert_eq!(v["stats"]["auth_rejected"], 1, "{v}");
    assert_eq!(v["stats"]["tool_ok"], 1, "{v}");
}
