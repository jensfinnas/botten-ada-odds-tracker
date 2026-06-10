from scrapers.smarkets import parse_markets


def test_parse_markets(load_fixture):
    parsed = list(parse_markets(load_fixture("smarkets_events.json")["events"],
                                load_fixture("smarkets_markets.json")["markets"],
                                load_fixture("smarkets_contracts.json")["contracts"],
                                load_fixture("smarkets_quotes.json")))
    slugs = {m["slug"] for m, _ in parsed}
    assert slugs == {"next_swedish_prime_minister",
                     "2026_swedish_general_election_most_seats"}

    pm = next(o for m, o in parsed if m["slug"] == "next_swedish_prime_minister")
    andersson = next(x for x in pm if x["label"] == "Magdalena Andersson")
    assert andersson["best_bid"] == 7353
    assert andersson["best_offer"] == 7937

    meta = next(m for m, _ in parsed if m["slug"] == "next_swedish_prime_minister")
    assert meta["odds_format"] == "smarkets_quotes"
