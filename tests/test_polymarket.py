from scrapers.polymarket import parse_event


def test_parse_winner_event(load_fixture):
    parsed = list(parse_event(load_fixture("polymarket_event_winner.json")[0]))
    # 9 active party markets; 27 inactive placeholders must be filtered out
    assert len(parsed) == 9
    market, outcomes = next(
        (m, o) for m, o in parsed
        if m["slug"].startswith("will_the_swedish_social_democratic_party"))
    assert market["odds_format"] == "probability"
    assert market["market_name"].startswith("Will the Swedish Social Democratic Party")
    yes = next(x for x in outcomes if x["label"] == "Yes")
    assert yes["price"] == 0.905
    assert yes["best_bid"] == 0.9
    assert yes["best_ask"] == 0.91
    no = next(x for x in outcomes if x["label"] == "No")
    assert no["price"] == 0.095


def test_parse_tido_event(load_fixture):
    parsed = list(parse_event(load_fixture("polymarket_event_tido.json")[0]))
    assert len(parsed) == 1
    market, outcomes = parsed[0]
    assert market["market_name"] == (
        "Will Tidö parties win a majority in the 2026 Swedish parliamentary elections?")
    yes = next(x for x in outcomes if x["label"] == "Yes")
    assert yes["price"] == 0.28
