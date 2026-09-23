"""The PDF attestation is an optional extra (`noirebox[pdf]`): without
reportlab the route answers a clean 501 with the install hint — never a
traceback. The dev environment ships with reportlab, so the 200 path is
covered by test_auth_pdf.py; this file covers the degraded path honestly.
"""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

from noirebox.main import create_app


def _client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(str(tmp_path / "pdf.db")))


def test_pdf_route_without_reportlab_answers_501_with_hint(tmp_path, monkeypatch):
    """Simulates a core-only install: every reportlab module is hidden."""
    for name in [m for m in sys.modules if m.startswith("reportlab")]:
        monkeypatch.delitem(sys.modules, name, raising=False)
    monkeypatch.setitem(sys.modules, "reportlab", None)
    monkeypatch.setitem(sys.modules, "reportlab.lib", None)
    monkeypatch.setitem(sys.modules, "reportlab.lib.pagesizes", None)
    monkeypatch.setitem(sys.modules, "reportlab.lib.units", None)
    monkeypatch.setitem(sys.modules, "reportlab.pdfgen", None)

    client = _client(tmp_path)
    r = client.get("/api/v1/attestation.pdf")
    assert r.status_code == 501
    assert "noirebox[pdf]" in r.json()["error"]
    assert "pip install" in r.json()["error"]


def test_pdf_route_with_reportlab_serves_the_document(tmp_path):
    """The full install (dev/`noirebox[pdf]`) serves the real attestation."""
    client = _client(tmp_path)
    client.post("/api/v1/events", json={"type": "llm_call", "payload": {"model": "demo"}})
    r = client.get("/api/v1/attestation.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
