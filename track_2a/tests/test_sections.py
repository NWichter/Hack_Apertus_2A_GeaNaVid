from booklint.ingest import Booklet, Chunk
from booklint.sections import PREFER, claim_cue, classify, factors


def _booklet(specs):
    chunks = [Chunk(i, page, text, heading, group, note) for i, (page, heading, group, note, text) in enumerate(specs)]
    return Booklet("x.pdf", "0", "de", 10, chunks, 0.0)


def test_classify_inherits_and_marks_committee_pages():
    b = _booklet([
        (2, "In Kürze", "Erste Vorlage: X", "", "Kurz gesagt."),
        (5, "Ausgangslage", "Erste Vorlage: X", "", "Heute gilt."),
        (5, "Neue Regeln", "Erste Vorlage: X", "", "Unterabschnitt."),
        (7, "Argumente", "Erste Vorlage: X", "Der Text auf dieser Doppelseite stammt vom Initiativkomitee.", "Wir finden."),
        (8, "Argumente Bundesrat und Parlament", "Erste Vorlage: X", "", "Der Bundesrat findet."),
        (9, "Abstimmungstext", "Erste Vorlage: X", "", "Art. 1"),
        (9, "Neue Regeln", "Zweite Vorlage: Y", "", "Andere Vorlage."),
    ])
    assert classify(b) == ["overview", "context", "context", "committee", "authorities", "legal", "other"]


def test_claim_cue_languages():
    assert claim_cue("Laut der Zusammenfassung steigt die Steuer.") == "summary"
    assert claim_cue("Selon le texte soumis au vote, la loi entre en vigueur.") == "legal"
    assert claim_cue("Il comitato ritiene che bastino 25 anni.") == "committee"
    assert claim_cue("Der Bundesrat empfiehlt ein Ja.") == "authorities"
    assert claim_cue("Die Steuer steigt.") is None


def test_factors_only_for_matching_sections():
    kinds = ["context", "committee", "legal"]
    assert factors(kinds, "committee", [0, 1, 2], 2.0) == {1: 2.0}
    assert factors(kinds, None, [0, 1, 2], 2.0) == {0: 2.0}
    assert factors(kinds, "legal", [0, 1, 2], 1.0) == {}
    assert PREFER["summary"] == {"context"}


def test_parse_survives_broken_json():
    from booklint.nli import parse

    assert parse({"content": '{"evidence": [1, "label": "contradiction"}'}, 3) == ("contradiction", [])
    assert parse({"content": ""}, 3) == (None, [])
    assert parse({"content": "[1, 2]"}, 3) == (None, [])
