#!/bin/sh
# Best-effort: seal each ZCode tool action (Write/Edit/Bash) into the NoireBox
# journal. The session must never block on the flight recorder, so failures
# still exit 0 — but stderr passes through and is printed loudly in the
# session: a silent failure would leave an unexplained gap in the journal.
# Disable entirely with NOIREBOX_HOOK_DISABLE=1.
[ -n "$NOIREBOX_HOOK_DISABLE" ] && exit 0
PLUGIN_ROOT="$1"
NB_HOME="${NOIREBOX_HOME:-/Users/samlabbe/.zcode/workspace/default/noirebox}"
PY="$NB_HOME/.venv/bin/python"
[ -x "$PY" ] || exit 0
[ -f "$PLUGIN_ROOT/hooks/seal_tool_use.py" ] || exit 0
"$PY" "$PLUGIN_ROOT/hooks/seal_tool_use.py" >/dev/null || true
exit 0
