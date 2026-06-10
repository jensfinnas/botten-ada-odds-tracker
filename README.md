# botten-ada-odds-tracker

Daily tracking of betting odds and prediction-market prices for the **2026
Swedish parliamentary election** (September 13), harmonized into probabilities
and compared with [Botten Ada](https://www.bottenada.se)'s model forecasts.

A GitHub Actions workflow scrapes all sources once a day, commits the raw
odds to this repository, and rebuilds per-question CSV files where every
source is expressed as a probability — so you can follow how betting markets
and a statistical forecasting model disagree (or agree) over time.

## Data layout

```
data/
├── raw/                      # odds exactly as published, one JSON file per market
│   ├── botten_ada/<question_id>.json
│   ├── kambi/<market_slug>.json
│   ├── betsson/<market_slug>.json
│   ├── smarkets/<market_slug>.json
│   └── polymarket/<market_slug>.json
└── clean/
    ├── <question_id>.csv     # harmonized probabilities, one column per source
    └── QUESTIONS.md          # auto-generated: every question + exact market wordings
```

**Raw files** keep the source's native odds format and metadata (market name,
URL, identifiers). One observation is appended per day:

```json
{
  "source": "kambi",
  "market_name": "Vinner flest platser",
  "odds_format": "decimal",
  "observations": [
    {"date": "2026-06-10", "fetched_at": "2026-06-10T05:01:13Z",
     "outcomes": [{"label": "(s)+(v)+(mp)+(c)", "odds": 1.22},
                  {"label": "(m)+(sd)+(kd)+(l)", "odds": 3.75}]}
  ]
}
```

**Clean files** contain one row per date and one column per source, with
probabilities as fractions 0–1. An empty cell means the source had no
(usable) market that day:

```csv
date,botten_ada,betsson,kambi
2026-06-10,0.971,0.79,0.7545
```

Questions are **binary** ("Will S become the largest party?", not "Which
party wins?") and named after Botten Ada's question ontology. Questions
without a counterpart in Botten Ada (e.g. `does_Andersson_become_pm`) follow
the same naming style and are marked accordingly in
[`data/clean/QUESTIONS.md`](data/clean/QUESTIONS.md), which lists every
question with the exact market wording and URL per source.

## Sources

| Source | Type | What it is |
| --- | --- | --- |
| `botten_ada` | Forecast model | [Botten Ada](https://www.bottenada.se)'s published probabilities (poll-based statistical model) |
| `kambi` | Bookmaker | The Kambi odds network powering **Unibet, Svenska Spel Oddset, ATG and Paf** — these four sites carry identical odds, so they are tracked as one source |
| `betsson` | Bookmaker | Betsson, the only major independently priced bookmaker with Swedish election markets that is scrapable |
| `smarkets` | Betting exchange | Peer-to-peer exchange; prices are set by traders, not a bookmaker |
| `polymarket` | Prediction market | Crypto-based prediction market with substantial volume on Swedish election markets |

Evaluated and rejected: **Bet365** (markets exist but aggressive anti-bot
protection), **Betfair** and **William Hill** (left the Swedish market /
geo-blocked), **Pinnacle**, **bwin**, **Coolbet** (no Swedish election
markets), **Kalshi** (market exists but no liquidity yet — a candidate to add
later).

## Method: from odds to probabilities

Different sources publish prices in different formats. To make them
comparable, everything is converted to an implied probability:

**Bookmakers (Kambi, Betsson) — decimal odds.** A bookmaker's implied
probabilities `1/odds` sum to more than 1 across a market's outcomes; the
excess (the *overround*) is the bookmaker's margin. We remove it by
**proportional normalization** over all outcomes of the market:

```
p_i = (1 / odds_i) / Σ_j (1 / odds_j)
```

This is exact for two-way markets and the standard baseline for multi-outcome
markets. It is known to slightly overstate longshots (the favourite–longshot
bias); Shin's method is a possible future refinement.

**Smarkets — exchange quotes.** Exchange prices carry no overround (the
exchange charges commission on winnings instead). The probability is the
**midpoint of the best back and lay quotes** (the API quotes prices in
probability basis points). If either side of the book is empty, no value is
recorded that day. Contracts are priced independently; no cross-outcome
normalization is applied.

**Polymarket.** Prices *are* probabilities. We use the midpoint of best
bid/ask when both exist, otherwise the published outcome price.

**Botten Ada.** Model probabilities are used as-is.

**Over/under markets.** Bookmakers offer over/under markets on party vote
shares. These map to threshold questions (e.g. `is_L_above_4_pct`, the 4%
parliamentary threshold) **only while the bookmaker's line is exactly 4.0**.
If the line moves, the series stops rather than silently answering a
different question.

## Caveats

- **Non-exhaustive outcome lists.** Bookmaker outright markets may omit
  unlikely outcomes (e.g. only three prime minister candidates are listed).
  Proportional normalization then slightly overstates the listed outcomes.
- **Block duel = block majority.** With 349 seats (an odd number) and only
  the eight current parliament parties winning seats, "more seats than the
  other block" and "own majority" are the same outcome — Botten Ada's model
  assigns them identical probabilities. The market sources are therefore
  shared between the duel questions (`does_rw_get_more_seats_than_lw`) and
  the majority questions (`does_M_L_KD_SD_have_seat_majority`). Market
  resolution rules differ in principle (Polymarket's Tidö market resolves on
  ≥175 seats, the bookmaker duels on most seats) and would diverge only if a
  new party entered parliament.
- **Thin liquidity.** Smarkets' Swedish markets and some Polymarket markets
  have little trading; wide bid/ask spreads make midpoints noisy.
- **Margins differ by market.** Bookmaker margins (and hence the size of the
  vig correction) vary between markets and over time.
- **Betsson coverage gaps.** Betsson's API requires browser-like headers and
  is geo-blocked outside its licensed jurisdictions: GitHub's US-based
  Actions runners get an HTML block page, so the scheduled runs currently
  collect **no Betsson data** (the source fails in isolation; all other
  columns are unaffected). Betsson rows appear only when `run.py` is executed
  from a Swedish/EU IP. Possible future fixes: an EU-hosted runner or proxy.

## Running locally

```bash
pip install -r requirements.txt
python run.py                  # scrape all sources + rebuild clean CSVs
python run.py --source kambi   # one source only (repeatable flag)
python run.py --skip-scrape    # only rebuild clean CSVs from existing raw data
python run.py --skip-clean     # only scrape
python -m pytest               # test suite (uses saved API fixtures, no network)
```

The daily run is scheduled in
[`.github/workflows/scrape.yml`](.github/workflows/scrape.yml) (05:00 UTC,
plus manual `workflow_dispatch`).

## Adding a question or a source

- **New question:** add an entry to
  [`pipeline/mappings.yaml`](pipeline/mappings.yaml) pointing at the raw
  market file(s) and outcome label(s). If the market is already scraped, no
  code change is needed. Use Botten Ada's question ontology naming
  (`botten-ada-data-preparation/PROB_QUESTIONS.md`) when a counterpart
  exists.
- **New source:** add a module under `scrapers/` exposing
  `scrape(raw_dir=None)` (use `scrapers/base.py` helpers), register it in
  `scrapers/__init__.py`, and map its markets in `pipeline/mappings.yaml`.

## License

[MIT](LICENSE). Odds data belongs to the respective sources; this repository
records publicly displayed prices for journalistic and research purposes.
