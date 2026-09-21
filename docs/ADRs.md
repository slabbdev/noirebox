# ADRs — NoireBox

*Architecture Decision Records: design decisions, context, and justification. These documents show that the project reasons about choices instead of just stacking features.*

---

## ADR 001 — Guardrail: regex heuristics first, then ML micro-model, LLM judge last

**Status**: decided (stages 0 and 1 in production), LLM judge in roadmap.

**Context**: every incoming transcript must be scanned before the agent.
Three detector families are possible.

**Decision**: layered architecture, cheapest to most expensive —
1. regex (obvious cases, zero cost, deterministic, testable in CI)
2. French ML micro-model (293 KB, generalizes to paraphrases, local)
3. LLM judge (only for ambiguous scores) — because it is the only stage that costs time and money per request.

**Consequences**: scanning stages 1–2 is effectively free, so we can scan every request instead of a sample. The incident format is unified across engines (positions + category), and the API selects via `engine: regex|ml`.

---

## ADR 002 — Reject Meta's Llama Prompt Guard 2 as the engine

**Status**: evaluated and rejected deliberately.

**Context**: Prompt Guard 2 22M (Meta) is the industry-standard prompt injection classifier (~90 MB). The question was whether to rely on it instead of training a homegrown model.

**Decision**: do not integrate it, for four measured reasons:

| Criterion | Prompt Guard 2 22M | NoireBox ML (293 KB) |
|---|---|---|
| Language | English (our meetings are **French**) | FR, versioned FR corpus |
| Output | binary INJECTION/BENIGN | 4 attack families → audit report + scoring |
| License | **gated** (HF account + Meta acceptance + token) | project artifact, zero friction |
| Dependencies | torch + transformers (heavy, opt-in) | scikit-learn only, already present |

## ADR 003 — Third-party detectors (Llama Guard 3, Prompt Guard 2): documented path, not embedded

**Status**: integration path documented; no third-party detector embedded in v0.

**Context**: the question naturally comes back — “why not plug in the industry classifier?” ADR 002 documented the rejection of Prompt Guard 2 (language, binary output, gated license, dependencies). This ADR fixes the integration path for the day a real need arises (e.g., product sold in English, client requirement for Meta ecosystem).

**Decision**: every third-party detector integrates behind the existing engine interface without touching the core:

```python
# Contract: same shape as guardrail.scan_transcript / ml_guardrail.scan_ml
def scan_<engine>(text: str, min_confidence: float = 0.5) -> list[dict]:
    # → [{"category": str, "score": float, "excerpt": str, "start": int, "end": int}]
```

1. **Adapter** (~40 lines): call the third-party model, map its output to the incident format above and include line offsets.
2. **Isolated dependencies**: separate `requirements-<engine>.txt`, late imports in `main.py` so the core stays lean.
3. **Actionable 503** if the engine is missing (exact install message).
4. **Skip-if-absent tests**: never simulated — third-party model absent means skip, never a made-up response (project anti-fake rule).
5. **Published benchmarks**: the third-party detector is compared with the internal engines on unseen FR *and* EN sentences before activation.
6. **License**: no unofficial mirror; gated handling stays on the deployment side (`HF_TOKEN`), never in the repo.

**Consequences**: adding a detector costs only an adapter; the LLM judge from ADR 001 (stage 2) follows the same path via `llama-guard3:1b` — already served by the required Ollama for the LLM scene.

---

## ADR 004 — OAuth2 authentication (JWT bearer) and rate limiting: optional via configuration

**Status**: implemented (v0.2.0).

**Context**: the API writes to a proof journal — without auth, anyone able to reach the port can create events (not forge them, which is impossible, but pollute them). The threat model listed the lack of auth/rate limiting as an assumed gap.

