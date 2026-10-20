import pytest

from reveries import Quirk, find, normalize


def quirk(id="q", match=("indiana jones 4",), **kw):
    return Quirk(id=id, match=list(match), templates=["Kiste {kiste}."], **kw)


@pytest.mark.parametrize("raw, expected", [
    ("Indiana  Jones\tIV!", "indiana jones 4"),
    ("Kristallschädel", "kristallschaedel"),
    ("KRISTALLSCHAEDEL", "kristallschaedel"),
    ("Straße", "strasse"),
    ("Amélie", "amelie"),
    ("Ocean’s Eleven", "oceans eleven"),
    ("ｆｕｌｌｗｉｄｔｈ", "fullwidth"),         # NFKC
    ("Highlander II – Die Rückkehr", "highlander 2 die rueckkehr"),
    ("i robot", "i robot"),                     # „i“ bleibt ein Wort
])
def test_normalize(raw, expected):
    assert normalize(raw) == expected


@pytest.mark.parametrize("text", [
    "wo ist Indiana Jones 4?",
    "indiana jones iv",
    "INDIANA-JONES 4",
    "Indiana Jones und das Königreich des Kristallschädels",
    "kristallschaedel",
])
def test_match_variants(text):
    q = quirk(match=["indiana jones 4", "kristallschädel"])
    assert find([q], [text])


@pytest.mark.parametrize("text", ["indiana jones 40", "indiana jones 14", "indiana jones",
                                  "indiana jones 4s", "kristallschädelsammlung"])
def test_word_boundaries(text):
    q = quirk(match=["indiana jones 4", "kristallschädel"])
    assert not find([q], [text])


def test_german_inflection_only_for_words():
    assert find([quirk(match=["netzteil"])], ["wo sind die netzteile"])
    assert find([quirk(match=["kabel"])], ["alle kabeln"])
    assert not find([quirk(match=["rad"])], ["rades"])     # zu kurz für Endungen
    assert not find([quirk(match=["netzteil"])], ["netzteilchen"])


def test_matches_any_of_several_texts():
    q = quirk(match=["kristallschädel"])
    matches = find([q], ["wo ist der vierte indy?", "Indiana Jones – Kristallschädel"])
    assert matches and matches[0].text_index == 1


def test_scope_filter():
    only_nestegg = quirk("a", scope=["nestegg"])
    everywhere = quirk("b", scope=["*"])
    other = quirk("c", scope=["kochbuch"])
    ids = lambda project: {m.quirk.id for m in find([only_nestegg, everywhere, other],
                                                    ["indiana jones 4"], project)}
    assert ids("nestegg") == {"a", "b"}
    assert ids("NestEgg") == {"a", "b"}
    assert ids("kochbuch") == {"b", "c"}
    assert ids(None) == {"a", "b", "c"}


def test_priority_then_specificity():
    low = quirk("low", match=["indiana jones 4"], priority=0)
    high = quirk("high", match=["indiana"], priority=5)
    assert find([low, high], ["indiana jones 4"])[0].quirk.id == "high"

    short = quirk("short", match=["indiana"])
    long = quirk("long", match=["indiana jones 4"])
    assert find([short, long], ["indiana jones 4"])[0].quirk.id == "long"
