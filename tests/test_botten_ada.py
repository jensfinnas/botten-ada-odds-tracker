from pipeline.mappings import load_mappings
from scrapers.botten_ada import mapped_question_ids, parse_question


def test_mapped_question_ids():
    ids = mapped_question_ids()
    assert "is_L_above_4_pct" in ids
    assert "does_lw_get_more_seats_than_rw" in ids
    # non-ada questions must not be fetched
    assert "does_S_get_most_votes" not in ids


def test_parse_question(load_fixture):
    market, outcomes = parse_question(
        "is_L_above_4_pct", load_fixture("botten_ada_is_L_above_4_pct.json"))
    assert market["slug"] == "is_L_above_4_pct"
    assert market["odds_format"] == "probability"
    assert "model_run" in market
    assert outcomes[0]["label"] == "yes"
    assert 0.0 <= outcomes[0]["probability"] <= 1.0
