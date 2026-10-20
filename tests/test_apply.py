import random
import time

import pytest

from reveries import Quirk, apply, explain

PLAIN = "Indiana Jones und das Königreich des Kristallschädels liegt in Kiste 4."
FACTS = {"kiste": 4, "titel": "Indiana Jones und das Königreich des Kristallschädels"}
TEXTS = ["wo ist indiana jones 4?", FACTS["titel"]]


def indy(**kw):
    defaults = dict(id="indy", match=["indiana jones 4"], scope=["nestegg"], guard=["kiste"],
                    attitude="Es gibt nur drei Filme.",
                    templates=["Es gibt nur drei Filme. Kiste {kiste}."])
    defaults.update(kw)
    return Quirk(**defaults)


def run(quirks, **kw):
    args = dict(plain=PLAIN, facts=FACTS, project="nestegg", texts=TEXTS, quirks=quirks,
                rng=random.Random(0))
    args.update(kw)
    return explain(**args)


def test_no_match_returns_plain_untouched():
    out = run([indy()], texts=["wo ist galaxy quest"])
    assert out.text == PLAIN and out.source == "original"


def test_template_is_filled():
    assert run([indy()]).text == "Es gibt nur drei Filme. Kiste 4."


def test_scope_mismatch_returns_plain():
    assert run([indy()], project="kochbuch").text == PLAIN


def test_template_with_missing_placeholder_is_skipped():
    q = indy(templates=["Kiste {kiste}, Regal {regal}.", "Nur Kiste {kiste}."])
    for seed in range(20):
        assert run([q], rng=random.Random(seed)).text == "Nur Kiste 4."


def test_template_without_guarded_fact_is_skipped():
    q = indy(templates=["Gibt's nicht."])
    assert run([q]).text == PLAIN


def test_default_guard_requires_all_facts():
    q = indy(guard=None, templates=["Kiste {kiste}."])   # titel fehlt in der Vorlage
    assert run([q]).text == PLAIN
    q = indy(guard=None, templates=["{titel}? Kiste {kiste}."])
    assert run([q]).text.endswith("Kiste 4.")


def test_chance_with_fixed_seed():
    q = indy(chance=0.3)
    rng = random.Random(1234)
    hits = sum(run([q], rng=rng).source == "vorlage" for _ in range(2000))
    assert 0.25 < hits / 2000 < 0.35
    # gleicher Seed → gleiches Ergebnis
    a = [run([q], rng=random.Random(7)).text for _ in range(5)]
    assert len(set(a)) == 1
    assert run([indy(chance=0.0)]).text == PLAIN


def test_priority_decides_between_quirks():
    low = indy(id="low", templates=["low {kiste}"])
    high = indy(id="high", priority=1, templates=["high {kiste}"])
    assert run([low, high]).text == "high 4"


def test_llm_is_used_and_gets_only_the_matching_quirk():
    prompts = []
    other = Quirk(id="other", match=["galaxy quest"], attitude="GEHEIM-ANDERER-QUIRK",
                  templates=["x {kiste}"])

    def llm(prompt):
        prompts.append(prompt)
        return "„Nur drei Filme, aber gut: Kiste 4.“"

    out = run([indy(), other], llm=llm, llm_share=1.0, persona="Du bist der Keller.")
    assert out.source == "llm"
    assert out.text == "Nur drei Filme, aber gut: Kiste 4."
    [prompt] = prompts
    assert "Es gibt nur drei Filme." in prompt
    assert "GEHEIM-ANDERER-QUIRK" not in prompt
    assert "kiste = 4" in prompt and PLAIN in prompt and "Du bist der Keller." in prompt


def test_llm_not_called_without_match():
    def llm(prompt):
        raise AssertionError("darf nicht aufgerufen werden")
    assert run([indy()], llm=llm, llm_share=1.0, texts=["galaxy quest"]).text == PLAIN


@pytest.mark.parametrize("answer", [
    "Nur drei Filme. Schau halt im Keller.",   # Kiste fehlt
    "Kiste 14, glaub ich.",                    # falsche Zahl trotz „4“ als Teilstring
    "Kiste IV.",                               # römisch zählt nicht
    "",
    "<think>Kiste 4</think>",                  # nur im Denkblock
])
def test_fact_guard_rejects_llm_answer(answer):
    q = indy(templates=[])
    assert run([q], llm=lambda p: answer, llm_share=1.0).text == PLAIN


def test_fact_guard_falls_back_to_template():
    out = run([indy()], llm=lambda p: "Keine Ahnung.", llm_share=1.0)
    assert out.source == "vorlage" and out.text == "Es gibt nur drei Filme. Kiste 4."


def test_llm_exception_returns_plain(capsys):
    def boom(prompt):
        raise ConnectionError("Server weg")
    assert run([indy(templates=[])], llm=boom, llm_share=1.0).text == PLAIN
    assert "Server weg" in capsys.readouterr().err


def test_llm_timeout_returns_plain():
    def slow(prompt):
        time.sleep(2)
        return "Kiste 4"
    start = time.monotonic()
    out = run([indy(templates=[])], llm=slow, llm_share=1.0, llm_timeout=0.2)
    assert out.text == PLAIN
    assert time.monotonic() - start < 1.5


def test_llm_share_zero_uses_template():
    def llm(prompt):
        raise AssertionError("llm_share=0 → kein Aufruf")
    assert run([indy()], llm=llm, llm_share=0.0).source == "vorlage"


def test_apply_returns_string_and_never_raises():
    class Kaputt:
        id = "kaputt"
        scope = ["*"]
        priority = "keine zahl"   # bringt das Sortieren zum Absturz
        patterns = ["indiana jones 4"]
    assert apply(PLAIN, FACTS, "nestegg", TEXTS, [Kaputt(), indy()]) == PLAIN
    assert isinstance(apply(PLAIN, FACTS, "nestegg", TEXTS, [indy()], rng=random.Random(0)), str)


def test_texts_default_to_plain():
    q = indy(match=["kristallschädel"])
    assert apply(PLAIN, FACTS, quirks=[q], rng=random.Random(0)) == "Es gibt nur drei Filme. Kiste 4."
