import pytest

from pipeline.harmonize import (normalize_decimal_odds, prob_from_observation,
                                prob_from_smarkets_quote)


def test_normalize_decimal_odds_two_way():
    # 1/1.22 + 1/3.75 = 1.086339...; proportional normalization removes the vig
    probs = normalize_decimal_odds([1.22, 3.75])
    assert probs[0] == pytest.approx(0.75453, abs=1e-4)
    assert probs[1] == pytest.approx(0.24547, abs=1e-4)
    assert sum(probs) == pytest.approx(1.0)


def test_smarkets_quote_midpoint():
    # basis points: bid 7353, offer 7937 -> mid 0.7645
    assert prob_from_smarkets_quote(7353, 7937) == pytest.approx(0.7645)
    assert prob_from_smarkets_quote(None, 7937) is None


def test_prob_from_observation_decimal():
    obs = {"outcomes": [{"label": "A", "odds": 1.22}, {"label": "B", "odds": 3.75}]}
    assert prob_from_observation("decimal", obs, "A") == pytest.approx(0.75453, abs=1e-4)
    assert prob_from_observation("decimal", obs, "missing") is None


def test_prob_from_observation_require_line():
    obs = {"outcomes": [{"label": "Over", "odds": 2.3, "line": 4.0},
                        {"label": "Under", "odds": 1.55, "line": 4.0}]}
    p = prob_from_observation("decimal", obs, "Over", require_line=4.0)
    assert p == pytest.approx((1 / 2.3) / (1 / 2.3 + 1 / 1.55))
    # line moved -> mapping must break rather than pollute the series
    assert prob_from_observation("decimal", obs, "Over", require_line=4.5) is None


def test_prob_from_observation_probability_formats():
    ada = {"outcomes": [{"label": "yes", "probability": 0.971}]}
    assert prob_from_observation("probability", ada, "yes") == 0.971
    poly = {"outcomes": [{"label": "Yes", "price": 0.28, "best_bid": 0.23, "best_ask": 0.33},
                         {"label": "No", "price": 0.72}]}
    assert prob_from_observation("probability", poly, "Yes") == pytest.approx(0.28)
    poly_no_book = {"outcomes": [{"label": "Yes", "price": 0.905}]}
    assert prob_from_observation("probability", poly_no_book, "Yes") == 0.905


def test_prob_from_observation_smarkets():
    obs = {"outcomes": [{"label": "Magdalena Andersson", "best_bid": 7353, "best_offer": 7937}]}
    assert prob_from_observation("smarkets_quotes", obs, "Magdalena Andersson") == pytest.approx(0.7645)
