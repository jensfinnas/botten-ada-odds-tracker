from scrapers.kambi import find_election_event_ids, parse_event


def test_find_election_event_ids(load_fixture):
    ids = find_election_event_ids(load_fixture("kambi_listview_politics.json"))
    assert ids == [1020265650]


def test_parse_event(load_fixture):
    # parse_event yields (market, outcomes) tuples
    parsed = list(parse_event(load_fixture("kambi_event_1020265650.json")))
    slugs = {m["slug"] for m, _ in parsed}
    assert "2026_swedish_general_election_party_coalition_to_obtain_most_seats" in slugs
    assert "2026_swedish_general_election_percentage_of_votes_obtained_liberals_l" in slugs
    assert ("2026_swedish_general_election_party_to_get_most_votes_"
            "moderate_party_m_sweden_democrats_sd") in slugs

    market, outcomes = next(
        (m, o) for m, o in parsed
        if m["slug"].endswith("party_coalition_to_obtain_most_seats"))
    assert market["odds_format"] == "decimal"
    assert market["market_name_english"] == "Party/Coalition to obtain most seats"
    odds = {o["label"]: o["odds"] for o in outcomes}
    assert odds["(s)+(v)+(mp)+(c)"] == 1.22
    assert odds["(m)+(sd)+(kd)+(l)"] == 3.75

    ou_l = next(o for m, o in parsed
                if m["slug"].endswith("percentage_of_votes_obtained_liberals_l"))
    over = next(x for x in ou_l if x["label"] == "Over")
    assert over["line"] == 4.0
    assert over["odds"] == 2.3
