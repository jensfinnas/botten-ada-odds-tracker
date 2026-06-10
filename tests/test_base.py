import json

from scrapers.base import save_observation, slugify


def test_slugify_swedish_and_punctuation():
    assert slugify("Nästa Riksdagsval: Flest mandat H2H") == "nasta_riksdagsval_flest_mandat_h2h"
    assert slugify("Party/Coalition to obtain most seats") == "party_coalition_to_obtain_most_seats"
    assert slugify("(s)+(v)+(mp)+(c)") == "s_v_mp_c"


def test_save_observation_creates_file(tmp_path):
    market = {"slug": "test_market", "market_name": "Test", "market_id": "1",
              "url": "https://example.com", "odds_format": "decimal"}
    outcomes = [{"label": "Yes", "odds": 1.5}]
    path = save_observation("kambi", market, outcomes, raw_dir=tmp_path, date="2026-06-10")
    doc = json.loads(path.read_text())
    assert path == tmp_path / "kambi" / "test_market.json"
    assert doc["source"] == "kambi"
    assert doc["market_name"] == "Test"
    assert "slug" not in doc
    assert doc["observations"][0]["date"] == "2026-06-10"
    assert doc["observations"][0]["outcomes"] == outcomes


def test_save_observation_appends_and_replaces_same_date(tmp_path):
    market = {"slug": "m", "market_name": "M", "market_id": "1",
              "url": "u", "odds_format": "decimal"}
    save_observation("kambi", market, [{"label": "A", "odds": 2.0}], raw_dir=tmp_path, date="2026-06-10")
    save_observation("kambi", market, [{"label": "A", "odds": 2.1}], raw_dir=tmp_path, date="2026-06-11")
    path = save_observation("kambi", market, [{"label": "A", "odds": 2.2}], raw_dir=tmp_path, date="2026-06-11")
    doc = json.loads(path.read_text())
    assert [o["date"] for o in doc["observations"]] == ["2026-06-10", "2026-06-11"]
    assert doc["observations"][1]["outcomes"][0]["odds"] == 2.2
