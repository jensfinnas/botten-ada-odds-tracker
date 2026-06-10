from . import betsson, botten_ada, kambi, polymarket, smarkets

SCRAPERS = {
    "botten_ada": botten_ada.scrape,
    "kambi": kambi.scrape,
    "betsson": betsson.scrape,
    "smarkets": smarkets.scrape,
    "polymarket": polymarket.scrape,
}
