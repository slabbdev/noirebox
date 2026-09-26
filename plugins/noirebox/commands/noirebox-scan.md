---
description: Passe un texte au garde-fou NoireBox (injections FR/EN)
argument-hint: texte ou chemin de fichier à analyser
---

Récupère le texte à analyser : si `$ARGUMENTS` est un chemin de fichier
existant, lis-le ; sinon utilise `$ARGUMENTS` tel quel.

Appelle l'outil MCP `noirebox_scan` (serveur `noirebox`) avec ce texte
(`meeting_id` optionnel si l'utilisateur en donne un). L'outil scelle
lui-même l'incident dans le journal.

Présente le résultat : nombre d'incidents, catégorie et extrait de chaque
détection, puis le `seq` de l'événement `incident` scellé. Si aucun incident
n'est détecté, dis-le et rappelle que le garde-fou bundle (regex + ML FR/EN)
est une source d'événements parmi d'autres — un garde-fou existant
(Lakera, Llama Guard…) peut journaliser ses verdicts via
`noirebox_log_event`.
