use std::{future::IntoFuture, path::PathBuf, sync::Arc, time::Duration};

use anyhow::{Context, bail};
use deltachat_mcpd::rpc::{Config, Core};
use tokio::{net::TcpListener, task::JoinHandle, time::timeout};
use tokio_util::sync::CancellationToken;

const NATIVE_FAILURE_DRAIN: Duration = Duration::from_secs(5);

/// Usage: deltachat-mcpd --listen 127.0.0.1:9122
///        (--token-file CREDENTIAL_PATH | --token-env VAR)
///        --rpc-bin PATH --accounts-dir PATH --account-id ID
///        [--allowed-host HOST[:PORT]]...
/// `--token-env` reads the token from an environment variable (e.g. supplied by `kwsecret exec`).
/// Omitting the three account flags enables HTTP diagnostics only.
#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(tracing_subscriber::EnvFilter::try_from_default_env().unwrap_or_else(|_| "info".into()))
        .init();
    let mut listen = None;
    let mut token_file = None;
    let mut token_env = None;
    let mut hosts = Vec::new();
    let mut rpc_bin = None;
    let mut accounts_dir = None;
    let mut account_id = None;
    let mut args = std::env::args().skip(1);
    while let Some(a) = args.next() {
        match a.as_str() {
            "--listen" => listen = args.next(),
            "--token-file" => token_file = args.next(),
            "--token-env" => token_env = args.next(),
            "--allowed-host" => hosts.extend(args.next()),
            "--rpc-bin" => rpc_bin = Some(PathBuf::from(args.next().context("--rpc-bin requires PATH")?)),
            "--accounts-dir" => accounts_dir = Some(PathBuf::from(args.next().context("--accounts-dir requires PATH")?)),
            "--account-id" => account_id = Some(args.next().context("--account-id requires ID")?
                .parse::<u32>().context("--account-id requires a positive integer")?),
            other => bail!("unknown argument {other}"),
        }
    }
    let listen = listen.context("--listen ADDR:PORT is required")?;
    let (token, source) = match (token_file, token_env.as_ref()) {
        (Some(f), None) => (
            std::fs::read_to_string(&f).with_context(|| format!("reading token file {f}"))?,
            f,
        ),
        (None, Some(v)) => (
            std::env::var(&v).with_context(|| format!("environment variable {v} is not set"))?,
            format!("${v}"),
        ),
        _ => bail!("exactly one of --token-file PATH or --token-env VAR is required"),
    };
    let token = token.trim().to_string();
    if token.len() < 32 {
        bail!("token from {source} is shorter than 32 characters");
    }
    if hosts.is_empty() {
        let host = listen.rsplit_once(':').map(|(h, _)| h).unwrap_or(&listen).to_string();
        hosts = vec![host, listen.clone()];
    }
    let cancel = CancellationToken::new();
    let listener = TcpListener::bind(&listen).await.with_context(|| format!("bind {listen}"))?;
    let config = match (rpc_bin, accounts_dir, account_id) {
        (Some(executable), Some(accounts_dir), Some(account_id)) => Some(Config {
            executable, accounts_dir, account_id, token_env,
        }),
        (None, None, None) => None,
        _ => bail!("--rpc-bin, --accounts-dir, and --account-id must be set together"),
    };
    let listen_cancel = cancel.clone();
    #[cfg(unix)]
    let mut terminate = tokio::signal::unix::signal(tokio::signal::unix::SignalKind::terminate())?;
    let signals = tokio::spawn(async move {
        #[cfg(unix)]
        tokio::select! {
            _ = terminate.recv() => {},
            _ = tokio::signal::ctrl_c() => {},
        }
        #[cfg(not(unix))]
        let _ = tokio::signal::ctrl_c().await;
        listen_cancel.cancel();
    });
    let (core, native) = match config {
        Some(config) => {
            let (core, native) = Core::open(config, cancel.clone()).await?;
            (Some(core), Some(native))
        }
        None => (None, None),
    };
    let app = deltachat_mcpd::router_with_account(
        deltachat_mcpd::Settings { token, allowed_hosts: hosts },
        Arc::new(deltachat_mcpd::Stats::default()),
        cancel.clone(),
        core,
    );
    tracing::info!("deltachat-mcpd listening on {listen} (/mcp, /status)");
    let result = serve(listener, app, cancel, native).await;
    signals.abort();
    result
}

async fn serve(
    listener: TcpListener,
    app: axum::Router,
    cancel: CancellationToken,
    native: Option<JoinHandle<anyhow::Result<()>>>,
) -> anyhow::Result<()> {
    let http = axum::serve(listener, app)
        .with_graceful_shutdown(cancel.clone().cancelled_owned())
        .into_future();
    tokio::pin!(http);
    let Some(mut native) = native else {
        return Ok(http.await?);
    };

    tokio::select! {
        result = &mut http => {
            cancel.cancel();
            native.await.context("native Delta Chat supervisor task failed")??;
            result?;
        }
        result = &mut native => {
            cancel.cancel();
            let failure = result.context("native Delta Chat supervisor task failed").and_then(|r| r);
            if failure.is_err() {
                if timeout(NATIVE_FAILURE_DRAIN, &mut http).await.is_err() {
                    tracing::warn!("HTTP drain expired after native Delta Chat failure");
                }
                return failure;
            }
            http.await?;
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn native_failure_stops_http_and_returns_an_error() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let address = listener.local_addr().unwrap();
        let app = axum::Router::new().route("/status", axum::routing::get(|| async { "ready" }));
        let cancel = CancellationToken::new();
        let (fail, failed) = tokio::sync::oneshot::channel::<()>();
        let native = tokio::spawn(async move {
            failed.await.unwrap();
            bail!("Delta Chat core restart limit reached");
        });
        let task = tokio::spawn(serve(listener, app, cancel.clone(), Some(native)));
        let response = timeout(Duration::from_secs(3), reqwest::get(format!("http://{address}/status")))
            .await.unwrap().unwrap();
        assert!(response.status().is_success());
        drop(response);

        fail.send(()).unwrap();
        let failure = timeout(Duration::from_secs(3), task).await.unwrap().unwrap().unwrap_err();
        assert!(failure.to_string().contains("restart limit reached"));
        assert!(cancel.is_cancelled());
        assert!(tokio::net::TcpStream::connect(address).await.is_err());
    }
}
