from pipeline.mappings import load_mappings
from scrapers.botten_ada import mapped_question_ids, parse_question


def test_mapped_question_ids():
    ids = mapped_question_ids()
    assert "is_L_above_4_pct" in ids
    assert "does_lw_get_more_seats_than_rw" in ids
    assert "does_S_get_most_votes" in ids
    # non-ada questions must not be fetched
    assert "does_Andersson_become_pm" not in ids


def test_parse_question(load_fixture):
    market, outcomes = parse_question(
        "is_L_above_4_pct", load_fixture("botten_ada_is_L_above_4_pct.json"))
    assert market["slug"] == "is_L_above_4_pct"
    assert market["odds_format"] == "probability"
    assert "model_run" in market
    assert outcomes[0]["label"] == "yes"
    assert 0.0 <= outcomes[0]["probability"] <= 1.0


def test_scrape_skips_unpublished_questions(monkeypatch, tmp_path, capsys, load_fixture):
    import scrapers.botten_ada as ada

    published = load_fixture("botten_ada_is_L_above_4_pct.json")

    class FakeResponse:
        def __init__(self, status_code, payload=None):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class FakeSession:
        def get(self, url, timeout=None):
            if "is_L_above_4_pct" in url:
                return FakeResponse(200, published)
            return FakeResponse(403)  # S3 responds 403 for missing keys

    monkeypatch.setattr(ada, "get_session", lambda: FakeSession())
    monkeypatch.setattr(ada, "mapped_question_ids",
                        lambda: ["is_L_above_4_pct", "does_S_get_most_votes"])

    paths = ada.scrape(raw_dir=tmp_path)
    assert [p.name for p in paths] == ["is_L_above_4_pct.json"]
    assert "does_S_get_most_votes" in capsys.readouterr().err
