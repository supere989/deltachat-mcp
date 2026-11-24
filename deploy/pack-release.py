"""Package tested release inputs without embedding installation state."""

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tomllib
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ASSET = "deltachat-mcpd-linux-x86_64.tar.gz"
PROTOCOL = "2026-07-28"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True, cwd=ROOT).strip()


def package(daemon: Path, wheel: Path, output: Path, tag: str | None) -> None:
    if command("uname", "-sm") != "Linux x86_64":
        raise ValueError("the archive is for x86-64 Linux")
    with (ROOT / "rust/deltachat-mcpd/Cargo.toml").open("rb") as metadata:
        version = tomllib.load(metadata)["package"]["version"]
    if tag is not None and tag != f"deltachat-mcpd-v{version}":
        raise ValueError("release tag must match the Rust package version")

    native_lock = (ROOT / "deploy/native-core.lock").read_text()
    native_version, digest = re.search(
        r"deltachat-rpc-server==([\d.]+).*?--hash=sha256:([0-9a-f]{64})", native_lock, re.S,
    ).groups()
    if sha256(wheel.read_bytes()) != digest:
        raise ValueError("Delta Chat Core wheel does not match deploy/native-core.lock")

    files = {"bin/deltachat-mcpd": (daemon.read_bytes(), 0o755)}
    with ZipFile(wheel) as archive:
        files["bin/deltachat-rpc-server"] = (archive.read("deltachat_rpc_server/deltachat-rpc-server"), 0o755)
        files["licenses/native/LICENSE"] = (archive.read("deltachat_rpc_server/LICENSE"), 0o644)
        for name in archive.namelist():
            path = PurePosixPath(name)
            if path.name.startswith(("LICENSE", "COPYING", "NOTICE")) and not name.endswith("/"):
                files.setdefault(f"licenses/native/{path.name}", (archive.read(name), 0o644))

    for name in ("deltachat-mcpd@.service", "hermes-deltachat-mcp@.service", "run-instance"):
        files[f"systemd/{name}"] = ((ROOT / "deploy/systemd" / name).read_bytes(), 0o644)
    for name in ("__init__.py", "adapter.py", "plugin.yaml", "settings.py"):
        path = f"hermes/deltachat_mcp/{name}"
        files[path] = ((ROOT / path).read_bytes(), 0o644)
    for name in ("LICENSE", "deploy/README.md", "deploy/native-core.lock"):
        files[name] = ((ROOT / name).read_bytes(), 0o644)

    commit = command("git", "rev-parse", "HEAD")
    mtime = int(command("git", "show", "-s", "--format=%ct", "HEAD"))
    source = f"https://github.com/chatmail/core/tree/v{native_version}"
    files["licenses/native/SOURCE.md"] = (
        f"Unmodified Delta Chat RPC executable from the PyPI {native_version} wheel.\n"
        f"Corresponding source and license are available at {source}.\n".encode(),
        0o644,
    )
    manifest = {
        "tag": tag,
        "commit": commit,
        "daemon_version": version,
        "architecture": "x86_64-unknown-linux-gnu",
        "rustc": command("rustc", "--version"),
        "mcp_revision": PROTOCOL,
        "hermes_transport": {"python": "3.11", "mcp_sdk": "2.0.0", "httpx2": "2.7.0"},
        "native_core": {"version": native_version, "wheel_sha256": digest, "source": source},
        "files": {name: sha256(data) for name, (data, _) in sorted(files.items())},
    }
    files["release.json"] = ((json.dumps(manifest, indent=2) + "\n").encode(), 0o644)
    output.mkdir(parents=True, exist_ok=True)
    artifact = output / ASSET
    with artifact.open("xb") as raw, gzip.GzipFile(fileobj=raw, filename="", mtime=0) as zipstream:
        with tarfile.open(fileobj=zipstream, mode="w|") as archive:
            for name, (data, mode) in sorted(files.items()):
                entry = tarfile.TarInfo(name)
                entry.mode, entry.size, entry.mtime = mode, len(data), mtime
                archive.addfile(entry, io.BytesIO(data))
    with artifact.with_suffix(".gz.sha256").open("x") as checksum:
        checksum.write(f"{sha256(artifact.read_bytes())}  {ASSET}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daemon", type=Path, required=True)
    parser.add_argument("--native-wheel", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tag")
    args = parser.parse_args()
    package(args.daemon, args.native_wheel, args.output, args.tag)
