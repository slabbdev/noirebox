"""Reconciliation plugin (v0.1) — business invariants over the journal.

The journal proves integrity and order. It deliberately does NOT know what a
"missing half" is: that knowledge is domain-specific, and this plugin is where
it lives — the same plugin pattern as the guardrail (journal domain-blind,
domain knowledge pluggable). Community request: issue #3, schema refined by
Axiru (payout side).

The pattern it checks (two-event flow, e.g. payouts):

    policy_decision (allow/hold/deny + reason_code + policy_version
                     + expected_by or expected_within)
    provider_response (provider status, optional unauthorized flag)
    ... linked by a correlation key: decision_id

Schema notes (from the Axiru review, v0.1):

1. **Correlate on a decision id, not the payment intent** — one intent can
   produce several attempts, each with its own decision. Matching on the
   intent would hide a second decision for the same intent.
2. **A decision carries its deadline** — `expected_by` (absolute ISO) or
   `expected_within` (duration from the decision timestamp). A decision
   whose window passed with no outcome flips to `unconfirmed` — the gap is
   flagged in real time, not discovered in hindsight. Without a deadline the
   gap stays `open_gap` (visible only in hindsight).
3. **An orphan outcome should carry an explicit flag** — `unauthorized: true`
   in the outcome payload means "never authorized": auditors search for the
   flag, they do not search for silence. Unflagged orphans stay inferred
   (`orphan_outcome`).

Every finding is evidence, not an action: the plugin never repairs, it
reports. And the report is sealed into the journal like any event — the
journal's auditor is audited by the journal it audits.

v0.1 boundaries:
- config is JSON (stdlib) — YAML would add a dependency for syntax
- one correlation key per invariant, first event wins on duplicates
- `now` is injectable for tests; defaults to the real clock
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
    """One reconciliation result — evidence sealed into the journal.

    Statuses:
        matched         — decision and outcome both sealed
        late            — both sealed, but the outcome came after the deadline
        pending         — decision sealed, window not passed yet, no outcome yet
        unconfirmed     — decision sealed, deadline passed, no outcome
        open_gap        — decision sealed with NO deadline at all
        orphan_outcome  — outcome with no decision (inferred by absence)
        unauthorized    — outcome explicitly flagged `unauthorized: true`
                          ("never authorized" — auditors search for the flag)
    """

    invariant: str
    status: str
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


def _deadline(decision: dict, inv: Invariant) -> datetime | None:
    """The per-event deadline from the decision: `expected_by` (absolute ISO)
    wins over `expected_within` (duration from the decision timestamp); the
    invariant's `within` is the last-resort fallback."""
    payload = decision.get("payload", {})
    if payload.get("expected_by"):
        return datetime.fromisoformat(payload["expected_by"])
    if payload.get("expected_within"):
        return _ts(decision) + timedelta(
            seconds=parse_duration(payload["expected_within"]) or 0
        )
    if inv.within_seconds is not None:
        return _ts(decision) + timedelta(seconds=inv.within_seconds)
    return None


def reconcile(events: list[dict], invariants: list[Invariant],
              now: datetime | None = None) -> list[Finding]:
    """Runs every invariant over the events, returns the findings.

    `events` is what `store.all()` returns — or any handcrafted list with
    the same shape (seq, ts, type, payload). First occurrence wins on
    duplicate correlation ids: the original decision, the first response.
    `now` is the reference clock for deadline checks (injectable in tests).
    """
    ref = now or datetime.now(timezone.utc)
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
                deadline = _deadline(decision, inv)
                if deadline is None:
                    findings.append(Finding(inv.name, "open_gap", cid,
                                            decision_seq=decision["seq"]))
                elif ref > deadline:
                    findings.append(Finding(inv.name, "unconfirmed", cid,
                                            decision_seq=decision["seq"]))
                else:
                    findings.append(Finding(inv.name, "pending", cid,
                                            decision_seq=decision["seq"]))
                continue
            lag = (_ts(outcome) - _ts(decision)).total_seconds()
            if inv.within_seconds is not None and lag > inv.within_seconds:
                findings.append(Finding(inv.name, "late", cid,
                                        decision_seq=decision["seq"],
                                        outcome_seq=outcome["seq"],
                                        lag_seconds=lag))
            else:
                findings.append(Finding(inv.name, "matched", cid,
                                        decision_seq=decision["seq"],
                                        outcome_seq=outcome["seq"]))

        for cid, outcome in outcomes.items():
            if cid in decisions:
                continue
            if outcome.get("payload", {}).get("unauthorized") is True:
                findings.append(Finding(inv.name, "unauthorized", cid,
                                        outcome_seq=outcome["seq"]))
            else:
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
