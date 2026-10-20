"""End-to-end mit dem echten lager_suche.py – übersprungen, wenn ../nestegg-locator fehlt."""

import importlib.util
import shutil
import sys

import pytest

from conftest import REPO

NESTEGG = REPO.parent / "nestegg-locator"
pytestmark = pytest.mark.skipif(not (NESTEGG / "lager_suche.py").exists(),
                                reason="nestegg-locator nicht neben reveries ausgecheckt")

EXTRA = (
    '"Indiana Jones und das Königreich des Kristallschädels","DVD","","","","","","Filme",'
    '"Keller » Kiste 4","1","","","","","","","","","",""\n'
    '"Matrix Reloaded","DVD","","","","","","Filme","Keller » Kiste 2","1","","","","","","","","","",""\n'
    '"Matrix Reloaded","Bluray","","","","","","Filme","Keller » Kiste 6","1","","","","","","","","","",""\n'
)


@pytest.fixture
def example(tmp_path, monkeypatch):
    monkeypatch.setenv("REVERIES_DIR", str(REPO))
    monkeypatch.delenv("REVERIES_LLM_URL", raising=False)
    monkeypatch.syspath_prepend(str(NESTEGG))
    spec = importlib.util.spec_from_file_location(
        "lager_suche_integration", REPO / "examples" / "lager_suche_integration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import lager_suche as ls

    csv = tmp_path / "inventar.csv"
    shutil.copy(NESTEGG / "tests" / "fixtures" / "inventar_beispiel.csv", csv)
    with csv.open("a", encoding="utf-8") as fh:
        fh.write(EXTRA)
    config = ls.load_config(None)
    items = ls.load_inventory(csv, config)

    def ask(text):
        _, arg = ls.parse_request(text)
        result = ls.search(items, arg, config["fuzzy_cutoff"])
        return ls.format_search(result, config), module.humanize(
            text, result, ls.format_search(result, config), config)

    return ask


def test_quirk_kicks_in_with_correct_box(example):
    answers = {example("wo ist der kristallschädel")[1] for _ in range(30)}
    quirky = [a for a in answers if "📦" not in a]
    assert quirky, answers
    assert all("Kiste 4" in a for a in answers)


def test_unrelated_and_ambiguous_stay_plain(example):
    for question in ("wo ist die hard", "wo ist matrix reloaded"):
        plain, out = example(question)
        assert out == plain
