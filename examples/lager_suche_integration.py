#!/usr/bin/env python3
"""Beispiel: lager_suche.py (nestegg-locator) um reveries ergänzen.

Lauffähig zum Ausprobieren:
    NESTEGG_DIR=../nestegg-locator python3 examples/lager_suche_integration.py \\
        --data ../nestegg-locator/tests/fixtures/inventar_beispiel.csv wo ist die hard

In lager_suche.py selbst braucht es nur den markierten Block plus eine Zeile in
der Suche: print(humanize(text, result, format_search(result, config), config)).
Ist reveries nicht installiert oder kaputt, bleibt die Antwort einfach sachlich.
"""

import os
import re
import sys
from pathlib import Path

# ----------------------------------------------------------- Block für lager_suche.py
REVERIES_DIR = Path(os.environ.get("REVERIES_DIR", "/config/reveries"))

try:
    sys.path.insert(0, str(REVERIES_DIR))   # geklonter Ordner; bei pip-Installation egal
    import reveries
    QUIRKS = reveries.load(REVERIES_DIR / "quirks")
    PERSONA = reveries.load_persona(REVERIES_DIR / "persona.md")
except Exception as exc:  # Suche muss auch ohne reveries funktionieren
    reveries = None
    print(f"reveries nicht verfügbar: {exc!r}", file=sys.stderr)


def reveries_llm():
    """Optional: lokaler vLLM-Server, falls REVERIES_LLM_URL gesetzt ist."""
    url = os.environ.get("REVERIES_LLM_URL")
    if not url or reveries is None:
        return None
    from reveries.llm import openai_compatible
    return openai_compatible(url, os.environ.get("REVERIES_LLM_MODEL", "default"), timeout=20)


def humanize(question, result, plain, config):
    """Würzt eine Suchantwort – nur wenn alle Treffer eindeutig in derselben Kiste liegen."""
    if reveries is None or result.fuzzy or not result.hits:
        return plain
    try:
        items = [h.item for h in result.hits]
        if any(i.unknown for i in items) or len({i.location for i in items}) != 1:
            return plain
        item = items[0]
        word = re.escape(config["container_word"])
        number = re.fullmatch(rf"{word}\s+(\S+)", item.container, re.I)
        facts = {"kiste": number.group(1) if number else item.container,
                 "ort": item.place, "titel": item.name}
        if not facts["kiste"]:
            return plain
        return reveries.apply(
            plain=plain, facts=facts, project="nestegg",
            texts=[question] + [i.name for i in items],
            quirks=QUIRKS, llm=reveries_llm(), persona=PERSONA)
    except Exception as exc:
        print(f"reveries übersprungen: {exc!r}", file=sys.stderr)
        return plain
# ----------------------------------------------------------- Ende des Blocks


def main(argv=None):
    """Nachbau des Such-Pfads von lager_suche.main(), nur für dieses Beispiel."""
    sys.path.insert(0, os.environ.get("NESTEGG_DIR", "/config/nestegg-lager"))
    import lager_suche as ls

    args = sys.argv[1:] if argv is None else argv
    config = ls.load_config(None)
    if args[:1] == ["--data"]:
        config["data_file"], args = args[1], args[2:]
    text = " ".join(args)
    items = ls.load_inventory(ls.data_path(config), config)

    mode, arg = ls.parse_request(text)
    if mode != "search":
        print(ls.answer(text, items, config))
        return 0
    result = ls.search(items, arg, config["fuzzy_cutoff"])
    print(humanize(text, result, ls.format_search(result, config), config))
    return 0


if __name__ == "__main__":
    sys.exit(main())
