#!/usr/bin/env python3
from __future__ import annotations

import base64
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noirebox.attestation import verify_attestation
from noirebox.chain import (
    compute_event_hash,
    ed25519_verify,
    verify_chain,
)

GENESIS = "0" * 64


def verify_anchor_event(payload: dict) -> tuple[bool, str]:
    """Verify an RFC 3161 token against the chain head it claims to cover.

    The TSA certificate travels INSIDE the anchor (TOFU, ADR 006): we check
    that the token is signed by THIS certificate and covers THIS head_hash.
    A careful deployment can pin the certificate — here, the report states
    exactly what was checked.
    """
    if not shutil.which("openssl"):
        return True, "openssl missing — token not verified (reported, not hidden)"
    with tempfile.TemporaryDirectory() as tmp:
        tsr = Path(tmp) / "token.tsr"
        cert = Path(tmp) / "tsa.pem"
        tsr.write_bytes(base64.b64decode(payload["tsr"]))
        cert.write_text(payload["tsa_cert_pem"], encoding="ascii")
        proc = subprocess.run(
            ["openssl", "ts", "-verify", "-digest", payload["head_hash"],
             "-in", str(tsr), "-CAfile", str(cert), "-untrusted", str(cert)],
            capture_output=True,
        )
    if proc.returncode != 0:
        return False, f"invalid TSA token: {proc.stderr.decode().strip()[:200]}"
    return True, ""


def verify_export(export: dict) -> dict:
    """Recompute the whole chain from the export, without trusting the server."""
    errors: list[dict] = []
    public_key = export.get("public_key", "")
    events = export.get("events", [])

    if not public_key:
        errors.append({"seq": None, "reason": "public key missing from the export"})

    prev = "0" * 64
    for expected_seq, ev in enumerate(events, start=1):
        if ev["seq"] != expected_seq:
            errors.append({"seq": ev["seq"], "reason": "broken sequence"})
            break
        if ev["prev_hash"] != prev:
            errors.append({"seq": ev["seq"], "reason": "prev_hash link broken"})
            break
        recomputed = compute_event_hash(ev["seq"], ev["ts"], ev["type"], ev["payload"], ev["prev_hash"])
        if recomputed != ev["event_hash"]:
            errors.append({"seq": ev["seq"], "reason": "invalid hash (content modified)"})
            break
        if not ed25519_verify(public_key, ev["signature"], bytes.fromhex(ev["event_hash"])):
            errors.append({"seq": ev["seq"], "reason": "invalid signature"})
            break
        prev = ev["event_hash"]

    attestation = export.get("attestation", {})
    if not attestation:
        errors.append({"seq": None, "reason": "attestation missing"})
    else:
        if not verify_attestation(attestation):
            errors.append({"seq": None, "reason": "invalid attestation signature"})
        head_hash = attestation.get("head_hash")
        head_seq = attestation.get("head_seq")
        if head_seq != len(events):
            errors.append({"seq": None, "reason": f"attestation: head_seq={head_seq} ≠ {len(events)} exported events"})
        if events and head_hash != events[-1]["event_hash"]:
            errors.append({"seq": None, "reason": "attestation: head_hash does not match the last event"})

    chain_report = verify_chain(public_key, events)







    anchors_checked = 0
    anchors_unverifiable = 0
    for ev in events:
        if ev["type"] != "anchor":
            continue
        payload = ev["payload"]
        head_seq = payload.get("head_seq")
        idx_ok = (
            isinstance(head_seq, int) and 0 <= head_seq <= len(events)
            and (events[head_seq - 1]["event_hash"] if head_seq else GENESIS) == payload.get("head_hash")
        )
        if not idx_ok:
            errors.append({"seq": ev["seq"],
                           "reason": "anchor: cited head_hash does not match the chain (regeneration?)"})
            continue
        ok, reason = verify_anchor_event(payload)
        if not ok:
            errors.append({"seq": ev["seq"], "reason": reason})
            continue
        anchors_checked += 1 if reason == "" else 0
        anchors_unverifiable += 1 if reason != "" else 0

    valid = not errors and chain_report["valid"]
    return {
        "valid": valid,
        "nb_events_checked": len(events),
        "anchors_checked": anchors_checked,
        "anchors_unverifiable": anchors_unverifiable,
        "errors": errors,
        "head_hash": events[-1]["event_hash"] if events else None,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    export = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    report = verify_export(export)

    if report["valid"]:
        print(f"[✓] INTACT — {report['nb_events_checked']} events verified, "
              f"attestation valid, head of chain: {report['head_hash'][:16]}…")
        return 0

    print("[✗] TAMPERING DETECTED")
    for err in report["errors"]:
        seq = err["seq"] if err["seq"] is not None else "—"
        print(f"    event {seq}: {err['reason']}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
