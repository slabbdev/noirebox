"""PostToolUse hook body: seals ZCode tool actions into the NoireBox journal.

Reads the hook JSON on stdin and appends one event (type: agent_tool_use) to
the same journal the MCP server writes to — same SQLite file, same Ed25519
key, same chain. Payload keeps a truncated preview of the tool input only
(data minimization): the journal proves what was done, it is not a log dump.
"""
from __future__ import annotations

import datetime
import json
import os
import sys

from noirebox.chain import KeyPair
from noirebox.store import EventStore

MAX_PREVIEW_CHARS = 800
DEFAULT_HOME = "/Users/samlabbe/.zcode/workspace/default/noirebox"


def journal_path() -> str:
    db = os.environ.get("NOIREBOX_DB")
    if db:
        return db
    home = os.environ.get("NOIREBOX_HOME", DEFAULT_HOME)
    return os.path.join(home, "data", "noirebox.db")


def main() -> None:
    try:
        hook = json.load(sys.stdin)
    except Exception:
        return
    tool = str(hook.get("tool_name", "unknown"))
    detail = hook.get("tool_input") or {}
    try:
        preview = json.dumps(detail, ensure_ascii=False)[:MAX_PREVIEW_CHARS]
    except Exception:
        preview = "<unserializable tool input>"
    db = journal_path()
    try:
        store = EventStore(db)
        key = KeyPair.load_or_create(db + ".key")
        store.append(
            "agent_tool_use",
            {
                "source": "zcode-plugin",
                "tool": tool,
                "input_preview": preview,
                "sealed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            },
            key,
        )
    except Exception as exc:
        # A seal that fails must be visible: a silent failure would leave an
        # unexplained gap in a tamper-evident journal. Loud on stderr, but
        # never blocking — the wrapper still exits 0.
        print(f"[noirebox] seal failed ({tool}): {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
