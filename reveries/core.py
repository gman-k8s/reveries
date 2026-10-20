"""apply(): aus einer sachlichen Antwort eine menschlichere machen – oder sie unverändert lassen.

Garantie: Das Ergebnis ist entweder die Originalantwort oder ein Text, in dem
alle geschützten Fakten stehen. Fehler jeder Art führen zur Originalantwort.
"""

import random
import re
import threading
from dataclasses import dataclass, field

from .log import warn
from .matcher import find
from .quirk import facts_present

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)
_QUOTES = "\"'„“”«»‚‘’"


@dataclass
class Outcome:
    text: str
    source: str = "original"   # "original" | "vorlage" | "llm"
    quirk: object = None
    reason: str = ""
    matches: list = field(default_factory=list)


def build_prompt(quirk, facts, plain, persona=""):
    """Kurzer Prompt mit genau einem Quirk – nie mit allen."""
    lines = []
    if persona:
        lines.append(persona)
    lines.append("Formuliere die folgende Antwort neu: auf Deutsch, höchstens 2 Sätze.")
    if quirk.attitude:
        lines.append(f"Haltung: {quirk.attitude}")
    if facts:
        exact = ", ".join(f"{k} = {v}" for k, v in facts.items())
        lines.append(f"Diese Fakten exakt übernehmen: {exact}")
    lines.append(f"Originalantwort: {plain}")
    lines.append("Gib nur die neue Antwort aus.")
    return "\n".join(lines)


def clean_llm_output(text):
    text = _THINK.sub("", str(text or "")).strip()
    if len(text) >= 2 and text[0] in _QUOTES and text[-1] in _QUOTES:
        text = text[1:-1].strip()
    return " ".join(text.split())


def call_with_timeout(fn, arg, timeout):
    """Hartes Zeitlimit für beliebige Callables (HA bricht shell_command nach 60 s ab)."""
    box = {}

    def run():
        try:
            box["value"] = fn(arg)
        except BaseException as exc:  # noqa: BLE001 – wird im Hauptthread weitergereicht
            box["error"] = exc

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(timeout)
    if worker.is_alive():
        raise TimeoutError(f"LLM hat nicht innerhalb von {timeout} s geantwortet")
    if "error" in box:
        raise box["error"]
    return box["value"]


def _via_llm(quirk, facts, plain, llm, timeout, persona):
    """Liefert (text | None, grund)."""
    prompt = build_prompt(quirk, facts, plain, persona)
    try:
        raw = call_with_timeout(llm, prompt, timeout)
    except Exception as exc:
        warn(f"LLM-Fehler bei Quirk {quirk.id}: {exc!r}")
        return None, f"LLM-Fehler: {exc}"
    text = clean_llm_output(raw)
    if not text:
        return None, "LLM-Antwort leer"
    if len(text) > max(400, 3 * len(plain)):
        return None, "LLM-Antwort zu lang"
    if not facts_present(text, facts, quirk.guard_keys(facts)):
        return None, "LLM-Antwort ohne alle Fakten verworfen"
    return text, "LLM"


def explain(plain, facts=None, project=None, texts=None, quirks=(), llm=None,
            llm_share=0.4, rng=None, persona="", llm_timeout=25):
    """Wie apply(), liefert aber ein Outcome mit Begründung (für CLI und Tests)."""
    facts = dict(facts or {})
    rng = rng or random.Random()
    try:
        matches = find(quirks, texts if texts is not None else [plain], project)
        if not matches:
            return Outcome(plain, reason="kein Quirk passt")
        quirk = matches[0].quirk
        outcome = Outcome(plain, quirk=quirk, matches=matches)

        roll = rng.random()
        if roll >= quirk.chance:
            outcome.reason = f"chance {quirk.chance} nicht erreicht (Wurf {roll:.2f})"
            return outcome

        templates = quirk.rendered_templates(facts)
        use_llm = llm is not None and (not templates or rng.random() < llm_share)
        if use_llm:
            text, reason = _via_llm(quirk, facts, plain, llm, llm_timeout, persona)
            if text:
                outcome.text, outcome.source, outcome.reason = text, "llm", reason
                return outcome
            outcome.reason = reason + "; "
        if templates:
            outcome.text, outcome.source = rng.choice(templates), "vorlage"
            outcome.reason += "Vorlage"
            return outcome
        outcome.reason += "keine passende Vorlage"
        return outcome
    except Exception as exc:  # reveries darf die Suche nie kaputt machen
        warn(f"interner Fehler, Originalantwort bleibt: {exc!r}")
        return Outcome(plain, reason=f"interner Fehler: {exc!r}")


def apply(plain, facts=None, project=None, texts=None, quirks=(), llm=None,
          llm_share=0.4, rng=None, persona="", llm_timeout=25):
    """Gibt die vermenschlichte Antwort zurück oder unverändert plain.

    plain       – deterministische Originalantwort
    facts       – Werte für Platzhalter; alle (bzw. die im Quirk unter guard
                  genannten) müssen in der Ausgabe stehen
    project     – Name für den scope-Filter; None filtert nicht
    texts       – Texte fürs Matching (z. B. Nutzerfrage + DB-Titel); Default [plain]
    llm         – optional, Callable str -> str; wird nur bei einem Treffer gerufen
    llm_share   – Anteil der Treffer, die per LLM statt Vorlage formuliert werden
    rng         – random.Random für reproduzierbare Ergebnisse
    persona     – globaler Grundton für den LLM-Prompt (siehe load_persona)
    llm_timeout – hartes Zeitlimit für den LLM-Aufruf in Sekunden
    """
    return explain(plain, facts, project, texts, quirks, llm, llm_share, rng,
                   persona, llm_timeout).text
