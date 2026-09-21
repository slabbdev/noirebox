/* NoireBox — progress bar, reveals, ticker, typed terminal. Zero deps. */

// ── scroll progress ─────────────────────────────────
const progress = document.getElementById("progress");
window.addEventListener("scroll", () => {
  const max = document.documentElement.scrollHeight - window.innerHeight;
  progress.style.width = `${(window.scrollY / max) * 100}%`;
}, { passive: true });

// ── reveal on scroll ────────────────────────────────
let termStarted = false;
const observer = new IntersectionObserver((entries) => {
  for (const entry of entries) {
    if (entry.isIntersecting) {
      entry.target.classList.add("on");
      if (entry.target.querySelector("#term-out") && !termStarted) startTerminal();
      observer.unobserve(entry.target);
    }
  }
}, { threshold: 0.15 });
document.querySelectorAll(".reveal").forEach((el) => observer.observe(el));

// ── event-hash ticker ───────────────────────────────
const TYPES = ["llm_call", "incident", "llm_output", "eval", "anchor", "tool_use", "rag_query"];
function fakeHash() {
  const hex = "0123456789abcdef";
  let s = "";
  for (let i = 0; i < 10; i++) s += hex[Math.floor(Math.random() * 16)];
  return s;
}
function buildTicker() {
  const items = [];
  for (let i = 0; i < 14; i++) {
    const type = TYPES[i % TYPES.length];
    items.push(`<span>#${i + 1} <b>${type}</b> ${fakeHash()}…</span>`);
  }
  // doubled for a seamless infinite loop
  document.getElementById("ticker").innerHTML = items.join("") + items.join("");
}
buildTicker();

// ── typed terminal: the third-party verifier ────────
const TERM_LINES = [
  ["$ curl -s https://noirebox.example.com/api/v1/export > export.json", "t-dim"],
  ["$ python verifier/verifier.py export.json", ""],
  ["", ""],
  ["[✓] INTACT — 42 events verified · attestation valid · 1 anchor ok", "t-ok"],
  ["    head of chain: b3fe86add26f95ba…  (exit 0)", "t-dim"],
  ["", ""],
  ["# …one week later, someone edits event #12…", "t-dim"],
  ["$ python verifier/verifier.py export.json", ""],
  ["", ""],
  ["[✗] TAMPERING DETECTED", "t-bad"],
  ["    event 12: hash invalid (content modified)  (exit 1)", "t-bad"],
  ["    anchor #1 no longer covers this head", "t-bad"],
];

function esc(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function startTerminal() {
  termStarted = true;
  const out = document.getElementById("term-out");
  let line = 0, col = 0;

  function type() {
    if (line >= TERM_LINES.length) return;
    const [text, cls] = TERM_LINES[line];
    col += 1;
    const done = TERM_LINES.slice(0, line)
      .map(([t, c]) => (c ? `<span class="${c}">${esc(t)}</span>` : esc(t)))
      .join("\n");
    const partial = text.slice(0, col);
    out.innerHTML = (done ? done + "\n" : "") +
      (cls ? `<span class="${cls}">${esc(partial)}</span>` : esc(partial));
    if (col < text.length) {
      setTimeout(type, 12 + Math.random() * 20);
    } else {
      line += 1; col = 0;
      setTimeout(type, 240);
    }
  }
  type();
}

// ── copy install command (hero pill) ────────────────
const copyBtn = document.getElementById("copy-install");
if (copyBtn) {
  copyBtn.addEventListener("click", async () => {
    const cmd = document.getElementById("install-cmd").textContent;
    try {
      await navigator.clipboard.writeText(cmd);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = cmd;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    copyBtn.textContent = "✓";
    copyBtn.classList.add("done");
    setTimeout(() => {
      copyBtn.textContent = "⧉";
      copyBtn.classList.remove("done");
    }, 1600);
  });
}
