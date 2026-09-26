---
description: Vérifie l'intégrité complète de la chaîne NoireBox
---

Appelle l'outil MCP `noirebox_verify` (serveur `noirebox`).

Présente le résultat en deux lignes maximum :

1. Verdict : chaîne **intacte** (ordre, liens, signatures valides) ou
   **compromise**, avec l'événement fautif s'il y en a un.
2. Nombre d'événements dans le journal et tête de chaîne (hash tronqué).

Si la chaîne est compromise, ne tente aucune réparation : c'est la preuve
d'une falsification, dis-le tel quel et suggère l'attestation pour figer
l'état.
