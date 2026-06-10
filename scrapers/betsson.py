"""Betsson sportsbook widget API.

No login needed, but AWS WAF blocks non-browser user agents (403) and the
API requires brandid + marketcode headers (400 without). The remaining
context headers make responses stable. Content is jurisdiction-filtered;
if runs from non-EU datacenter IPs stop returning Swedish markets, this
source fails in isolation and the clean CSV column goes empty.
"""
from .base import TIMEOUT, get_session, save_observation, slugify

SOURCE = "betsson"
URL = ("https://www.betsson.com/api/sb/v1/widgets/view/v1"
       "?categoryIds=31&configurationKey=sportsbook.category"
       "&excludedWidgetKeys=sportsbook.tournament.carousel&nodeIdentifier=31"
       "&slug=politik-och-naringsliv&timezoneOffsetMinutes=120&priceFormats=1")
PAGE_URL = "https://www.betsson.com/sv/odds/politik-och-naringsliv"
HEADERS = {
    "accept": "application/json, text/plain, */*",
    "brandid": "6a6d80b9-16ac-4387-a413-244d93a74deb",
    "marketcode": "sv",
    "x-sb-jurisdiction": "Sga",
    "x-sb-content-id": "6a6d80b9-16ac-4387-a413-244d93a74deb",
    "x-sb-static-context-id": "stc--412615874",
    "x-sb-user-context-id": "stc--412615874",
    "x-sb-type": "b2b",
    "x-sb-segment-id": "45c98893-208e-40e8-b84b-ab4ae1c83609",
    "x-sb-app-version": "7.37.31.3608-rd8be260",
    "x-sb-language-code": "sv",
    "x-sb-country-code": "SE",
    "x-sb-currency-code": "SEK",
    "x-sb-channel": "Web",
    "x-sb-identifier": "SPORTSBOOK_CATEGORY_WIDGET_REQUEST",
    "user-agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"),
    "referer": PAGE_URL,
}
REGION = "Sverige"


def parse_widgets(payload):
    widget = next(w for w in payload["data"]["widgets"]
                  if w.get("key") == "sportsbook.category.outrights")
    data = widget["data"]["data"]
    events = {e["id"]: e for e in data["events"]}
    selections = {}
    for selection in data["selections"]:
        selections.setdefault(selection["marketId"], []).append(selection)

    for market in data["markets"]:
        event = events.get(market["eventId"])
        if event is None or event.get("regionName") != REGION:
            continue
        market_label = market.get("marketFriendlyName") or market.get("label") or ""
        line = market.get("lineValueRaw")
        outcomes = []
        for selection in selections.get(market["id"], []):
            if not selection.get("odds"):
                continue
            label = selection["label"]
            if line is not None:
                lowered = label.lower()
                if lowered.startswith(("över", "over")):
                    label = "Över"
                elif lowered.startswith("under"):
                    label = "Under"
            parsed = {"label": label, "odds": selection["odds"]}
            if line is not None:
                parsed["line"] = float(line)
            outcomes.append(parsed)
        if not outcomes:
            continue
        meta = {
            "slug": slugify("%s %s" % (event["label"], market_label)),
            "market_name": "%s – %s" % (event["label"], market_label),
            "market_id": market["id"],
            "event_name": event["label"],
            "url": PAGE_URL,
            "odds_format": "decimal",
        }
        yield meta, outcomes


def scrape(raw_dir=None):
    session = get_session()
    response = session.get(URL, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    if "json" not in response.headers.get("content-type", ""):
        raise RuntimeError(
            "Betsson returned non-JSON (geo-blocked? runs from non-EU IPs "
            "are known to fail); content-type=%s"
            % response.headers.get("content-type"))
    paths = []
    for market, outcomes in parse_widgets(response.json()):
        paths.append(save_observation(SOURCE, market, outcomes, raw_dir=raw_dir))
    return paths
