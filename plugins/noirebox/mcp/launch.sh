#!/bin/sh
# Launches the NoireBox MCP server (stdio JSON-RPC) from the local NoireBox checkout.
# Override the checkout location with NOIREBOX_HOME; the journal lives in $NOIREBOX_HOME/data.
NB_HOME="${NOIREBOX_HOME:-/Users/samlabbe/.zcode/workspace/default/noirebox}"
export NOIREBOX_DB="${NOIREBOX_DB:-$NB_HOME/data/noirebox.db}"
exec "$NB_HOME/.venv/bin/python" -m noirebox.mcp_server
