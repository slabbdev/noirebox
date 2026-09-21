import stat

from noirebox.chain import (
    GENESIS,
    KeyPair,
    compute_event_hash,
    verify_chain,
    verify_event,
)


def _events(store_key, store):
    return store.all()


def test_genesis_and_first_event(tmp_path):
    from noirebox.store import EventStore

    store = EventStore(str(tmp_path / "t.db"))
    key = KeyPair.generate()
    ev = store.append("llm_call", {"prompt": "bonjour"}, key)

    assert ev.seq == 1
    assert ev.prev_hash == GENESIS
    assert ev.event_hash == compute_event_hash(1, ev.ts, "llm_call", {"prompt": "bonjour"}, GENESIS)


def test_chain_of_three_is_valid(tmp_path):
    from noirebox.store import EventStore

    store = EventStore(str(tmp_path / "t.db"))
    key = KeyPair.generate()
    for i in range(3):
        store.append("test", {"i": i}, key)

    report = verify_chain(key.public_hex(), store.all())
    assert report["valid"] is True
    assert report["nb_events"] == 3
    assert report["first_error"] is None


def test_payload_tamper_detected(tmp_path):
    from noirebox.store import EventStore

    store = EventStore(str(tmp_path / "t.db"))
    key = KeyPair.generate()
    store.append("llm_output", {"resume": "client OK"}, key)

    events = store.all()
    events[0]["payload"]["resume"] = "client REFUSE"
    reason = verify_event(key.public_hex(), events[0])
    assert reason == "invalid hash (content was modified)"


def test_hash_tamper_detected(tmp_path):
    from noirebox.store import EventStore

    store = EventStore(str(tmp_path / "t.db"))
    key = KeyPair.generate()
    store.append("test", {}, key)

    events = store.all()
    events[0]["event_hash"] = "f" * 64
    reason = verify_event(key.public_hex(), events[0])
    assert reason == "invalid hash (content was modified)"


def test_signature_tamper_detected(tmp_path):
    from noirebox.store import EventStore

    store = EventStore(str(tmp_path / "t.db"))
    key = KeyPair.generate()
    store.append("test", {"a": 1}, key)

    events = store.all()
    events[0]["signature"] = "00" * 64
    reason = verify_event(key.public_hex(), events[0])
    assert reason == "invalid signature"


def test_removed_event_breaks_sequence(tmp_path):
    from noirebox.store import EventStore

    store = EventStore(str(tmp_path / "t.db"))
    key = KeyPair.generate()
    for i in range(3):
        store.append("test", {"i": i}, key)

    events = store.all()
    del events[1]
    report = verify_chain(key.public_hex(), events)
    assert report["valid"] is False
    assert report["first_error"]["reason"] == "broken sequence (reordering or deletion)"


def test_wrong_key_fails_verification(tmp_path):
    from noirebox.store import EventStore

    store = EventStore(str(tmp_path / "t.db"))
    key = KeyPair.generate()
    impostor = KeyPair.generate()
    store.append("test", {}, key)

    report = verify_chain(impostor.public_hex(), store.all())
    assert report["valid"] is False
    assert report["first_error"]["reason"] == "invalid signature"


def test_key_persistence_roundtrip_and_permissions(tmp_path):
    key_path = tmp_path / "instance.key"
    kp1 = KeyPair.load_or_create(str(key_path))
    kp2 = KeyPair.load_or_create(str(key_path))

    assert kp1.public_hex() == kp2.public_hex()
    mode = stat.S_IMODE(key_path.stat().st_mode)
    assert mode == 0o600
