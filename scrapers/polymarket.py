"""Polymarket prediction market via the public gamma API, no auth.

Prices ARE probabilities (0-1). `outcomes` and `outcomePrices` are
JSON-encoded strings; bestBid/bestAsk refer to the Yes outcome.
Tracked events are listed explicitly — add new slugs as Polymarket
creates more Swedish election markets.
"""
import json

from .base import TIMEOUT, get_session, save_observation, slugify

SOURCE = "polymarket"
BASE = "https://gamma-api.polymarket.com"
EVENT_SLUGS = [
    "sweden-parliamentary-election-winner",
    "sweden-parliamentary-election-2nd-place",
    "sweden-parliamentary-election-3rd-place",
    "next-prime-minister-of-sweden",
    "will-tido-parties-win-a-majority-in-the-2026-swedish-parliamentary-elections-20260603233725849",
]


def parse_event(event):
    for market in event["markets"]:
        if not market.get("active") or market.get("closed"):
            continue
        if not market.get("outcomePrices"):
            continue
        labels = json.loads(market["outcomes"])
        prices = [float(p) for p in json.loads(market["outcomePrices"])]
        outcomes = []
        for index, (label, price) in enumerate(zip(labels, prices)):
            outcome = {"label": label, "price": price}
            if index == 0:  # bestBid/bestAsk quote the first (Yes) outcome
                outcome["best_bid"] = market.get("bestBid")
                outcome["best_ask"] = market.get("bestAsk")
            outcomes.append(outcome)
        meta = {
            "slug": slugify(market["slug"]),
            "market_name": market["question"],
            "market_id": market["id"],
            "event_name": event["title"],
            "url": "https://polymarket.com/event/" + event["slug"],
            "odds_format": "probability",
            "volume_usd": market.get("volumeNum"),
        }
        yield meta, outcomes


def scrape(raw_dir=None):
    session = get_session()
    paths = []
    for event_slug in EVENT_SLUGS:
        response = session.get(BASE + "/events", params={"slug": event_slug},
                               timeout=TIMEOUT).json()
        if not response:
            continue
        for market, outcomes in parse_event(response[0]):
            paths.append(save_observation(SOURCE, market, outcomes, raw_dir=raw_dir))
    return paths
