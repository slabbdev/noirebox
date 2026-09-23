"""Reconciliation plugin (v0) — business invariants over the journal.

The journal proves integrity and order. It deliberately does NOT know what a
"missing half" is: that knowledge is domain-specific, and this plugin is where
it lives — the same plugin pattern as the guardrail (journal domain-blind,
domain knowledge pluggable). Community request: issue #3.

The pattern it checks (two-event flow, e.g. payouts):

    policy_decision (allow/hold/deny + reason_code + policy_version)
    provider_response (provider status)
    ... linked by a correlation key: payment_intent_id

For each invariant, the checker pairs decision/outcome events by the
correlation key and reports:

    matched          — both sealed (flagged `late` if the outcome lagged
                       beyond the invariant's `within` window)
    open_gap         — decision sealed, no outcome ever recorded
                       (the process died before the provider call — the gap
                       itself is evidence, not an error to hide)
    orphan_outcome   — outcome sealed with no decision in front of it
                       (a retry skipped the journaling step)

Every finding is evidence, not an action: the plugin never repairs, it
reports. And the report is sealed into the journal like any event — the
journal's auditor is audited by the journal it audits.

v0 boundaries (feedback on issue #3 decides what comes next):
- config is JSON (stdlib) — YAML would add a dependency for syntax
- one correlation key per invariant, first event wins on duplicates
- `within` supports "Ns", "Nm", "Nh" strings or plain seconds (int)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

_DURATION = re.compile(r"^\s*(\d+)\s*([smh]?)\s*$", re.IGNORECASE)
_UNITS = {"s": 1, "m": 60, "h": 3600}


@dataclass(frozen=True)
class Invariant:
    """One business invariant: every decision_type must get its outcome_type."""

    name: str
    decision_type: str
    outcome_type: str
    correlation_key: str
    within_seconds: int | None = None


@dataclass(frozen=True)
class Finding:
    """One reconciliation result — evidence sealed into the journal."""

    invariant: str
    status: str                    # matched | open_gap | orphan_outcome | late
    correlation_id: str
    decision_seq: int | None = None
    outcome_seq: int | None = None
    lag_seconds: float | None = None


def parse_duration(value: int | str | None) -> int | None:
    """`"5m"` → 300 · `"90s"` → 90 · `"1h"` → 3600 · `90` → 90 · None → None."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    m = _DURATION.match(value)
    if not m:
        raise ValueError(f"invalid duration: {value!r} (expected Ns, Nm or Nh)")
    return int(m.group(1)) * _UNITS[m.group(2).lower()]


def load_config(path: str) -> list[Invariant]:
    """Loads invariants from a JSON file (see reconciliation.example.json)."""
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    return [
        Invariant(
            name=inv["name"],
            decision_type=inv["decision_type"],
            outcome_type=inv["outcome_type"],
            correlation_key=inv["correlation_key"],
            within_seconds=parse_duration(inv.get("within")),
        )
        for inv in cfg.get("invariants", [])
    ]


def _ts(event: dict) -> datetime:
    return datetime.fromisoformat(event["ts"])


def reconcile(events: list[dict], invariants: list[Invariant]) -> list[Finding]:
    """Runs every invariant over the events, returns the findings.

    `events` is what `store.all()` returns — or any handcrafted list with
    the same shape (seq, ts, type, payload). First occurrence wins on
    duplicate correlation ids: the original decision, the first response.
    """
    findings: list[Finding] = []
    for inv in invariants:
        decisions: dict[str, dict] = {}
        outcomes: dict[str, dict] = {}
        for e in events:
            key = e.get("payload", {}).get(inv.correlation_key)
            if key is None:
                continue
            key = str(key)
            if e.get("type") == inv.decision_type:
                decisions.setdefault(key, e)
            elif e.get("type") == inv.outcome_type:
                outcomes.setdefault(key, e)

        for cid, decision in decisions.items():
            outcome = outcomes.get(cid)
            if outcome is None:
                findings.append(Finding(inv.name, "open_gap", cid,
                                        decision_seq=decision["seq"]))
            elif inv.within_seconds is not None:
                lag = (_ts(outcome) - _ts(decision)).total_seconds()
                if lag > inv.within_seconds:
                    findings.append(Finding(inv.name, "late", cid,
                                            decision_seq=decision["seq"],
                                            outcome_seq=outcome["seq"],
                                            lag_seconds=lag))
        for cid, outcome in outcomes.items():
            if cid not in decisions:
                findings.append(Finding(inv.name, "orphan_outcome", cid,
                                        outcome_seq=outcome["seq"]))
    return findings


def journal_report(store, key, invariants: list[Invariant],
                   findings: list[Finding]) -> dict:
    """Seals the reconciliation report as a `reconciliation` event.

    The checker journals its own findings: at audit time, "these gaps were
    open" is part of the sealed history. The journal audits its auditor.
    """
    report = {
        "invariants": [inv.name for inv in invariants],
        "total_findings": len(findings),
        "findings": [f.__dict__ for f in findings],
    }
    return store.append("reconciliation", report, key)
