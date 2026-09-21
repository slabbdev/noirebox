import base64
import socket
import subprocess
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from noirebox.anchors import build_query, request_token
from noirebox.attestation import build_attestation
from noirebox.chain import KeyPair
from noirebox.main import create_app
from noirebox.store import EventStore

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(
    subprocess.run(["which", "openssl"], capture_output=True).returncode != 0,
    reason="openssl not available",
)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def tsa_url(tmp_path_factory):
    """Generate the TSA material and start the local TSA server once for all tests."""
    material = tmp_path_factory.mktemp("tsa_material")
    gen = subprocess.run(
        ["bash", str(ROOT / "tsa" / "gen_tsa.sh"), str(material)],
        capture_output=True,
    )
    assert gen.returncode == 0, gen.stderr.decode()
    port = _free_port()
    server = subprocess.Popen(
        [sys_executable(), str(ROOT / "tsa" / "tsa_server.py"),
         "--material", str(material), "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            import httpx

            httpx.get(f"{base}/cert", timeout=1)
            break
        except Exception:
            time.sleep(0.05)
    yield base
    server.terminate()


def sys_executable() -> str:
    import sys

    return sys.executable


@pytest.fixture()
def client_tsa(tsa_url, tmp_path, monkeypatch):
    """App with TSA configured + auth disabled."""
    monkeypatch.setenv("NOIREBOX_TSA_URL", tsa_url)
    return TestClient(create_app(str(tmp_path / "anchor.db")))


def test_anchor_503_without_tsa(tmp_path, monkeypatch):
    monkeypatch.delenv("NOIREBOX_TSA_URL", raising=False)
    client = TestClient(create_app(str(tmp_path / "notsa.db")))
    r = client.post("/api/v1/anchors")
    assert r.status_code == 503
    assert "NOIREBOX_TSA_URL" in r.json()["detail"]


def test_anchor_seals_chain_head(client_tsa):
    client_tsa.post("/api/v1/events", json={"type": "llm_call", "payload": {"prompt": "résume"}})
    r = client_tsa.post("/api/v1/anchors")
    assert r.status_code == 201
    body = r.json()
    assert body["anchored_head_seq"] == 1
    assert body["anchor_event_seq"] == 2


def test_export_with_anchor_verifies_as_third_party(client_tsa):
    """The full auditor scenario: chain + TSA token + certificate."""
    client_tsa.post("/api/v1/events", json={"type": "llm_call", "payload": {"p": 1}})
    client_tsa.post("/api/v1/anchors")
    export = client_tsa.get("/api/v1/export").json()

    from verifier.verifier import verify_export

    report = verify_export(export)
    assert report["valid"] is True, report["errors"]
    assert report["anchors_checked"] == 1


def test_insider_regeneration_is_caught_by_anchor(tsa_url, tmp_path):
    """THE threat-model test: an insider with the PRIVATE key regenerates the
    whole chain (consistent fingerprints, real signatures). The chain becomes
    "valid"... but the old TSA token does not cover the new head.
    This is the only control that exposes it."""

    h_old = "ab" * 32
    token = request_token(h_old, tsa_url)
    cert_pem = __import__("httpx").get(f"{tsa_url}/cert", timeout=5).text



    key = KeyPair.generate()
    store = EventStore(str(tmp_path / "forged.db"))
    store.append("llm_output", {"compte_rendu": "FALSIFIÉ, chaîne régénérée"}, key)
    h_new = store.all()[-1]["event_hash"]
    store.append("anchor", {"head_seq": 2, "head_hash": h_new,
                            "tsr": base64.b64encode(token).decode("ascii"),
                            "tsa_cert_pem": cert_pem}, key)
    export = {"format_version": 1, "public_key": key.public_hex(),
              "events": store.all(), "attestation": build_attestation(store, key)}

    from verifier.verifier import verify_export

    report = verify_export(export)
    assert report["valid"] is False
    assert any("anchor" in e["reason"] for e in report["errors"])


def test_query_contains_only_a_hash_not_data():
    """The TSA never sees the data: the request only carries a digest."""
    query = build_query("cd" * 32)
    assert len(query) < 200

    assert query[0] == 0x30
