import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from noirebox.attestation import build_attestation
from noirebox.chain import KeyPair
from noirebox.store import EventStore
from verifier.verifier import verify_export


def _export(tmp_path, nb=3) -> dict:
    store = EventStore(str(tmp_path / "v.db"))
    key = KeyPair.load_or_create(str(tmp_path / "v.key"))
    for i in range(nb):
        store.append("test", {"i": i}, key)
    return {
        "format_version": 1,
        "public_key": key.public_hex(),
        "events": store.all(),
        "attestation": build_attestation(store, key),
    }


def test_valid_export_passes(tmp_path):
    report = verify_export(_export(tmp_path))
    assert report["valid"] is True
    assert report["nb_events_checked"] == 3
    assert report["errors"] == []


def test_modified_payload_fails(tmp_path):
    export = _export(tmp_path)
    export["events"][1]["payload"]["i"] = 999
    report = verify_export(export)
    assert report["valid"] is False
    assert any("invalid hash" in e["reason"] for e in report["errors"])


def test_deleted_event_fails(tmp_path):
    export = _export(tmp_path)
    del export["events"][1]
    report = verify_export(export)
    assert report["valid"] is False


def test_swapped_signature_fails(tmp_path):
    export = _export(tmp_path)
    export["events"][0]["signature"], export["events"][2]["signature"] = (
        export["events"][2]["signature"],
        export["events"][0]["signature"],
    )
    report = verify_export(export)
    assert report["valid"] is False


def test_attestation_head_mismatch_fails(tmp_path):
    export = _export(tmp_path)
    export["attestation"]["head_seq"] = 42
    report = verify_export(export)
    assert report["valid"] is False
    assert any("head_seq" in e["reason"] for e in report["errors"])


def test_missing_attestation_fails(tmp_path):
    export = _export(tmp_path)
    export.pop("attestation")
    report = verify_export(export)
    assert report["valid"] is False
    assert any("attestation missing" in e["reason"] for e in report["errors"])
