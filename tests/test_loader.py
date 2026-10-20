from reveries import check, load, load_persona
from reveries.loader import parse_quirk

from conftest import INDY, REPO


def test_parses_frontmatter_and_body(write_quirk):
    path = write_quirk("filme/indy.md", INDY)
    q, problems = parse_quirk(path)
    assert problems == []
    assert q.id == "indy"
    assert q.scope == ["nestegg"]
    assert q.chance == 1.0 and q.priority == 0
    assert q.guard == ["kiste"]
    assert q.attitude == "Es gibt nur drei Indiana-Jones-Filme."
    assert q.templates == ["Es gibt nur drei Filme. Kiste {kiste}."]
    assert q.patterns == ["indiana jones 4", "kristallschaedel"]


def test_defaults_and_notes_section(write_quirk):
    write_quirk("x.md", """
        ---
        id: x
        match: einzeln
        ---
        Trocken.

        ## Vorlagen
        - Erste {kiste}
          mit Fortsetzung.
        * Zweite {kiste}

        ## Notizen
        - keine Vorlage
    """)
    [q] = load(write_quirk.root)
    assert q.scope == ["*"] and q.match == ["einzeln"]
    assert q.templates == ["Erste {kiste} mit Fortsetzung.", "Zweite {kiste}"]


def test_broken_files_are_skipped_and_logged(write_quirk, capsys):
    write_quirk("ok.md", INDY)
    write_quirk("kein-frontmatter.md", "nur text\n")
    write_quirk("kaputtes-yaml.md", "---\nid: [unclosed\n---\nx\n")
    write_quirk("ohne-match.md", "---\nid: leer\n---\n## Vorlagen\n- Kiste {kiste}\n")
    write_quirk("chance.md", "---\nid: c\nmatch: [a]\nchance: 2\n---\nx\n")
    (write_quirk.root / "binaer.md").write_bytes(b"\xff\xfe\x00garbage")
    quirks = load(write_quirk.root)
    assert [q.id for q in quirks] == ["indy"]
    err = capsys.readouterr().err
    for name in ("kein-frontmatter", "kaputtes-yaml", "ohne-match", "chance", "binaer"):
        assert name in err


def test_duplicate_ids(write_quirk):
    write_quirk("a.md", INDY)
    write_quirk("b.md", INDY)
    quirks, problems = check(write_quirk.root)
    assert len(quirks) == 1
    assert any("doppelte id" in p.message for p in problems)


def test_template_checks(write_quirk):
    write_quirk("t.md", """
        ---
        id: t
        match: [a]
        guard: [kiste]
        tippfehler: 1
        ---
        ## Vorlagen
        - kaputt {kiste
        - ohne platzhalter
        - nur {titel}
        - attribut {kiste.real}
    """)
    _, problems = check(write_quirk.root)
    text = "\n".join(str(p) for p in problems)
    assert "kaputten Klammern" in text
    assert "ohne Platzhalter" in text
    assert "wird nie verwendet" in text
    assert "ungültig" in text
    assert "tippfehler" in text


def test_missing_path_does_not_raise(tmp_path):
    assert load(tmp_path / "gibtsnicht") == []


def test_example_quirks_are_valid():
    quirks, problems = check(REPO / "quirks")
    assert [p for p in problems if p.level == "fehler"] == []
    assert len(quirks) >= 3


def test_persona(tmp_path):
    assert "Keller" in load_persona(REPO / "persona.md")
    assert not load_persona(REPO / "persona.md").startswith("#")
    assert load_persona(tmp_path / "fehlt.md") == ""
