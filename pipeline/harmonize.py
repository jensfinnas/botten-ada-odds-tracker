"""Convert source-native odds to comparable probabilities.

Methods (documented in README):
- Bookmaker decimal odds: proportional normalization. Implied probabilities
  1/odds sum to >1 (the overround = bookmaker margin); dividing each by the
  sum removes the margin: p_i = (1/o_i) / sum_j(1/o_j).
- Smarkets exchange quotes: midpoint of best bid/offer (basis points / 10000).
  Exchange prices carry no overround (commission is charged on winnings).
- Polymarket: prices are probabilities; midpoint of bestBid/bestAsk when both
  exist, else the published outcome price.
- Botten Ada: model probability used directly.
"""


def normalize_decimal_odds(odds):
    implied = [1.0 / o for o in odds]
    total = sum(implied)
    return [p / total for p in implied]


def prob_from_smarkets_quote(best_bid, best_offer):
    if best_bid is None or best_offer is None:
        return None
    return (best_bid + best_offer) / 2.0 / 10000.0


def prob_from_observation(odds_format, observation, target_label, require_line=None):
    """Probability of `target_label` in one raw observation, or None if the
    outcome is missing or the O/U line differs from `require_line`."""
    outcomes = observation["outcomes"]
    if require_line is not None:
        outcomes = [o for o in outcomes if o.get("line") == require_line]
    target = next((o for o in outcomes if o["label"] == target_label), None)
    if target is None:
        return None

    if odds_format == "decimal":
        probs = normalize_decimal_odds([o["odds"] for o in outcomes])
        return probs[outcomes.index(target)]
    if odds_format == "smarkets_quotes":
        return prob_from_smarkets_quote(target.get("best_bid"), target.get("best_offer"))
    if odds_format == "probability":
        if "probability" in target:
            return target["probability"]
        if target.get("best_bid") is not None and target.get("best_ask") is not None:
            return (target["best_bid"] + target["best_ask"]) / 2.0
        return target.get("price")
    raise ValueError("unknown odds_format: %s" % odds_format)
