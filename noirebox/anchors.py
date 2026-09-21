from __future__ import annotations

import base64
import os
import subprocess
import tempfile

import httpx

from .chain import GENESIS, KeyPair
from .store import EventStore

GENESIS_HASH = GENESIS


def tsa_configured() -> bool:
    return bool(os.environ.get("NOIREBOX_TSA_URL"))


def _tsa_url() -> str:
    return os.environ["NOIREBOX_TSA_URL"].rstrip("/")


def build_query(head_hash: str) -> bytes:
    """Builds the timestamp request (TimeStampReq, DER) via OpenSSL.

    The DIGEST (hex) is passed directly — the TSA never sees the data;
    a 32-byte hash tells no one anything.
    """
    with tempfile.TemporaryDirectory() as tmp:
        out = f"{tmp}/req.tsq"
        proc = subprocess.run(
            ["openssl", "ts", "-query", "-digest", head_hash, "-sha256", "-cert", "-out", out],
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"openssl ts -query failed: {proc.stderr.decode()[:200]}")
        with open(out, "rb") as f:
            return f.read()


def request_token(head_hash: str, tsa_url: str | None = None) -> bytes:
    """Sends the request to the TSA, returns the TimeStampResp token (DER)."""
    url = (tsa_url or _tsa_url()).rstrip("/")
    response = httpx.post(
        f"{url}/tsa",
        content=build_query(head_hash),
        headers={"Content-Type": "application/timestamp-query"},
        timeout=10,
    )
    if response.status_code != 200:
        raise RuntimeError(f"TSA responded {response.status_code}")
    return response.content


def fetch_tsa_cert(tsa_url: str | None = None) -> str:
    """Fetches the TSA certificate (it travels INSIDE the anchor — the third
    party needs it to verify the token; TOFU + pinning possible, ADR 006)."""
    url = (tsa_url or _tsa_url()).rstrip("/")
    response = httpx.get(f"{url}/cert", timeout=10)
    response.raise_for_status()
    return response.text


def anchor_now(store: EventStore, key: KeyPair, tsa_url: str | None = None) -> dict:
    """Seals the current chain head to the TSA: token + certificate logged
    in an "anchor" event (the anchor is part of the chain)."""
    events = store.all()
    head_seq = len(events)
    head_hash = events[-1]["event_hash"] if events else GENESIS_HASH

    token = request_token(head_hash, tsa_url)
    cert_pem = fetch_tsa_cert(tsa_url)

    event = store.append(
        "anchor",
        {"head_seq": head_seq, "head_hash": head_hash,
         "tsr": base64.b64encode(token).decode("ascii"),
         "tsa_cert_pem": cert_pem},
        key,
    )
    return {
        "anchor_event_seq": event.seq,
        "anchored_head_seq": head_seq,
        "anchored_head_hash": head_hash,
        "tsr_bytes": len(token),
    }
