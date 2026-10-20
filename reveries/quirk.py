"""Datenmodell eines Quirks und Vorlagen-Logik."""

import re
import string
from dataclasses import dataclass, field
from pathlib import Path

from .matcher import normalize

_FORMATTER = string.Formatter()


def placeholders(template):
    """Platzhalternamen einer Vorlage. Wirft ValueError bei kaputten Klammern."""
    names = set()
    for _, name, _, _ in _FORMATTER.parse(template):
        if name is not None:
            names.add(name)
    return names


def placeholder_root(name):
    return re.split(r"[.\[]", name, maxsplit=1)[0]


def facts_present(text, facts, keys):
    """Stehen alle Faktenwerte (normalisiert, mit Wortgrenze) im Text?

    Römische Zahlen werden hier nicht umgewandelt: „Kiste IV“ zählt nicht als „4“.
    """
    text_norm = f" {normalize(text, roman=False)} "
    for key in keys:
        if key not in facts:
            continue
        value = normalize(facts[key], roman=False)
        if value and f" {value} " not in text_norm:
            return False
    return True


@dataclass
class Quirk:
    id: str
    match: list
    scope: list = field(default_factory=lambda: ["*"])
    chance: float = 1.0
    priority: int = 0
    guard: list | None = None   # None = alle übergebenen Fakten sind Pflicht
    attitude: str = ""
    templates: list = field(default_factory=list)
    source: Path | None = None
    patterns: list = field(init=False, repr=False)

    def __post_init__(self):
        self.patterns = [p for p in (normalize(m) for m in self.match) if p]

    def guard_keys(self, facts):
        return list(facts) if self.guard is None else [k for k in self.guard if k in facts]

    def render(self, template, facts):
        """Gefüllte Vorlage oder None (fehlender Platzhalter, Formatfehler, Fakt fehlt)."""
        values = {k: str(v) for k, v in facts.items()}
        try:
            if any(placeholder_root(p) not in values for p in placeholders(template)):
                return None
            text = template.format_map(values)
        except (ValueError, KeyError, IndexError, AttributeError):
            return None
        return text if facts_present(text, facts, self.guard_keys(facts)) else None

    def rendered_templates(self, facts):
        return [t for t in (self.render(t, facts) for t in self.templates) if t]
