from reveries.__main__ import main

from conftest import INDY


def test_lint_ok(write_quirk, capsys):
    write_quirk("indy.md", INDY)
    assert main(["lint", str(write_quirk.root)]) == 0
    assert "1 Quirk(s) gültig, 0 Fehler" in capsys.readouterr().out


def test_lint_fails_on_errors(write_quirk, capsys):
    write_quirk("indy.md", INDY)
    write_quirk("kaputt.md", "---\nid: x\n---\n")
    assert main(["lint", str(write_quirk.root)]) == 1
    out = capsys.readouterr().out
    assert "kaputt.md: FEHLER: Pflichtfeld „match“ fehlt" in out


def test_test_command(write_quirk, capsys):
    write_quirk("indy.md", INDY)
    assert main(["test", "wo ist indiana jones IV", "--fakt", "kiste=4", "--project", "nestegg",
                 "--quirks", str(write_quirk.root), "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert "→ Treffer: indy" in out
    assert "Antwort:  Es gibt nur drei Filme. Kiste 4." in out
