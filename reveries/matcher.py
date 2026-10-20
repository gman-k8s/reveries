"""Normalisierung und String-Matching – bewusst ohne LLM."""

import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_APOSTROPHE = re.compile(r"['’`´]")
_TRENNER = re.compile(r"[\W_]+")


def _roman(n):
    out = ""
    for value, symbol in ((10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= value:
            out += symbol
            n -= value
    return out


# „i“ fehlt absichtlich: im Englischen ein normales Wort („i robot“).
_ROEMISCH = {_roman(n): str(n) for n in range(2, 21)}


def normalize(text, roman=True):
    """Vergleichsform: klein, ä→ae, ohne Akzente/Satzzeichen, „iv“→„4“.

    Wird symmetrisch auf Muster und Texte angewendet, deshalb funktionieren
    „Kristallschädel“ und „kristallschaedel“ gleichermaßen.
    """
    text = unicodedata.normalize("NFKC", str(text)).lower().translate(_UMLAUTE)
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))
    tokens = _TRENNER.sub(" ", _APOSTROPHE.sub("", text)).split()
    if roman:
        tokens = [_ROEMISCH.get(t, t) for t in tokens]
    return " ".join(tokens)


@lru_cache(maxsize=4096)
def _term_regex(term_norm):
    # Endet der Begriff auf ein Wort (nicht auf eine Zahl), sind übliche deutsche
    # Endungen erlaubt: „kristallschaedel“ trifft „des Kristallschädels“.
    last_word = term_norm.split()[-1]
    suffix = r"(?:s|es|n|en|e|er)?" if last_word.isalpha() and len(last_word) >= 4 else ""
    return re.compile(rf"(?<!\S){re.escape(term_norm)}{suffix}(?!\S)")


def contains(text_norm, term_norm):
    """Wortgrenzen-sicher: „indiana jones 4“ passt nicht in „indiana jones 40“."""
    return bool(term_norm) and _term_regex(term_norm).search(text_norm) is not None


@dataclass(frozen=True)
class Match:
    quirk: object
    term: str        # normalisierter Suchbegriff, der getroffen hat
    text_index: int  # in welchem der übergebenen Texte


def in_scope(quirk, project):
    """project=None filtert nicht (praktisch für Tests und die CLI)."""
    if project is None:
        return True
    scope = {s.lower() for s in quirk.scope}
    return "*" in scope or project.lower() in scope


def find(quirks, texts, project=None):
    """Alle passenden Quirks, bester zuerst (priority, dann längster Begriff, dann id)."""
    if isinstance(texts, str):
        texts = [texts]
    normalized = [normalize(t) for t in texts if t]
    matches = []
    for quirk in quirks:
        if not in_scope(quirk, project):
            continue
        best = None
        for term in quirk.patterns:
            for index, text in enumerate(normalized):
                if contains(text, term) and (best is None or len(term) > len(best.term)):
                    best = Match(quirk, term, index)
        if best:
            matches.append(best)
    matches.sort(key=lambda m: (-m.quirk.priority, -len(m.term), m.quirk.id))
    return matches
