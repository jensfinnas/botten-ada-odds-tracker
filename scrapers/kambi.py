"""Kambi powers Unibet, Svenska Spel Oddset, ATG and Paf with identical odds.

Open CDN API, no auth. Odds are millis (1220 = 1.22); over/under lines are
percent * 1000 (4000 = 4.0%). The election event id may change if Kambi
recreates the event, so it is re-discovered from the politics listing on
every run.
"""
from .base import TIMEOUT, get_session, save_observation, slugify

SOURCE = "kambi"
OFFERING = "ub"  # unibet; same feed available as svenskaspel/atg/paf
BASE = "https://eu-offering-api.kambicdn.com/offering/v2018/" + OFFERING
PARAMS = {"lang": "sv_SE", "market": "SE"}
BET_OFFER_TYPE_HEAD_TO_HEAD = 13


def find_election_event_ids(listing):
    ids = []
    for wrapper in listing.get("events", []):
        event = wrapper["event"]
        term_keys = {p["termKey"] for p in event.get("path", [])}
        if {"sweden", "elections"} <= term_keys:
            ids.append(event["id"])
    return ids


def parse_event(detail):
    event = detail["events"][0]
    for offer in detail["betOffers"]:
        criterion = offer["criterion"]
        slug = slugify("%s %s" % (event["englishName"], criterion["englishLabel"]))
        outcomes = []
        for outcome in offer["outcomes"]:
            if outcome.get("odds") is None:  # suspended
                continue
            parsed = {"label": outcome.get("englishLabel") or outcome["label"],
                      "odds": outcome["odds"] / 1000.0}
            if outcome.get("line") is not None:
                parsed["line"] = outcome["line"] / 1000.0
            outcomes.append(parsed)
        if not outcomes:
            continue
        if offer["betOfferType"]["id"] == BET_OFFER_TYPE_HEAD_TO_HEAD:
            slug += "_" + "_".join(sorted(slugify(o["label"]) for o in outcomes))
        market = {
            "slug": slug,
            "market_name": criterion["label"],
            "market_name_english": criterion["englishLabel"],
            "market_id": "%s/%s" % (event["id"], offer["id"]),
            "criterion_id": criterion["id"],
            "event_name": event["englishName"],
            "url": "https://www.unibet.se/betting/sports/event/%s" % event["id"],
            "odds_format": "decimal",
        }
        yield market, outcomes


def scrape(raw_dir=None):
    session = get_session()
    listing = session.get(BASE + "/listView/politics.json",
                          params=PARAMS, timeout=TIMEOUT).json()
    paths = []
    for event_id in find_election_event_ids(listing):
        detail = session.get(BASE + "/betoffer/event/%s.json" % event_id,
                             params=PARAMS, timeout=TIMEOUT).json()
        for market, outcomes in parse_event(detail):
            paths.append(save_observation(SOURCE, market, outcomes, raw_dir=raw_dir))
    return paths