**Decision**:
1. **Homegrown OAuth2 client-credentials**: `client_id:secret` (env `NOIREBOX_CLIENTS`) exchanged for a **1-hour HS256 JWT** (`POST /api/v1/token`), presented as `Authorization: Bearer`. Secret comparison uses constant-time logic (`hmac.compare_digest`).
2. **Explicit activation**: without `NOIREBOX_CLIENTS`, the API runs open (local demo without friction); with the variable set, writes and exports are protected. Security is a deployment choice, never an accident.
3. **Precise scope**: auth protects WRITES (`POST /events`, `/scan`) and EXPORTS. VERIFICATION routes (`/verify`, `/attestation`, `/attestation.pdf`) remain open — we never lock verification, which is foundational to the project.
4. **Per-client rate limiting**: sliding window in memory (60 req/min), 429 + `Retry-After`. In-memory rather than SQLite: near-zero cost and never polluting the append-only journal. Redis = documented multi-process extension.

**Consequences**: the threat model gap for a network attacker is reduced to transport authentication (TLS handled by the reverse proxy); the JWT signing secret is derived from the instance key if `NOIREBOX_JWT_SECRET` is not set (unique per deployment, no config required).

---

## ADR 005 — PDF attestation: proof for humans, JSON for machines

**Status**: implemented (v0.2.0).

**Context**: the JSON export is proof for a verifier; a DPO, however, needs a document that can be placed in a compliance file.

**Decision**: `GET /api/v1/attestation.pdf` produces a sober A4 page (reportlab, PDF ~3.6 KB): chain status, public key, signature, and especially **verification instructions printed on the document** (exit 0 / exit 1, no trust required). JSON remains the single source of truth; the PDF carries the promise and the method, never a claim of certification (printed note at the footer).

**Consequences**: reportlab joins the dependencies (lightweight, pure Python); the EN localization of the document will follow with the product i18n work.

---

## ADR 006 — RFC 3161 anchoring: close the “insider with the key” gap

**Status**: implemented (v0.3.0).

**Context**: the threat model assumed a gap: an operator holding the private key could regenerate the entire chain (consistent hashes, valid signatures) — the only detection path was via a published external attestation. The underlying question: the journal proves integrity, but the DATE was self-declared by the accused.

**Decision**: `POST /api/v1/anchors` seals the chain head with a TSA (Timestamp Authority, RFC 3161):

1. Only the **head hash** leaves to the TSA (no data leaves the infrastructure — zero GDPR leakage).
2. The signed token + TSA certificate are journaled as an `anchor` event **inside the chain itself**: the journal seals its own external proof; no parallel storage.
3. The third-party verifier gains a check: the head named by the anchor is the real chain head at that height, the token is signed by the embedded TSA certificate, and it covers that hash. A regeneration creates a head the old token does not cover — detected without any prior external publication.
4. **TSA is interchangeable via configuration** (`NOIREBOX_TSA_URL`): self-hosted OpenSSL TSA (`make tsa`, separate process with its own key — free, offline, sovereign) is the default demo mode; any public or qualified TSA works in production. A TOFU model is assumed (the certificate travels in the anchor), with pinning possible on the verifier side.

**Consequences**: the threat model gap for “insider with the key” is closed (detection occurs at the first anchor, not at attestation time); verifier dependency = openssl (universal on macOS/Linux); TSA rotation is recommended in production to distribute trust.

---

## ADR 007 — Self-hosted TSA: root + leaf chain, not a single certificate

**Status**: implemented (v0.3.0).

**Context**: `openssl ts -reply` requires a signer certificate with TimeStamping usage; `-verify` also requires a CA certificate as trust anchor. A single CA:TRUE + TimeStamping certificate is rejected ("invalid signer certificate purpose"): a CA should not sign tokens.

**Decision**: the TSA material (`tsa/gen_tsa.sh`) generates a two-certificate chain — self-signed root (CA:TRUE), TSA leaf (CA:FALSE, critical EKU `timeStamping`) signed by the root — and serves the bundle at `GET /cert`. The bundle travels with each anchor and is given to the verifier twice (`-CAfile bundle -untrusted bundle`).

**Consequences**: setup validated experimentally (verify OK for the correct hash, FAILED for a different one); TSA port 3318 (ports < 1024 are privileged); the TSA material (`tsa/material/`) is never committed.
