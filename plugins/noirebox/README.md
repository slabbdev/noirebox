# Plugin ZCode — NoireBox

Branche NoireBox — le journal inaltérable pour agents IA — directement dans
ZCode : l'agent devient son propre vol enregistré.

## Ce que fait le plugin

| Composant | Rôle |
|---|---|
| Serveur MCP `noirebox` | 4 outils natifs : `noirebox_scan`, `noirebox_log_event`, `noirebox_verify`, `noirebox_attestation` |
| Hook `PostToolUse` (Write/Edit/Bash) | Scelle automatiquement chaque action de l'agent (type `agent_tool_use`) dans le même journal |
| Skills `noirebox-journal` / `noirebox-demo` | Savoir sceller/vérifier/attester ; démo guidée en 5 étapes |
| Commandes `/noirebox-seal`, `/noirebox-verify`, `/noirebox-attest`, `/noirebox-scan` | Raccourcis des 4 gestes |

Le serveur MCP et le hook écrivent **le même journal** (même SQLite, même
clé Ed25519) : la chaîne ne fait qu'un.

## Configuration

Le plugin pointe sur un checkout NoireBox local (venv + journal). Deux
variables d'environnement le déplacent :

- `NOIREBOX_HOME` — racine du checkout (défaut :
  `/Users/samlabbe/.zcode/workspace/default/noirebox`) ; le journal vit dans
  `$NOIREBOX_HOME/data/noirebox.db`.
- `NOIREBOX_DB` — chemin SQLite explicite, prioritaire sur `NOIREBOX_HOME`.
- `NOIREBOX_HOOK_DISABLE=1` — désactive le scellement automatique par hook.

Déplacer le plugin (autre machine, autre chemin de checkout) = poser
`NOIREBOX_HOME` ; rien à éditer dans le plugin.
