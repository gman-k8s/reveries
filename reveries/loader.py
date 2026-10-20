"""Quirk-Dateien (Markdown + YAML-Frontmatter) lesen und prüfen.

Defekte Dateien werden übersprungen und auf stderr gemeldet – sie dürfen die
aufrufende Suche nie kaputt machen.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from .log import warn
from .matcher import normalize
from .quirk import Quirk, placeholder_root, placeholders

try:
    import yaml
except ImportError:  # pragma: no cover - im HA-Container vorhanden
    yaml = None

KNOWN_KEYS = {"id", "match", "scope", "chance", "priority", "guard"}
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_LIST_ITEM = re.compile(r"^\s*[-*+]\s+(.*)$")
_TEMPLATE_HEADINGS = {"vorlagen", "vorlage", "templates", "antworten"}
_ATTITUDE_HEADINGS = {"haltung", "attitude"}
_ATTITUDE_LABEL = re.compile(r"^(?:haltung|attitude)\s*:\s*", re.I)


@dataclass
class Problem:
    path: Path
    level: str  # "fehler" | "warnung"
    message: str

    def __str__(self):
        return f"{self.path}: {self.level.upper()}: {self.message}"


class QuirkError(ValueError):
    pass


def split_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise QuirkError("Frontmatter fehlt (Datei muss mit „---“ beginnen)")
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() in ("---", "..."):
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1:])
    raise QuirkError("Frontmatter wird nicht mit „---“ abgeschlossen")


def parse_body(body):
    """Teilt den Markdown-Körper in Haltung und Vorlagen. Andere Abschnitte sind Notizen."""
    attitude, templates = [], []
    section = "attitude"
    for line in body.splitlines():
        heading = _HEADING.match(line)
        if heading:
            name = heading.group(1).strip().lower().rstrip(":")
            section = ("templates" if name in _TEMPLATE_HEADINGS
                       else "attitude" if name in _ATTITUDE_HEADINGS else "notes")
            continue
        if section == "attitude":
            attitude.append(line)
        elif section == "templates":
            item = _LIST_ITEM.match(line)
            if item:
                templates.append(item.group(1).strip())
            elif line.strip() and templates and line[:1].isspace():
                templates[-1] += " " + line.strip()  # eingerückte Fortsetzungszeile
    attitude = _ATTITUDE_LABEL.sub("", "\n".join(attitude).strip(), count=1)
    return attitude, [t for t in templates if t]


def _string_list(meta, key, errors, default=None):
    value = meta.get(key, default)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, (str, int, float)) for v in value):
        errors.append(f"„{key}“ muss eine Liste von Texten sein")
        return default
    return [str(v) for v in value]


def parse_quirk(path):
    """Liest eine Datei. Liefert (Quirk | None, [Problem])."""
    path = Path(path)
    errors, warnings = [], []

    def result(quirk=None):
        return quirk, ([Problem(path, "fehler", e) for e in errors]
                       + [Problem(path, "warnung", w) for w in warnings])

    if yaml is None:
        errors.append("PyYAML ist nicht installiert")
        return result()
    try:
        front, body = split_frontmatter(path.read_text(encoding="utf-8-sig"))
        meta = yaml.safe_load(front) if front.strip() else {}
    except (OSError, UnicodeDecodeError, QuirkError) as exc:
        errors.append(str(exc))
        return result()
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        where = f" (Zeile {mark.line + 2})" if mark else ""
        errors.append(f"Frontmatter ist kein gültiges YAML{where}: {getattr(exc, 'problem', exc)}")
        return result()
    if not isinstance(meta, dict):
        errors.append("Frontmatter muss aus „schlüssel: wert“-Zeilen bestehen")
        return result()

    for key in sorted(set(meta) - KNOWN_KEYS):
        warnings.append(f"unbekanntes Feld „{key}“ wird ignoriert (Tippfehler?)")

    quirk_id = meta.get("id")
    if not isinstance(quirk_id, str) or not quirk_id.strip():
        errors.append("Pflichtfeld „id“ fehlt oder ist leer")

    match = _string_list(meta, "match", errors, default=[])
    if "match" not in meta:
        errors.append("Pflichtfeld „match“ fehlt")
    elif match is not None and not match:
        errors.append("„match“ ist leer – der Quirk würde nie greifen")

    scope = _string_list(meta, "scope", errors, default=["*"])

    chance = meta.get("chance", 1.0)
    if isinstance(chance, bool) or not isinstance(chance, (int, float)) or not 0 <= chance <= 1:
        errors.append(f"„chance“ muss eine Zahl zwischen 0 und 1 sein, nicht {chance!r}")
    elif chance == 0:
        warnings.append("„chance: 0“ – der Quirk greift nie")

    priority = meta.get("priority", 0)
    if isinstance(priority, bool) or not isinstance(priority, int):
        errors.append(f"„priority“ muss eine ganze Zahl sein, nicht {priority!r}")

    guard = _string_list(meta, "guard", errors) if "guard" in meta else None

    attitude, templates = parse_body(body)
    for template in templates:
        try:
            names = placeholders(template)
        except ValueError as exc:
            errors.append(f"Vorlage mit kaputten Klammern ({exc}): {template}")
            continue
        bad = [n for n in names if not n.isidentifier()]
        if bad:
            errors.append(f"Platzhalter {', '.join('{' + b + '}' for b in bad)} ungültig, "
                          f"nur einfache Namen wie {{kiste}}: {template}")
        if not names:
            warnings.append(f"Vorlage ohne Platzhalter – Fakten wie die Kiste fehlen: {template}")
        elif guard and not {placeholder_root(n) for n in names} >= set(guard):
            missing = ", ".join("{" + g + "}" for g in guard if g not in names)
            warnings.append(f"Vorlage ohne {missing} aus „guard“ – wird nie verwendet: {template}")
    if not templates and not attitude:
        errors.append("weder Haltung noch Vorlagen – der Quirk hat nichts zu sagen")
    elif not templates:
        warnings.append("keine Vorlagen – der Quirk greift nur mit LLM")
    if match:
        for term in match:
            if not normalize(term):
                errors.append(f"Suchbegriff {term!r} ist nach Normalisierung leer")

    if errors:
        return result()
    return result(Quirk(id=quirk_id.strip(), match=match, scope=scope, chance=float(chance),
                        priority=priority, guard=guard, attitude=attitude,
                        templates=templates, source=path))


def quirk_files(path):
    path = Path(path)
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    return sorted(p for p in path.rglob("*.md")
                  if p.name.lower() != "readme.md" and not p.name.startswith(("_", ".")))


def check(path):
    """Für lint: alle Quirks plus alle Probleme (inkl. doppelter IDs)."""
    quirks, problems, seen = [], [], {}
    if not Path(path).exists():
        return [], [Problem(Path(path), "fehler", "Pfad existiert nicht")]
    for file in quirk_files(path):
        try:
            quirk, found = parse_quirk(file)
        except Exception as exc:  # Robustheit geht vor
            quirk, found = None, [Problem(file, "fehler", f"unerwarteter Fehler: {exc!r}")]
        problems.extend(found)
        if quirk is None:
            continue
        if quirk.id in seen:
            problems.append(Problem(file, "fehler",
                                    f"doppelte id „{quirk.id}“ (schon in {seen[quirk.id]})"))
            continue
        seen[quirk.id] = file
        quirks.append(quirk)
    return quirks, problems


def load(path):
    """Lädt alle gültigen Quirks unter path (Datei oder Ordner). Wirft nie."""
    try:
        quirks, problems = check(path)
    except Exception as exc:
        warn(f"Quirks unter {path} nicht lesbar: {exc!r}")
        return []
    for problem in problems:
        if problem.level == "fehler":
            warn(f"übersprungen – {problem}")
    return quirks


def load_persona(path):
    """Globaler Grundton (persona.md) ohne Frontmatter; leer, wenn nicht lesbar."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""
    try:
        _, text = split_frontmatter(text)
    except QuirkError:
        pass
    return "\n".join(l for l in text.splitlines() if not l.startswith("#")).strip()
