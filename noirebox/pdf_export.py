from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .attestation import build_attestation
from .chain import KeyPair
from .store import EventStore

INK = (0.06, 0.07, 0.09)
RED = (0.88, 0.02, 0.0)
GREY = (0.45, 0.5, 0.55)


def attestation_pdf(store: EventStore, key: KeyPair) -> bytes:
    """Builds the attestation PDF (bytes — FastAPI serves it as-is)."""
    att = build_attestation(store, key)
    evidence_id = f"NBX-{att['head_hash'][:16].upper()}"

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pdfVersion=(1, 4))
    width, height = A4
    margin = 22 * mm
    c.setTitle(f"NoireBox - Journal Integrity Attestation - {evidence_id}")
    c.setAuthor("NoireBox")
    c.setSubject("Technical integrity attestation of an AI-agent journal")
    c.setKeywords("NoireBox, GDPR, AI Act, audit, integrity, A4, attestation")
    c.setCreator("NoireBox API")


    c.setFillColorRGB(*RED)
    c.rect(0, height - 14 * mm, width, 14 * mm, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, height - 9.5 * mm, "NOIREBOX — JOURNAL INTEGRITY ATTESTATION")


    y = height - 32 * mm
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y, "Tamper-proof journal for AI agents")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    c.setFillColorRGB(*GREY)
    generated = datetime.fromisoformat(att["generated_at"]).astimezone(timezone.utc)
    c.drawString(margin, y, f"Issued on {generated.strftime('%d/%m/%Y at %H:%M UTC')} — Algorithm: {att['algo']}")
    y -= 6 * mm
    c.setFont("Helvetica", 8.5)
    c.drawString(margin, y, f"Evidence ID: {evidence_id} — Format: PDF 1.4 / A4")


    y -= 14 * mm
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Chain status")
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    rows = [
        ("Chain height (sealed events)", str(att["head_seq"])),
        ("Head fingerprint (SHA-256)", att["head_hash"]),
        ("Validity at time of issuance", "INTACT — signature verified" if att["chain_valid"] else "BROKEN"),
    ]
    for label, value in rows:
        c.setFillColorRGB(*GREY)
        c.drawString(margin + 2 * mm, y, label)
        c.setFillColorRGB(*INK)

        shown = value if len(value) <= 56 else value[:53] + "…"
        c.setFont("Courier-Bold", 8.4)
        c.drawRightString(width - margin, y, shown)
        c.setFont("Helvetica", 10)
        y -= 6.5 * mm


    y -= 4 * mm
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Event breakdown")
    y -= 7 * mm
    c.setFont("Helvetica", 10)
    for type_, count in sorted(att["event_types"].items()):
        c.setFillColorRGB(*GREY)
        c.drawString(margin + 2 * mm, y, type_)
        c.setFillColorRGB(*INK)
        c.drawRightString(width - margin, y, str(count))
        y -= 6 * mm


    y -= 3 * mm
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Intended use")
    y -= 6 * mm
    c.setFont("Helvetica", 8.5)
    regulatory_lines = [
        "Internal technical audit record — keep with the corresponding JSON export.",
        "References: GDPR (EU) 2016/679 and AI Act (EU) 2024/1689, as applicable.",
        "This document evidences the observed integrity; it is neither a certification nor legal advice.",
    ]
    for line in regulatory_lines:
        c.setFillColorRGB(*GREY if line.startswith("References") else INK)
        c.drawString(margin + 2 * mm, y, line)
        y -= 4.5 * mm


    y -= 4 * mm
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(margin, y, "Cryptographic proof")
    y -= 7 * mm
    c.setFont("Helvetica", 9)
    for label, value in [
        ("Instance public key (Ed25519)", att["public_key"]),
        ("Signature of this attestation", att["signature"]),
    ]:
        c.setFillColorRGB(*GREY)
        c.drawString(margin + 2 * mm, y, label)
        y -= 4.5 * mm
        c.setFillColorRGB(*INK)
        c.setFont("Courier", 7.6)

        for i in range(0, len(value), 62):
            c.drawString(margin + 2 * mm, y, value[i : i + 62])
            y -= 3.8 * mm
        c.setFont("Helvetica", 9)
        y -= 2 * mm


    y -= 2 * mm
    c.setFillColorRGB(*RED)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "How to verify this attestation without trusting the issuer")
    y -= 6 * mm
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica", 9.5)
    steps = [
        "1. Get the full export from the issuer (GET /api/v1/export).",
        "2. Run the standalone verifier:  python verifier/verifier.py export.json",
        "3. The verifier recomputes the whole chain offline:",
        "   - exit 0: journal intact, the attestation above is confirmed;",
        "   - exit 1: tampering detected, with the exact event number.",
        "No identifying information is required. Verification never contacts",
        "a server: the proof is arithmetic, not a promise.",
    ]
    for step in steps:
        c.drawString(margin + 2 * mm, y, step)
        y -= 5 * mm


    c.setFillColorRGB(*GREY)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(margin, 14 * mm,
                 "NoireBox — the black box for AI agents. The core is open source (MIT) and verification stays free forever.")
    c.drawString(margin, 10 * mm,
                 "This document attests to the state of the journal at the time of issuance; it is not a third-party certification.")

    c.showPage()
    c.save()
    return buf.getvalue()
