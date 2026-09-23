"""Reconciliation plugin v0 — invariants over the journal (issue #3).

The two-event pattern (decision ↔ outcome) is sealed by the integrator;
this plugin pairs them by correlation key and journals its findings.
The checker is itself audited: its report is sealed as a `reconciliation`
event in the same journal."""
from __future__ import annotations

from pathlib import Path

from noirebox.chain import KeyPair, verify_chain
from noirebox.reconcile import Invariant, journal_report, reconcile
from noirebox.store import EventStore


def _events(tmp_path: Path) -> tuple[EventStore, KeyPair, list[dict]]:
    """Seals two-event pairs for tests: real store, real chain."""
    store = EventStore(str(tmp_path / "recon.db"))
    key = KeyPair.load_or_create(str(tmp_path / "recon.key"))
    return store, key, []


def _pair(store: EventStore, key: KeyPair, intent: str, decision: str = "allow") -> None:
    store.append("policy_decision", {"payment_intent_id": intent,
                                     "decision": decision, "policy_version": "2.4.1"}, key)


def _outcome(store: EventStore, key: KeyPair, intent: str, status: str = "succeeded") -> None:
    store.append("provider_response", {"payment_intent_id": intent,
                                       "status": status}, key)


INV = [Invariant(name="every-decision-has-an-outcome",
                 decision_type="policy_decision",
                 outcome_type="provider_response",
                 correlation_key="payment_intent_id")]


def test_matched_pairs_produce_no_findings(tmp_path):
    store, key, _ = _events(tmp_path)
    _pair(store, key, "pi_1")
    _outcome(store, key, "pi_1")
    findings = reconcile(store.all(), INV)
    assert findings == []


def test_decision_without_outcome_is_open_gap(tmp_path):
    store, key, _ = _events(tmp_path)
    _pair(store, key, "pi_crash")
    findings = reconcile(store.all(), INV)
    assert len(findings) == 1
    assert findings[0].status == "open_gap"
    assert findings[0].correlation_id == "pi_crash"


def test_outcome_without_decision_is_orphan(tmp_path):
    store, key, _ = _events(tmp_path)
    _outcome(store, key, "pi_orphan")
    findings = reconcile(store.all(), INV)
    assert len(findings) == 1
    assert findings[0].status == "orphan_outcome"


def test_multiple_invariants_coexist(tmp_path):
    store, key, _ = _events(tmp_path)
    _pair(store, key, "pi_a")
    _outcome(store, key, "pi_a")
    invs = INV + [Invariant(name="second", decision_type="policy_decision",
                            outcome_type="provider_response",
                            correlation_key="payment_intent_id")]
    assert reconcile(store.all(), invs) == []


def test_empty_journal_has_no_findings(tmp_path):
    store, key, _ = _events(tmp_path)
    assert reconcile(store.all(), INV) == []


def test_late_outcome_flagged_beyond_within():
    """`within` turns a matched pair into a `late` finding when the outcome
    lagged beyond the window (handcrafted timestamps — the store stamps at
    now, so the window case needs controlled clocks)."""
    events = [
        {"seq": 1, "ts": "2026-09-23T10:00:00.000+00:00", "type": "policy_decision",
         "payload": {"payment_intent_id": "pi_late"}},
        {"seq": 2, "ts": "2026-09-23T10:10:00.000+00:00", "type": "provider_response",
         "payload": {"payment_intent_id": "pi_late"}},
    ]
    inv = [Invariant(name="inv", decision_type="policy_decision",
                     outcome_type="provider_response",
                     correlation_key="payment_intent_id", within_seconds=300)]
    findings = reconcile(events, inv)
    assert len(findings) == 1
    assert findings[0].status == "late"
    assert findings[0].lag_seconds == 600.0


def test_load_config_reads_json(tmp_path):
    cfg = tmp_path / "reconciliation.json"
    cfg.write_text('{"invariants": [{"name": "inv", "decision_type": "policy_decision",'
                   ' "outcome_type": "provider_response", "correlation_key": "payment_intent_id",'
                   ' "within": "5m"}]}', encoding="utf-8")
    from noirebox.reconcile import load_config
    invariants = load_config(str(cfg))
    assert invariants[0].name == "inv"
    assert invariants[0].within_seconds == 300


def test_report_is_sealed_and_chain_stays_valid(tmp_path):
    """The checker journals its findings — and the journal audits its auditor."""
    store, key, _ = _events(tmp_path)
    _pair(store, key, "pi_1")
    _outcome(store, key, "pi_1")
    _pair(store, key, "pi_gap")
    findings = reconcile(store.all(), INV)
    event = journal_report(store, key, INV, findings)
    assert event.type == "reconciliation"
    assert event.payload["total_findings"] == 1
    assert event.payload["findings"][0]["correlation_id"] == "pi_gap"
    assert verify_chain(key.public_hex(), store.all())["valid"]
