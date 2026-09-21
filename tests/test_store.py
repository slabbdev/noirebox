"""Database file permissions: the journal may contain personal data, so the
file (and its WAL sidecars) must never be readable by other local accounts.
"""
from __future__ import annotations

import stat
from pathlib import Path

from noirebox.chain import KeyPair
from noirebox.store import EventStore


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _sidecar(db: Path, suffix: str, root: Path) -> Path:
    """WAL/SHM sidecar path — containment in the test sandbox is asserted,
    not assumed."""
    sidecar = db.with_name(db.name + suffix).resolve()
    assert sidecar.is_relative_to(root)
    return sidecar


def test_new_database_is_created_owner_only(tmp_path):
    """A freshly created database is 0600 — no window at 0644."""
    db = tmp_path / "box.db"
    EventStore(str(db))
    assert _mode(db) == 0o600


def test_loose_permissions_are_tightened_on_open(tmp_path):
    """A pre-existing world-readable database (created before the fix, or by
    another tool) is tightened to 0600 on the next open."""
    db = tmp_path / "box.db"
    db.write_text("")
    db.chmod(0o644)
    EventStore(str(db))
    assert _mode(db) == 0o600


def test_wal_sidecars_are_owner_only(tmp_path):
    """WAL/SHM sidecars appear on first write — they must be 0600 too."""
    db = tmp_path / "box.db"
    store = EventStore(str(db))
    key = KeyPair.load_or_create(str(tmp_path / "box.key"))
    store.append("llm_call", {"agent": "perm-test"}, key)
    for suffix in ("-wal", "-shm"):
        sidecar = _sidecar(db, suffix, tmp_path)
        if sidecar.exists():
            assert _mode(sidecar) == 0o600
