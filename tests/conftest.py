import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent


@pytest.fixture
def write_quirk(tmp_path):
    """Schreibt eine Quirk-Datei in tmp_path/quirks und gibt den Pfad zurück."""
    root = tmp_path / "quirks"
    root.mkdir()

    def write(name, content):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(content).lstrip(), encoding="utf-8")
        return path

    write.root = root
    return write


INDY = """
---
id: indy
match: ["indiana jones 4", "kristallschädel"]
scope: [nestegg]
guard: [kiste]
---
Haltung: Es gibt nur drei Indiana-Jones-Filme.

## Vorlagen
- Es gibt nur drei Filme. Kiste {kiste}.
"""
