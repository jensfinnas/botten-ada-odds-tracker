"""Smarkets betting exchange. Official public REST API, no auth.

Quote prices are probability basis points (7353 = 73.53%). Raw files store
best bid/offer per contract; the midpoint becomes the probability at
harmonization time.
"""
from .base import TIMEOUT, get_session, save_observation, slugify

SOURCE = "smarkets"
BASE = "https://api.smarkets.com/v3"
SWEDEN_PARENT_ID = "941513"  # politics/europe/sweden node


def parse_markets(events, markets, contracts, quotes):
    events_by_id = {e["id"]: e for e in events}
    contracts_by_market = {}
    for contract in contracts:
        contracts_by_market.setdefault(contract["market_id"], []).append(contract)

    for market in markets:
        event = events_by_id.get(market["event_id"], {})
        outcomes = []
        for contract in contracts_by_market.get(market["id"], []):
            quote = quotes.get(str(contract["id"])) or {}
            bids = quote.get("bids") or []
            offers = quote.get("offers") or []
            outcomes.append({
                "label": contract["name"],
                "best_bid": bids[0]["price"] if bids else None,
                "best_offer": offers[0]["price"] if offers else None,
            })
        if not outcomes:
            continue
        full_slug = event.get("full_slug")
        meta = {
            "slug": slugify(market.get("slug") or market["name"]),
            "market_name": market["name"],
            "market_id": market["id"],
            "event_name": event.get("name"),
            "url": ("https://smarkets.com" + full_slug) if full_slug
                   else "https://smarkets.com/listing/politics/europe/sweden",
            "odds_format": "smarkets_quotes",
        }
        yield meta, outcomes


def scrape(raw_dir=None):
    session = get_session()
    events = session.get(
        BASE + "/events/",
        params={"parent_id": SWEDEN_PARENT_ID,
                "state": ["new", "upcoming", "live"], "limit": 50},
        timeout=TIMEOUT).json()["events"]
    if not events:
        return []
    event_ids = ",".join(e["id"] for e in events)
    markets = session.get(BASE + "/events/%s/markets/" % event_ids,
                          timeout=TIMEOUT).json()["markets"]
    if not markets:
        return []
    market_ids = ",".join(m["id"] for m in markets)
    contracts = session.get(BASE + "/markets/%s/contracts/" % market_ids,
                            timeout=TIMEOUT).json()["contracts"]
    quotes = session.get(BASE + "/markets/%s/quotes/" % market_ids,
                         timeout=TIMEOUT).json()
    paths = []
    for market, outcomes in parse_markets(events, markets, contracts, quotes):
        paths.append(save_observation(SOURCE, market, outcomes, raw_dir=raw_dir))
    return paths
