from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import UTC, datetime

from .chain import Event, KeyPair, compute_event_hash

_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq        INTEGER PRIMARY KEY,
    ts         TEXT NOT NULL,
    type       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    prev_hash  TEXT NOT NULL,
    event_hash TEXT NOT NULL UNIQUE,
    signature  TEXT NOT NULL
);
"""


def now_iso() -> str:
    """ISO 8601 UTC timestamp with milliseconds.

    Always UTC (`timezone.utc`): an audit log mixing local times with and
    without daylight saving would be unusable. `timespec="ms"` fixes the
    precision — without it, two close calls would produce strings of
    different lengths depending on execution speed.
    """
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class EventStore:
    def __init__(self, path: str):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        # Hardening: the journal may contain personal data (transcripts,
        # payloads), so the file must never be readable by other local
        # accounts. O_CREAT gives 0600 at creation time (no window at 0644);
        # the unconditional chmod also tightens databases created before
        # this fix or by another tool. WAL sidecars inherit looser modes.
        fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
        os.close(fd)
        os.chmod(path, 0o600)
        for sidecar in (f"{path}-wal", f"{path}-shm"):
            if os.path.exists(sidecar):
                os.chmod(sidecar, 0o600)

        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def append(self, type_: str, payload: dict, key: KeyPair) -> Event:
        """Inserts a chained, signed event. Critical section under lock.

        The lock is essential: two simultaneous HTTP requests must read the
        same "last event", otherwise two events would share the same seq and
        the chain would be inconsistent from the very first writes.
        """
        with self._lock:
            row = self._conn.execute(
                "SELECT seq, event_hash FROM events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            seq = (row[0] + 1) if row else 1
            prev_hash = row[1] if row else "0" * 64
            ts = now_iso()
            event_hash = compute_event_hash(seq, ts, type_, payload, prev_hash)
            signature = key.sign(bytes.fromhex(event_hash))
            event = Event(seq, ts, type_, payload, prev_hash, event_hash, signature)
            self._conn.execute(
                "INSERT INTO events (seq, ts, type, payload, prev_hash, event_hash, signature) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (seq, ts, type_, json.dumps(payload, ensure_ascii=False, sort_keys=True),
                 prev_hash, event_hash, signature),
            )
            self._conn.commit()
            return event

    def all(self) -> list[dict]:
        """All events, oldest to newest, payload deserialized to a dict
        (the JSON is stored as TEXT)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT seq, ts, type, payload, prev_hash, event_hash, signature "
                "FROM events ORDER BY seq ASC"
            ).fetchall()
        return [
            {
                "seq": r[0], "ts": r[1], "type": r[2],
                "payload": json.loads(r[3]), "prev_hash": r[4],
                "event_hash": r[5], "signature": r[6],
            }
            for r in rows
        ]
