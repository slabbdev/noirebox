# 🚀 Deploying NoireBox — honest options, from $0 to VPS

> Principle: the repo is around 2 MB (code + FR + EN micro-models), with reproducible datasets via
> `make train` (seed 42).
> The Ollama LLM (~400 MB) never ships in the repo or demo server — it lives on the machine
> running `make demo-llm`.

## Overview

| Option | Cost | Public URL | Constraints | For what |
|---|---|---|---|---|
| **cloudflared tunnel** | $0, no account | `xxx.trycloudflare.com` (ephemeral) | your Mac must stay on | live demos during calls / video calls |
| **Hugging Face Spaces** | $0, free account | permanent | sleeps after inactivity (wakes in ~30s), free CPU | shareable public link |
| Koyeb / Render (free tier) | $0 | permanent | card may be required, also sleeps | alt to HF |
| Scaleway / OVH VPS | $3–6/month | permanent, yours | you manage it (or just Docker) | when real users exist |
| Scaleway serverless / K8s | pay-per-use | — | monitor billing | later — oversized here |

## Option 1 — instant tunnel ($0, ~2 minutes)

```bash
./start.sh &                                   # API on 127.0.0.1:8768
cloudflared tunnel --url http://localhost:8768 # immediate public HTTPS URL
```

The displayed URL (`https://…trycloudflare.com`) is reachable from anywhere while the command runs.
It is perfect for showing the API in a call: a client opens `…/docs` and scans a transcript from the browser.

## Option 2 — Hugging Face Spaces ($0, permanent URL — recommended for demos)

1. Create an account on huggingface.co → New Space → **Docker** (free CPU).
2. Copy into the Space: `Dockerfile` (already ready), `noirebox/`, `requirements.txt`, `corpus/`.
3. Add a Space `README.md` with the frontmatter (template: `deploy/hf-space-README.md`).
4. Push → automatic build → `https://huggingface.co/spaces/<your-handle>/noirebox`.

The Space runs `uvicorn noirebox.main:app --port 8768` as-is (the port is declared in the frontmatter).
The ML model (293 KB) is committed to the repo, so no retraining is required at deployment time — it remains reproducible via `make train` if needed.

## Option 3 — VPS when the project has real users

Scaleway / OVH from about $3/month: `docker compose up -d` and you're done
(volume `./data` for the database and private key). This is justified only when a VPS is genuinely needed — not before.

## What deployment does not change

Third-party verification remains local: `verifier/verifier.py export.json`
recomputes the chain **offline** — an auditor does not need access to the server, and that is the project’s core principle.
