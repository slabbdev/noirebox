---
description: Exporte l'attestation signée et l'export complet vérifiable du journal NoireBox
argument-hint: [chemin de sortie optionnel]
---

Produis les DEUX artefacts, ils n'ont pas le même rôle :

**1. Le résumé signé (preuve en discussion).** Appelle l'outil MCP
`noirebox_attestation` (serveur `noirebox`) et montre le résultat : nombre
d'événements, tête de chaîne, validité.

**2. L'export complet (artefact tiers).** C'est le seul fichier que
`verifier/verifier.py` accepte : il doit contenir `public_key` + `events` +
`attestation`, car l'auditeur **recalcule toute la chaîne** au lieu de
faire confiance au résumé. L'outil MCP ne l'expose pas : passe par le SDK
(`NOIREBOX_HOME` = racine du checkout, défaut
`/Users/samlabbe/.zcode/workspace/default/noirebox`) :

```bash
"$NOIREBOX_HOME/.venv/bin/python" - <<'PY'
import json, os
from noirebox.store import EventStore
from noirebox.chain import KeyPair
from noirebox.attestation import build_attestation
home = os.environ.get("NOIREBOX_HOME", "/Users/samlabbe/.zcode/workspace/default/noirebox")
db = os.environ.get("NOIREBOX_DB", os.path.join(home, "data", "noirebox.db"))
store, key = EventStore(db), KeyPair.load_or_create(db + ".key")
export = {
    "format_version": 1,
    "service": "noirebox",
    "public_key": key.public_hex(),
    "events": store.all(),
    "attestation": build_attestation(store, key),
}
out = os.environ.get("NB_EXPORT_OUT") or os.path.join(home, "data", "export-manuel.json")
json.dump(export, open(out, "w"), ensure_ascii=False, indent=2)
print(out, "-", len(export["events"]), "événements")
PY
```

Si `$ARGUMENTS` donne un chemin de fichier, écris l'export à cet endroit
(`NB_EXPORT_OUT`) ; sinon `data/export-<date du jour>.json` du checkout.

**3. La vérification tiers.** Lance
`"$NOIREBOX_HOME/.venv/bin/python" "$NOIREBOX_HOME/verifier/verifier.py"
<export.json>` et annonce le verdict avec le code de sortie : exit 0 =
`[✓] INTACT`, chaîne recalculée et signatures valides ; exit 1 =
falsification détectée, à signaler tel quel.

Rappelle le sens : l'export se vérifie hors-ligne par n'importe qui, sans
faire confiance à la machine qui l'a produit.
