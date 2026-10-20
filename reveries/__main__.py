"""CLI:  python -m reveries lint [pfad]
       python -m reveries test "frage" --titel "..." --fakt kiste=4 --project nestegg
"""

import argparse
import os
import random
import sys
from pathlib import Path

from .core import build_prompt, explain
from .loader import check, load, load_persona

REPO_DIR = Path(__file__).resolve().parent.parent


def default_quirks():
    local = Path.cwd() / "quirks"
    return local if local.is_dir() else REPO_DIR / "quirks"


def default_persona(quirks_path):
    for candidate in (Path(quirks_path).parent / "persona.md", REPO_DIR / "persona.md"):
        if candidate.is_file():
            return candidate
    return None


def cmd_lint(args):
    path = Path(args.pfad) if args.pfad else default_quirks()
    quirks, problems = check(path)
    for problem in problems:
        print(problem)
    errors = sum(p.level == "fehler" for p in problems)
    warnings = len(problems) - errors
    print(f"{len(quirks)} Quirk(s) gültig, {errors} Fehler, {warnings} Warnung(en) – {path}")
    return 1 if errors else 0


def parse_facts(pairs):
    facts = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep or not key.strip():
            raise SystemExit(f"--fakt erwartet name=wert, nicht {pair!r}")
        facts[key.strip()] = value.strip()
    return facts


def make_llm(args):
    if args.llm_url:
        from .llm import openai_compatible
        return openai_compatible(args.llm_url, args.llm_model or "default",
                                 api_key=os.environ.get("REVERIES_API_KEY"))
    if args.gemini:
        from .llm import gemini
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise SystemExit("--gemini braucht die Umgebungsvariable GEMINI_API_KEY")
        return gemini(args.gemini, key)
    return None


def cmd_test(args):
    quirks_path = Path(args.quirks) if args.quirks else default_quirks()
    quirks = load(quirks_path)
    facts = parse_facts(args.fakt)
    if args.titel:
        facts.setdefault("titel", args.titel)
    plain = args.plain or " · ".join(f"{k}: {v}" for k, v in facts.items()) or args.frage
    texts = [args.frage] + ([args.titel] if args.titel else [])
    persona_path = default_persona(quirks_path)
    persona = load_persona(persona_path) if persona_path else ""
    rng = random.Random(args.seed) if args.seed is not None else None

    outcome = explain(plain, facts, args.project, texts, quirks, llm=make_llm(args),
                      llm_share=args.llm_share, rng=rng, persona=persona)

    print(f"Quirks geladen: {len(quirks)} aus {quirks_path}")
    print(f"Texte:          {texts}")
    print(f"Fakten:         {facts}")
    if outcome.matches:
        for i, match in enumerate(outcome.matches):
            marker = "→" if i == 0 else " "
            print(f"{marker} Treffer: {match.quirk.id} (priority {match.quirk.priority}, "
                  f"chance {match.quirk.chance}, Begriff „{match.term}“) – {match.quirk.source}")
    print(f"Entscheidung:   {outcome.source} – {outcome.reason}")
    if args.prompt and outcome.quirk:
        print("\n--- LLM-Prompt ---\n" + build_prompt(outcome.quirk, facts, plain, persona))
    print(f"\nOriginal: {plain}\nAntwort:  {outcome.text}")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m reveries")
    sub = parser.add_subparsers(dest="command", required=True)

    lint = sub.add_parser("lint", help="Quirk-Dateien prüfen")
    lint.add_argument("pfad", nargs="?", help="Ordner oder Datei (Standard: ./quirks)")
    lint.set_defaults(func=cmd_lint)

    test = sub.add_parser("test", help="Zeigen, welcher Quirk greift")
    test.add_argument("frage", help="Nutzerfrage, z. B. „wo ist indiana jones 4“")
    test.add_argument("--titel", help="gefundener DB-Titel (wird auch Fakt „titel“)")
    test.add_argument("--fakt", action="append", default=[], metavar="NAME=WERT")
    test.add_argument("--project", help="Projektname für den scope-Filter")
    test.add_argument("--plain", help="Originalantwort (Standard: aus den Fakten gebaut)")
    test.add_argument("--quirks", help="Quirk-Ordner (Standard: ./quirks)")
    test.add_argument("--seed", type=int, help="Zufall reproduzierbar machen")
    test.add_argument("--prompt", action="store_true", help="LLM-Prompt anzeigen")
    test.add_argument("--llm-url", help="OpenAI-kompatibler Server, z. B. http://host:8000/v1")
    test.add_argument("--llm-model", help="Modellname für --llm-url")
    test.add_argument("--gemini", metavar="MODELL", help="Gemini-Modell (Key in GEMINI_API_KEY)")
    test.add_argument("--llm-share", type=float, default=0.4)
    test.set_defaults(func=cmd_test)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
