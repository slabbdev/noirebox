---
name: noirebox-journal
description: >
  Seal agent decisions and outputs into the NoireBox tamper-evident journal,
  verify the hash chain and export signed attestations. Use when the user asks
  to journaliser, sceller or garder une preuve d'une décision, vérifier la
  chaîne, produire une attestation, or wants a tamper-evident / GDPR-style
  audit trail (noirebox, Ed25519, hash chain, preuve, audit) of what this
  agent did. Also covers sealing a deliverable before handing it over.
---

# NoireBox — le journal inaltérable de cet agent

Chaque événement est chaîné par hachage SHA-256 et signé Ed25519. Une export
se vérifie hors-ligne par un tiers (auditeur, DPO, client) sans te faire
confiance. Le journal est la preuve ; ce que tu y écris doit y rester.

## Outils

Utilise en priorité les outils MCP du serveur `noirebox` (préfixe
`mcp__noirebox__` dans la session) :

- `noirebox_log_event` — ajoute un événement signé : `type` (texte libre :
  `decision`, `incident`, `llm_output`, `anchor`…) + `payload` (objet).
  Renvoie `seq` et `event_hash`.
- `noirebox_verify` — vérifie toute la chaîne (ordre, liens, signatures).
- `noirebox_attestation` — instantané signé de l'état du journal.
- `noirebox_scan` — garde-fou anti-injection FR/EN ; scelle lui-même les
  incidents détectés dans le journal.

Si le serveur MCP n'est pas connecté, fallback direct sur la base via le
checkout NoireBox local (racine `NOIREBOX_HOME`, par défaut
`/Users/samlabbe/.zcode/workspace/default/noirebox`) :

```bash
"$NOIREBOX_HOME/.venv/bin/python" - <<'PY'
from noirebox.store import EventStore
from noirebox.chain import KeyPair
db = "/Users/samlabbe/.zcode/workspace/default/noirebox/data/noirebox.db"
store, key = EventStore(db), KeyPair.load_or_create(db + ".key")
event = store.append("decision", {"summary": "..."}, key)
print(event.seq, event.event_hash)
PY
```

## Que sceller

- **Une décision** que l'utilisateur veut pouvoir prouver plus tard →
  `type: "decision"`, payload avec quoi/pourquoi/quand et le contexte
  minimal utile.
- **Un livrable** produit pour un client avant remise → `type:
  "llm_output"` avec une empreinte ou un extrait court, pas le contenu
  complet (minimisation des données — le journal prouve, il n'archive pas).
- **Tout texte suspect** avant qu'il n'atteigne un modèle → `noirebox_scan`.

## Après avoir scellé

Annonce toujours `seq` + `event_hash` à l'utilisateur. Pour un rapport ou un
audit : enchaîne `noirebox_verify` (chaîne intacte ?) puis
`noirebox_attestation`, et remets le JSON signé (commande
`/noirebox-attest`).
