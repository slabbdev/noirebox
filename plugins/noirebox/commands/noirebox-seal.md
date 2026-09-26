---
description: Scelle une décision ou un fait dans le journal inaltérable NoireBox
argument-hint: ce qu'il faut sceller
---

Scelle dans NoireBox ce que l'utilisateur vient de demander d'enregistrer.

Appelle l'outil MCP `noirebox_log_event` (serveur `noirebox`) avec :

- `type`: `"decision"`
- `payload`: `{"summary": $ARGUMENTS, "sealed_at": <date UTC ISO-8601 du
  moment>, "source": "zcode-command"}`

Si le serveur MCP est indisponible, applique le fallback décrit dans le
skill `noirebox-journal`.

Réponds avec le `seq` et le `event_hash` de l'événement, et rappelle en une
ligne : `/noirebox-verify` pour contrôler la chaîne, `/noirebox-attest` pour
produire l'attestation signée.
