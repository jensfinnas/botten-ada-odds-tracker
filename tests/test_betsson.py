from scrapers.betsson import parse_widgets


def test_parse_widgets_swedish_markets(load_fixture):
    parsed = list(parse_widgets(load_fixture("betsson_politics.json")))
    slugs = {m["slug"] for m, _ in parsed}
    assert "nasta_riksdagsval_flest_mandat_h2h" in slugs
    assert "nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare" in slugs
    assert "riksdagsvalet_2026_procent_av_rosterna_liberalerna_l_over_under" in slugs
    assert "vem_blir_statsminister_efter_riksdagsvalet_2026_vinnare" in slugs
    # only Swedish region markets
    assert all(m["odds_format"] == "decimal" for m, _ in parsed)

    duel = next(o for m, o in parsed if m["slug"] == "nasta_riksdagsval_flest_mandat_h2h")
    odds = {x["label"]: x["odds"] for x in duel}
    assert odds["S+V+MP+C"] == 1.16
    assert odds["M+SD+KD+L"] == 4.3

    ou_l = next(o for m, o in parsed
                if m["slug"] == "riksdagsvalet_2026_procent_av_rosterna_liberalerna_l_over_under")
    over = next(x for x in ou_l if x["label"] == "Över")
    assert over["line"] == 4.0
    assert over["odds"] == 2.45
