"""Supervision dashboard — a read-only HTML view of the journal.

Served by the API itself at `GET /dashboard`. Two hard rules, decided when
the feature was designed (2026-09, before any line of code):

1. **Read-only**: this view never mutates the journal. It renders what the
   existing GET endpoints already expose — nothing more, nothing writable.
2. **It displays, it does not attest**: the badge shows the result of the
   same local recomputation the verifier performs; the trust anchor remains
   the exported dossier. A dashboard is a convenience, never the proof.

Zero dependencies: one HTML constant, inline CSS/JS, fetched from the
existing endpoints (/api/v1/verify, /api/v1/events). The reconciliation
panel pairs `policy_decision` / `provider_response` events by their
`payment_intent_id` correlation key — the two-event pattern from issue #3 —
and only appears when such events exist.
"""

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NoireBox — dashboard</title>
<style>
  :root { --bg:#05060a; --panel:#0a0c12; --line:rgba(255,255,255,.08);
    --txt:#e8ecf1; --dim:#9aa4b2; --dimmer:#616b7a; --red:#e10600;
    --red-soft:#ff8577; --green:#3fb950; --mono:ui-monospace,SFMono-Regular,Menlo,monospace; }
  * { margin:0; padding:0; box-sizing:border-box; }
  body { background:var(--bg); color:var(--txt); font-family:var(--mono);
    padding:32px 5vw; }
  header { display:flex; align-items:center; justify-content:space-between;
    flex-wrap:wrap; gap:16px; margin-bottom:28px; }
  h1 { font-size:1.1rem; letter-spacing:.22em; font-weight:800; }
  h1 .cube { display:inline-block; width:12px; height:12px; border-radius:3px;
    background:linear-gradient(145deg,#2a2e38,#0d1117); margin-right:10px;
    box-shadow: inset 0 0 6px rgba(225,6,0,.5), 0 0 12px rgba(225,6,0,.25); }
  .badge { font-weight:800; padding:10px 22px; border-radius:8px;
    font-size:1rem; letter-spacing:.08em; }
  .badge.ok { color:var(--green); border:1px solid rgba(63,185,80,.5);
    background:rgba(63,185,80,.08); }
  .badge.bad { color:var(--red-soft); border:1px solid rgba(225,6,0,.6);
    background:rgba(225,6,0,.1); animation:pulse 1.2s infinite; }
  @keyframes pulse { 50% { opacity:.55; } }
  .cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
    gap:12px; margin-bottom:28px; }
  .card { background:var(--panel); border:1px solid var(--line);
    border-radius:12px; padding:18px; }
  .card b { display:block; font-size:1.35rem; font-weight:800; }
  .card span { font-size:.68rem; letter-spacing:.14em; text-transform:uppercase;
    color:var(--dimmer); }
  h2 { font-size:.72rem; letter-spacing:.2em; text-transform:uppercase;
    color:var(--dimmer); margin:26px 0 12px; }
  table { width:100%; border-collapse:collapse; font-size:.84rem; }
  th { text-align:left; color:var(--dimmer); font-size:.66rem;
    letter-spacing:.14em; text-transform:uppercase; padding:8px 10px;
    border-bottom:1px solid var(--line); }
  td { padding:9px 10px; border-bottom:1px solid var(--line);
    color:var(--dim); vertical-align:top; }
  td.seq, td.ts { font-family:var(--mono); color:var(--txt); white-space:nowrap; }
  .type { font-weight:700; color:var(--txt); }
  .type.policy_decision, .type.provider_response { color:var(--red-soft); }
  .type.reconciliation { color:var(--green); }
  .chip { border-radius:99px; padding:2px 10px; font-size:.72rem; }
  .chip.ok { color:var(--green); border:1px solid rgba(63,185,80,.45); }
  .chip.gap { color:var(--red-soft); border:1px solid rgba(225,6,0,.5); }
  .chip.orphan { color:#f5a623; border:1px solid rgba(245,166,35,.5); }
  footer { margin-top:34px; color:var(--dimmer); font-size:.78rem;
    display:flex; gap:20px; flex-wrap:wrap; }
  footer a { color:var(--red-soft); text-decoration:none; }
  .empty { color:var(--dimmer); padding:14px 10px; }
</style>
</head>
<body>
<header>
  <h1><span class="cube"></span>NOIREBOX — FLIGHT DATA RECORDER</h1>
  <span class="badge" id="badge">CHECKING…</span>
</header>

<div class="cards">
  <div class="card"><b id="c-events">—</b><span>sealed events</span></div>
  <div class="card"><b id="c-head">—</b><span>chain head</span></div>
  <div class="card"><b id="c-last">—</b><span>last event (UTC)</span></div>
  <div class="card"><b id="c-gaps">—</b><span>reconciliation gaps</span></div>
</div>

<div id="recon-panel" style="display:none">
  <h2>Reconciliation — two-event pattern (issue #3)</h2>
  <table id="recon-table">
    <thead><tr><th>payment_intent_id</th><th>state</th></tr></thead>
    <tbody></tbody>
  </table>
</div>

<h2>Sealed events</h2>
<table>
  <thead><tr><th>#</th><th>UTC</th><th>type</th><th>payload</th></tr></thead>
  <tbody id="rows"><tr><td colspan="4" class="empty">loading…</td></tr></tbody>
</table>

<footer>
  <span>read-only — this view never mutates the journal</span>
  <a href="/docs">API docs</a>
  <a href="/api/v1/export">export dossier</a>
  <a href="https://github.com/slabbdev/noirebox" target="_blank" rel="noopener">GitHub</a>
</footer>

<script>
const esc = s => String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
const short = h => h ? h.slice(0,10) + "…" : "—";

async function refresh() {
  try {
    const [verify, events] = await Promise.all([
      fetch("/api/v1/verify").then(r => r.json()),
      fetch("/api/v1/events?limit=1000").then(r => r.json()),
    ]);

    const badge = document.getElementById("badge");
    if (verify.valid) {
      badge.textContent = "✓ INTACT";
      badge.className = "badge ok";
    } else {
      badge.textContent = "✗ TAMPERING — " + (verify.first_error?.reason || "chain invalid");
      badge.className = "badge bad";
    }

    document.getElementById("c-events").textContent = events.length;
    document.getElementById("c-head").textContent =
      short(verify.valid ? events[events.length - 1]?.event_hash : null);
    document.getElementById("c-last").textContent =
      events.length ? events[events.length - 1].ts : "—";

    // reconciliation: pair policy_decision / provider_response by correlation key
    const pairTypes = ["policy_decision", "provider_response"];
    const decisions = {}, outcomes = {};
    for (const e of events) {
      const k = e.payload && e.payload.payment_intent_id;
      if (!k) continue;
      if (e.type === "policy_decision") decisions[k] = e;
      if (e.type === "provider_response") outcomes[k] = e;
    }
    const hasPayout = Object.keys(decisions).length || Object.keys(outcomes).length;
    const openGaps = Object.keys(decisions).filter(k => !(k in outcomes));
    const orphans = Object.keys(outcomes).filter(k => !(k in decisions));
    document.getElementById("c-gaps").textContent =
      hasPayout ? (openGaps.length + orphans.length) : "—";

    const panel = document.getElementById("recon-panel");
    panel.style.display = hasPayout ? "" : "none";
    if (hasPayout) {
      const rows = [];
      for (const k of new Set([...Object.keys(decisions), ...Object.keys(outcomes)])) {
        const inD = k in decisions, inO = k in outcomes;
        const state = inD && inO ? '<span class="chip ok">matched</span>'
          : inD ? '<span class="chip gap">open gap — no provider response</span>'
                : '<span class="chip orphan">orphan outcome — no decision</span>';
        rows.push(`<tr><td>${esc(k)}</td><td>${state}</td></tr>`);
      }
      document.querySelector("#recon-table tbody").innerHTML = rows.join("");
    }

    document.getElementById("rows").innerHTML = events.slice().reverse().map(e =>
      `<tr><td class="seq">${e.seq}</td><td class="ts">${esc(e.ts)}</td>` +
      `<td><span class="type ${esc(e.type)}">${esc(e.type)}</span></td>` +
      `<td>${esc(JSON.stringify(e.payload).slice(0, 90))}${JSON.stringify(e.payload).length > 90 ? "…" : ""}</td></tr>`
    ).join("") || '<tr><td colspan="4" class="empty">journal is empty — seal your first event</td></tr>';
  } catch (err) {
    document.getElementById("badge").textContent = "API UNREACHABLE";
    document.getElementById("badge").className = "badge bad";
  }
}

refresh();
setInterval(refresh, 10000);
</script>
</body>
</html>
"""
