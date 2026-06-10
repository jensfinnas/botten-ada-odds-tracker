# botten-ada-odds-tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily scraping of Swedish election odds from Kambi, Betsson, Smarkets, Polymarket and Botten Ada into per-market raw JSON files, harmonized into per-question clean CSVs, run by GitHub Actions.

**Architecture:** Dumb scrapers (one module per source) save markets in source-native odds formats to `data/raw/<source>/<slug>.json`, appending one observation per day. A central `pipeline/mappings.yaml` maps (source, market, outcome) → binary question IDs named after the Botten Ada ontology. `pipeline/build_clean.py` rebuilds all `data/clean/<question_id>.csv` from raw on every run (idempotent).

**Tech Stack:** Python (3.10+ compatible, CI runs 3.12), `requests`, `pyyaml`, `pytest`. No browser automation — all sources are plain JSON APIs. Test fixtures are real API responses already saved in `tests/fixtures/`.

**Spec:** `docs/superpowers/specs/2026-06-10-odds-tracker-design.md`

**Verified API facts (from live responses 2026-06-10, fixtures in `tests/fixtures/`):**

- **Kambi** (`eu-offering-api.kambicdn.com/offering/v2018/ub/...`, no auth): odds are millis (`1220` = 1.22), O/U `line` is percent×1000 (`4000` = 4.0%). Swedish election event id `1020265650`, found in `listView/politics.json` by `path[].termKey` ⊇ {sweden, elections}. Outcome English labels: `(s)+(v)+(mp)+(c)`, `Social-Democrats (s)`, `Over`/`Under`, etc. `betOfferType.id == 13` is Head-to-Head.
- **Betsson** (widgets API): requires browser `user-agent` (else AWS WAF 403) + `brandid` + `marketcode` (else 400); full header set recommended for stability. Data at `data.widgets[key=='sportsbook.category.outrights'].data.data.{events,markets,selections}`. Swedish events have `regionName == "Sverige"`. O/U market has `lineValueRaw: 17.5` (float), selection labels `"över 17.5"`/`"under 17.5"`, `odds` is a decimal float.
- **Smarkets** (`api.smarkets.com/v3`, no auth): Sweden node `parent_id=941513` → events `45120073` (Next PM), `45120074` (Most Seats); quotes per contract id with `bids`/`offers` arrays, `price` in probability basis points (`7353` = 73.53%).
- **Polymarket** (`gamma-api.polymarket.com/events?slug=...`, no auth): markets carry `outcomes`/`outcomePrices` as JSON-encoded strings, `bestBid`/`bestAsk` floats (refer to Yes), `active`/`closed` flags. Event slugs: `sweden-parliamentary-election-winner`, `sweden-parliamentary-election-2nd-place`, `sweden-parliamentary-election-3rd-place`, `next-prime-minister-of-sweden`, `will-tido-parties-win-a-majority-in-the-2026-swedish-parliamentary-elections-20260603233725849`.
- **Botten Ada**: `http://ada-site-data.s3.eu-north-1.amazonaws.com/latest_forecast/question--<Q_ID>.json` → `questions.<Q_ID>.now.prob` (0–1), run metadata in `metadata`.

---

### Task 1: Scaffolding

**Files:**
- Create: `requirements.txt`, `.gitignore`, `pytest.ini`, `scrapers/__init__.py` (empty for now), `pipeline/__init__.py`, `tests/__init__.py`, `tests/conftest.py`

- [ ] **Step 1: Create files**

`requirements.txt`:
```
requests>=2.31
pyyaml>=6.0
pytest>=7.0
```

`.gitignore`:
```
__pycache__/
*.pyc
.venv/
.pytest_cache/
```

`pytest.ini`:
```ini
[pytest]
testpaths = tests
```

`tests/conftest.py`:
```python
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def load_fixture():
    def _load(name):
        return json.loads((FIXTURES / name).read_text())
    return _load
```

`scrapers/__init__.py`, `pipeline/__init__.py`, `tests/__init__.py`: empty files.

- [ ] **Step 2: Verify pytest runs**

Run: `python3 -m pytest`
Expected: `no tests ran` (exit code 5 is fine).

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "chore: project scaffolding"
```

---

### Task 2: `scrapers/base.py` — slugify, HTTP session, observation persistence

**Files:**
- Create: `scrapers/base.py`
- Test: `tests/test_base.py`

- [ ] **Step 1: Write failing tests**

`tests/test_base.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_base.py -v`
Expected: FAIL (ModuleNotFoundError / ImportError).

- [ ] **Step 3: Implement `scrapers/base.py`**

```python
"""Shared helpers for all scrapers: slugs, HTTP session, raw-file persistence."""
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
TIMEOUT = 30


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-z0-9]+", "_", text.lower())
    return text.strip("_")


def get_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=2,
                    status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.headers["User-Agent"] = (
        "botten-ada-odds-tracker (+https://github.com/jensfinnas/botten-ada-odds-tracker)"
    )
    return session


def save_observation(source, market, outcomes, raw_dir=None, date=None, fetched_at=None):
    """Append today's observation for one market to data/raw/<source>/<slug>.json.

    `market` must contain: slug, market_name, market_id, url, odds_format.
    Extra keys are stored as metadata. An existing observation with the same
    date is replaced, so reruns within a day don't create duplicates.
    """
    now = datetime.now(timezone.utc)
    date = date or now.strftime("%Y-%m-%d")
    fetched_at = fetched_at or now.strftime("%Y-%m-%dT%H:%M:%SZ")

    raw_dir = Path(raw_dir) if raw_dir else DEFAULT_RAW_DIR
    path = raw_dir / source / (market["slug"] + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        doc = json.loads(path.read_text())
    else:
        doc = {"source": source, "observations": []}
    for key, value in market.items():
        if key != "slug":
            doc[key] = value

    observation = {"date": date, "fetched_at": fetched_at, "outcomes": outcomes}
    doc["observations"] = [o for o in doc["observations"] if o["date"] != date]
    doc["observations"].append(observation)
    doc["observations"].sort(key=lambda o: o["date"])

    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    return path
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_base.py -v` — Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add scrapers/base.py tests/test_base.py && git commit -m "feat: scraper base helpers (slugify, session, raw persistence)"
```

---

### Task 3: `pipeline/harmonize.py` — odds → probabilities

**Files:**
- Create: `pipeline/harmonize.py`
- Test: `tests/test_harmonize.py`

- [ ] **Step 1: Write failing tests**

`tests/test_harmonize.py`:
```python
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
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_harmonize.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/harmonize.py`**

```python
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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_harmonize.py -v` — Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/harmonize.py tests/test_harmonize.py && git commit -m "feat: odds harmonization (vig removal, exchange midpoints)"
```

---

### Task 4: `pipeline/mappings.yaml` + loader/validator

**Files:**
- Create: `pipeline/mappings.yaml`, `pipeline/mappings.py`
- Test: `tests/test_mappings.py`

- [ ] **Step 1: Write `pipeline/mappings.yaml`** (complete file; slugs/labels verified against fixtures)

```yaml
# Maps source markets to binary questions named after the Botten Ada
# question ontology (botten-ada-data-preparation/PROB_QUESTIONS.md).
# Questions with in_ada_ontology: false follow the same naming style but
# do not (yet) exist in Botten Ada.
#
# Per-source fields:
#   market_slug:   filename (without .json) under data/raw/<source>/
#   outcome_label: exact outcome label in the raw observation
#   require_line:  for over/under markets: the question is only defined at
#                  this exact line; if the bookmaker moves the line the
#                  mapping yields no value (by design).
questions:
  - question_id: does_lw_get_more_seats_than_rw
    description: "Skulle S, MP, C och V tillsammans få fler mandat än M, KD, SD och L tillsammans?"
    in_ada_ontology: true
    sources:
      botten_ada: {market_slug: does_lw_get_more_seats_than_rw, outcome_label: "yes"}
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_most_seats
        outcome_label: "(s)+(v)+(mp)+(c)"
      betsson:
        market_slug: nasta_riksdagsval_flest_mandat_h2h
        outcome_label: "S+V+MP+C"

  - question_id: does_rw_get_more_seats_than_lw
    description: "Skulle M, KD, SD och L tillsammans få fler mandat än S, MP, C och V tillsammans?"
    in_ada_ontology: true
    sources:
      botten_ada: {market_slug: does_rw_get_more_seats_than_lw, outcome_label: "yes"}
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_most_seats
        outcome_label: "(m)+(sd)+(kd)+(l)"
      betsson:
        market_slug: nasta_riksdagsval_flest_mandat_h2h
        outcome_label: "M+SD+KD+L"

  - question_id: does_M_L_KD_SD_have_seat_majority
    description: "Får Kristerssons underlag (M, L, KD, SD) en majoritet av mandaten?"
    in_ada_ontology: true
    sources:
      botten_ada: {market_slug: does_M_L_KD_SD_have_seat_majority, outcome_label: "yes"}
      polymarket:
        market_slug: will_tido_parties_win_a_majority_in_the_2026_swedish_parliamentary_elections_20260603233725849
        outcome_label: "Yes"

  - question_id: is_M_larger_than_SD
    description: "Är M större än SD?"
    in_ada_ontology: true
    sources:
      botten_ada: {market_slug: is_M_larger_than_SD, outcome_label: "yes"}
      kambi:
        market_slug: 2026_swedish_general_election_party_to_get_most_votes_moderate_party_m_sweden_democrats_sd
        outcome_label: "Moderate Party (m)"

  - question_id: is_SD_larger_than_M
    description: "Är SD större än M?"
    in_ada_ontology: true
    sources:
      botten_ada: {market_slug: is_SD_larger_than_M, outcome_label: "yes"}
      kambi:
        market_slug: 2026_swedish_general_election_party_to_get_most_votes_moderate_party_m_sweden_democrats_sd
        outcome_label: "Sweden Democrats (sd)"

  - question_id: is_L_above_4_pct
    description: "Ligger L över spärren?"
    in_ada_ontology: true
    sources:
      botten_ada: {market_slug: is_L_above_4_pct, outcome_label: "yes"}
      kambi:
        market_slug: 2026_swedish_general_election_percentage_of_votes_obtained_liberals_l
        outcome_label: "Over"
        require_line: 4.0
      betsson:
        market_slug: riksdagsvalet_2026_procent_av_rosterna_liberalerna_l_over_under
        outcome_label: "Över"
        require_line: 4.0

  # --- Largest party by votes (not in Ada ontology) ---
  - question_id: does_S_get_most_votes
    description: "Blir S största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Social-Democrats (s)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Socialdemokraterna (S)"

  - question_id: does_SD_get_most_votes
    description: "Blir SD största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Sweden Democrats (sd)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Sverigedemokraterna (SD)"

  - question_id: does_M_get_most_votes
    description: "Blir M största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Moderate Party (m)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Moderaterna (M)"

  - question_id: does_V_get_most_votes
    description: "Blir V största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Left Party (v)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Vänsterpartiet (V)"

  - question_id: does_C_get_most_votes
    description: "Blir C största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Centre Party (c)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Centerpartiet (C)"

  - question_id: does_MP_get_most_votes
    description: "Blir MP största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Green Party (mp)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Miljöpartiet (MP)"

  - question_id: does_KD_get_most_votes
    description: "Blir KD största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Christian-Democrats (kd)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Kristdemokraterna (KD)"

  - question_id: does_L_get_most_votes
    description: "Blir L största parti (flest röster)?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_party_coalition_to_obtain_highest_percentage_of_votes
        outcome_label: "Liberals (l)"
      betsson:
        market_slug: nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare
        outcome_label: "Liberalerna (L)"

  # --- Most seats (not in Ada ontology) ---
  - question_id: does_S_get_most_seats
    description: "Får S flest mandat?"
    in_ada_ontology: false
    sources:
      smarkets:
        market_slug: 2026_swedish_general_election_most_seats
        outcome_label: "Social Democrats"
      polymarket:
        market_slug: will_the_swedish_social_democratic_party_s_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  - question_id: does_SD_get_most_seats
    description: "Får SD flest mandat?"
    in_ada_ontology: false
    sources:
      smarkets:
        market_slug: 2026_swedish_general_election_most_seats
        outcome_label: "Sweden Democrats"
      polymarket:
        market_slug: will_the_sweden_democrats_sd_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  - question_id: does_M_get_most_seats
    description: "Får M flest mandat?"
    in_ada_ontology: false
    sources:
      smarkets:
        market_slug: 2026_swedish_general_election_most_seats
        outcome_label: "Moderate"
      polymarket:
        market_slug: will_the_moderate_party_m_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  - question_id: does_V_get_most_seats
    description: "Får V flest mandat?"
    in_ada_ontology: false
    sources:
      polymarket:
        market_slug: will_the_left_party_v_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  - question_id: does_C_get_most_seats
    description: "Får C flest mandat?"
    in_ada_ontology: false
    sources:
      polymarket:
        market_slug: will_the_centre_party_c_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  - question_id: does_MP_get_most_seats
    description: "Får MP flest mandat?"
    in_ada_ontology: false
    sources:
      polymarket:
        market_slug: will_the_green_party_mp_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  - question_id: does_KD_get_most_seats
    description: "Får KD flest mandat?"
    in_ada_ontology: false
    sources:
      polymarket:
        market_slug: will_the_christian_democrats_kd_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  - question_id: does_L_get_most_seats
    description: "Får L flest mandat?"
    in_ada_ontology: false
    sources:
      polymarket:
        market_slug: will_the_liberals_l_win_the_most_seats_in_the_2026_swedish_parliamentary_election
        outcome_label: "Yes"

  # --- Next prime minister (not in Ada ontology) ---
  - question_id: does_Andersson_become_pm
    description: "Blir Magdalena Andersson statsminister efter valet?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_candidate_to_be_appointed_prime_minister_after_the_election
        outcome_label: "Magdalena Andersson"
      betsson:
        market_slug: vem_blir_statsminister_efter_riksdagsvalet_2026_vinnare
        outcome_label: "Magdalena Andersson"
      smarkets:
        market_slug: next_swedish_prime_minister
        outcome_label: "Magdalena Andersson"
      polymarket:
        market_slug: will_magdalena_andersson_be_the_next_prime_minister_of_sweden
        outcome_label: "Yes"

  - question_id: does_Kristersson_become_pm
    description: "Blir Ulf Kristersson statsminister efter valet?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_candidate_to_be_appointed_prime_minister_after_the_election
        outcome_label: "Ulf Kristersson"
      betsson:
        market_slug: vem_blir_statsminister_efter_riksdagsvalet_2026_vinnare
        outcome_label: "Ulf Kristersson"
      smarkets:
        market_slug: next_swedish_prime_minister
        outcome_label: "Ulf Kristersson"
      polymarket:
        market_slug: will_ulf_kristersson_be_the_next_prime_minister_of_sweden
        outcome_label: "Yes"

  - question_id: does_Akesson_become_pm
    description: "Blir Jimmie Åkesson statsminister efter valet?"
    in_ada_ontology: false
    sources:
      kambi:
        market_slug: 2026_swedish_general_election_candidate_to_be_appointed_prime_minister_after_the_election
        outcome_label: "Jimmie Åkesson"
      betsson:
        market_slug: vem_blir_statsminister_efter_riksdagsvalet_2026_vinnare
        outcome_label: "Jimmie Åkesson"
      polymarket:
        market_slug: will_jimmie_kesson_be_the_next_prime_minister_of_sweden
        outcome_label: "Yes"
```

- [ ] **Step 2: Write failing tests**

`tests/test_mappings.py`:
```python
from pipeline.mappings import KNOWN_SOURCES, load_mappings


def test_load_and_validate():
    questions = load_mappings()
    assert len(questions) >= 20
    ids = [q["question_id"] for q in questions]
    assert len(ids) == len(set(ids)), "duplicate question_id"
    for q in questions:
        assert isinstance(q["in_ada_ontology"], bool)
        assert q["description"]
        assert q["sources"], q["question_id"]
        for source, cfg in q["sources"].items():
            assert source in KNOWN_SOURCES, source
            assert cfg["market_slug"]
            assert cfg["outcome_label"]
            if "require_line" in cfg:
                assert isinstance(cfg["require_line"], float)


def test_ada_questions_have_ada_source():
    for q in load_mappings():
        if q["in_ada_ontology"]:
            assert "botten_ada" in q["sources"], q["question_id"]
```

- [ ] **Step 3: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_mappings.py -v` — Expected: ImportError.

- [ ] **Step 4: Implement `pipeline/mappings.py`**

```python
"""Load and validate the market -> question mapping."""
from pathlib import Path

import yaml

KNOWN_SOURCES = {"botten_ada", "kambi", "betsson", "smarkets", "polymarket"}
MAPPINGS_PATH = Path(__file__).resolve().parent / "mappings.yaml"


def load_mappings(path=None):
    data = yaml.safe_load(Path(path or MAPPINGS_PATH).read_text())
    questions = data["questions"]
    seen = set()
    for q in questions:
        qid = q["question_id"]
        if qid in seen:
            raise ValueError("duplicate question_id: %s" % qid)
        seen.add(qid)
        q.setdefault("in_ada_ontology", False)
        for source, cfg in q["sources"].items():
            if source not in KNOWN_SOURCES:
                raise ValueError("%s: unknown source %s" % (qid, source))
            for field in ("market_slug", "outcome_label"):
                if not cfg.get(field):
                    raise ValueError("%s/%s: missing %s" % (qid, source, field))
            if "require_line" in cfg:
                cfg["require_line"] = float(cfg["require_line"])
    return questions
```

- [ ] **Step 5: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_mappings.py -v` — Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add pipeline/mappings.yaml pipeline/mappings.py tests/test_mappings.py && git commit -m "feat: market-to-question mappings with validation"
```

---

### Task 5: `scrapers/kambi.py`

**Files:**
- Create: `scrapers/kambi.py`
- Test: `tests/test_kambi.py` (fixtures: `kambi_listview_politics.json`, `kambi_event_1020265650.json`)

- [ ] **Step 1: Write failing tests**

`tests/test_kambi.py`:
```python
from scrapers.kambi import find_election_event_ids, parse_event


def test_find_election_event_ids(load_fixture):
    ids = find_election_event_ids(load_fixture("kambi_listview_politics.json"))
    assert ids == [1020265650]


def test_parse_event(load_fixture):
    # parse_event yields (market, outcomes) tuples
    parsed = list(parse_event(load_fixture("kambi_event_1020265650.json")))
    slugs = {m["slug"] for m, _ in parsed}
    assert "2026_swedish_general_election_party_coalition_to_obtain_most_seats" in slugs
    assert "2026_swedish_general_election_percentage_of_votes_obtained_liberals_l" in slugs
    assert ("2026_swedish_general_election_party_to_get_most_votes_"
            "moderate_party_m_sweden_democrats_sd") in slugs

    seats = next((m, o) for m, o in parsed
                 if m["slug"].endswith("party_coalition_to_obtain_most_seats"))
    market, outcomes = seats
    assert market["odds_format"] == "decimal"
    assert market["market_name_english"] == "Party/Coalition to obtain most seats"
    odds = {o["label"]: o["odds"] for o in outcomes}
    assert odds["(s)+(v)+(mp)+(c)"] == 1.22
    assert odds["(m)+(sd)+(kd)+(l)"] == 3.75

    ou_l = next(o for m, o in parsed
                if m["slug"].endswith("percentage_of_votes_obtained_liberals_l"))
    over = next(x for x in ou_l if x["label"] == "Over")
    assert over["line"] == 4.0
    assert over["odds"] == 2.3
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_kambi.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement `scrapers/kambi.py`**

```python
"""Kambi powers Unibet, Svenska Spel Oddset, ATG and Paf with identical odds.

Open CDN API, no auth. Odds are millis (1220 = 1.22); over/under lines are
percent * 1000 (4000 = 4.0%). The election event id may change if Kambi
recreates the event, so it is re-discovered from the politics listing on
every run.
"""
from .base import get_session, save_observation, slugify, TIMEOUT

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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_kambi.py -v` — Expected: 2 passed.

- [ ] **Step 5: Smoke-test live scrape into a temp dir**

Run: `python3 -c "from scrapers.kambi import scrape; print(*scrape(raw_dir='/tmp/odds_raw'), sep='\n')"`
Expected: ~12 file paths under `/tmp/odds_raw/kambi/`. Inspect one file.

- [ ] **Step 6: Commit**

```bash
git add scrapers/kambi.py tests/test_kambi.py && git commit -m "feat: kambi scraper (unibet/svenska spel/atg/paf feed)"
```

---

### Task 6: `scrapers/betsson.py`

**Files:**
- Create: `scrapers/betsson.py`
- Test: `tests/test_betsson.py` (fixture: `betsson_politics.json`)

- [ ] **Step 1: Write failing tests**

`tests/test_betsson.py`:
```python
from scrapers.betsson import parse_widgets


def test_parse_widgets_swedish_markets(load_fixture):
    parsed = list(parse_widgets(load_fixture("betsson_politics.json")))
    slugs = {m["slug"] for m, _ in parsed}
    assert "nasta_riksdagsval_flest_mandat_h2h" in slugs
    assert "nasta_riksdagsval_i_sverige_parti_med_flest_roster_vinnare" in slugs
    assert "riksdagsvalet_2026_procent_av_rosterna_liberalerna_l_over_under" in slugs
    assert "vem_blir_statsminister_efter_riksdagsvalet_2026_vinnare" in slugs
    # only Swedish region markets
    assert all(m["odds_format"] == "decimal" for m, _ in parsed)

    duel = next(o for m, o in parsed if m["slug"] == "nasta_riksdagsval_flest_mandat_h2h")
    odds = {x["label"]: x["odds"] for x in duel}
    assert odds["S+V+MP+C"] == 1.16
    assert odds["M+SD+KD+L"] == 4.3

    ou_l = next(o for m, o in parsed
                if m["slug"] == "riksdagsvalet_2026_procent_av_rosterna_liberalerna_l_over_under")
    over = next(x for x in ou_l if x["label"] == "Över")
    assert over["line"] == 4.0
    assert over["odds"] == 2.45
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_betsson.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement `scrapers/betsson.py`**

```python
"""Betsson sportsbook widget API.

No login needed, but AWS WAF blocks non-browser user agents (403) and the
API requires brandid + marketcode headers (400 without). The remaining
context headers make responses stable. Content is jurisdiction-filtered;
if runs from non-EU datacenter IPs stop returning Swedish markets, this
source fails in isolation and the clean CSV column goes empty.
"""
from .base import get_session, save_observation, slugify, TIMEOUT

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
    paths = []
    for market, outcomes in parse_widgets(response.json()):
        paths.append(save_observation(SOURCE, market, outcomes, raw_dir=raw_dir))
    return paths
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_betsson.py -v` — Expected: 1 passed.

- [ ] **Step 5: Smoke-test live scrape**

Run: `python3 -c "from scrapers.betsson import scrape; print(*scrape(raw_dir='/tmp/odds_raw'), sep='\n')"`
Expected: ~11 file paths under `/tmp/odds_raw/betsson/`.

- [ ] **Step 6: Commit**

```bash
git add scrapers/betsson.py tests/test_betsson.py && git commit -m "feat: betsson scraper"
```

---

### Task 7: `scrapers/smarkets.py`

**Files:**
- Create: `scrapers/smarkets.py`
- Test: `tests/test_smarkets.py` (fixtures: `smarkets_events.json`, `smarkets_markets.json`, `smarkets_contracts.json`, `smarkets_quotes.json`)

- [ ] **Step 1: Write failing tests**

`tests/test_smarkets.py`:
```python
from scrapers.smarkets import parse_markets


def test_parse_markets(load_fixture):
    parsed = list(parse_markets(load_fixture("smarkets_events.json")["events"],
                                load_fixture("smarkets_markets.json")["markets"],
                                load_fixture("smarkets_contracts.json")["contracts"],
                                load_fixture("smarkets_quotes.json")))
    slugs = {m["slug"] for m, _ in parsed}
    assert slugs == {"next_swedish_prime_minister",
                     "2026_swedish_general_election_most_seats"}

    pm = next(o for m, o in parsed if m["slug"] == "next_swedish_prime_minister")
    andersson = next(x for x in pm if x["label"] == "Magdalena Andersson")
    assert andersson["best_bid"] == 7353
    assert andersson["best_offer"] == 7937

    meta = next(m for m, _ in parsed if m["slug"] == "next_swedish_prime_minister")
    assert meta["odds_format"] == "smarkets_quotes"
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_smarkets.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement `scrapers/smarkets.py`**

```python
"""Smarkets betting exchange. Official public REST API, no auth.

Quote prices are probability basis points (7353 = 73.53%). Raw files store
best bid/offer per contract; the midpoint becomes the probability at
harmonization time.
"""
from .base import get_session, save_observation, slugify, TIMEOUT

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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_smarkets.py -v` — Expected: 1 passed.

Note: if the test fails because event ids in `smarkets_quotes.json` don't match (the quotes fixture was fetched per market), check that quote keys are contract ids as strings — the code uses `str(contract["id"])`.

- [ ] **Step 5: Smoke-test live scrape**

Run: `python3 -c "from scrapers.smarkets import scrape; print(*scrape(raw_dir='/tmp/odds_raw'), sep='\n')"`
Expected: 2 file paths.

- [ ] **Step 6: Commit**

```bash
git add scrapers/smarkets.py tests/test_smarkets.py && git commit -m "feat: smarkets scraper"
```

---

### Task 8: `scrapers/polymarket.py`

**Files:**
- Create: `scrapers/polymarket.py`
- Test: `tests/test_polymarket.py` (fixtures: `polymarket_event_winner.json`, `polymarket_event_tido.json`)

- [ ] **Step 1: Write failing tests**

`tests/test_polymarket.py`:
```python
from scrapers.polymarket import parse_event


def test_parse_winner_event(load_fixture):
    parsed = list(parse_event(load_fixture("polymarket_event_winner.json")[0]))
    # 9 active party markets; 27 inactive placeholders must be filtered out
    assert len(parsed) == 9
    s_market = next(
        (m, o) for m, o in parsed
        if m["slug"].startswith("will_the_swedish_social_democratic_party"))
    market, outcomes = s_market
    assert market["odds_format"] == "probability"
    assert market["market_name"].startswith("Will the Swedish Social Democratic Party")
    yes = next(x for x in outcomes if x["label"] == "Yes")
    assert yes["price"] == 0.905
    assert yes["best_bid"] == 0.9
    assert yes["best_ask"] == 0.91
    no = next(x for x in outcomes if x["label"] == "No")
    assert no["price"] == 0.095


def test_parse_tido_event(load_fixture):
    parsed = list(parse_event(load_fixture("polymarket_event_tido.json")[0]))
    assert len(parsed) == 1
    market, outcomes = parsed[0]
    assert market["market_name"] == (
        "Will Tidö parties win a majority in the 2026 Swedish parliamentary elections?")
    yes = next(x for x in outcomes if x["label"] == "Yes")
    assert yes["price"] == 0.28
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_polymarket.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement `scrapers/polymarket.py`**

```python
"""Polymarket prediction market via the public gamma API, no auth.

Prices ARE probabilities (0-1). `outcomes` and `outcomePrices` are
JSON-encoded strings; bestBid/bestAsk refer to the Yes outcome.
Tracked events are listed explicitly — add new slugs as Polymarket
creates more Swedish election markets.
"""
import json

from .base import get_session, save_observation, slugify, TIMEOUT

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
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_polymarket.py -v` — Expected: 2 passed.
(If `event["title"]` raises KeyError, check the fixture for the title field name and adjust.)

- [ ] **Step 5: Smoke-test live scrape**

Run: `python3 -c "from scrapers.polymarket import scrape; print(len(scrape(raw_dir='/tmp/odds_raw')))"`
Expected: ~30+ files (9 winner + 9+9 2nd/3rd + ~10 PM + 1 Tidö).

- [ ] **Step 6: Commit**

```bash
git add scrapers/polymarket.py tests/test_polymarket.py && git commit -m "feat: polymarket scraper"
```

---

### Task 9: `scrapers/botten_ada.py`

**Files:**
- Create: `scrapers/botten_ada.py`
- Test: `tests/test_botten_ada.py` (fixture: `botten_ada_is_L_above_4_pct.json`)

- [ ] **Step 1: Write failing tests**

`tests/test_botten_ada.py`:
```python
from pipeline.mappings import load_mappings
from scrapers.botten_ada import mapped_question_ids, parse_question


def test_mapped_question_ids():
    ids = mapped_question_ids()
    assert "is_L_above_4_pct" in ids
    assert "does_lw_get_more_seats_than_rw" in ids
    # non-ada questions must not be fetched
    assert "does_S_get_most_votes" not in ids


def test_parse_question(load_fixture):
    market, outcomes = parse_question(
        "is_L_above_4_pct", load_fixture("botten_ada_is_L_above_4_pct.json"))
    assert market["slug"] == "is_L_above_4_pct"
    assert market["odds_format"] == "probability"
    assert "model_run" in market
    assert outcomes[0]["label"] == "yes"
    assert 0.0 <= outcomes[0]["probability"] <= 1.0
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_botten_ada.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement `scrapers/botten_ada.py`**

```python
"""Botten Ada's published forecast probabilities (no scraping involved -
plain JSON files on S3). Fetches only the questions present in
pipeline/mappings.yaml."""
from pipeline.mappings import load_mappings

from .base import get_session, save_observation, TIMEOUT

SOURCE = "botten_ada"
BASE = "http://ada-site-data.s3.eu-north-1.amazonaws.com/latest_forecast"


def mapped_question_ids():
    ids = []
    for question in load_mappings():
        config = question["sources"].get("botten_ada")
        if config:
            ids.append(config["market_slug"])
    return ids


def parse_question(question_id, payload):
    probability = payload["questions"][question_id]["now"]["prob"]
    market = {
        "slug": question_id,
        "market_name": question_id,
        "market_id": question_id,
        "url": "%s/question--%s.json" % (BASE, question_id),
        "odds_format": "probability",
        "model_run": payload["metadata"].get("run"),
    }
    return market, [{"label": "yes", "probability": probability}]


def scrape(raw_dir=None):
    session = get_session()
    paths = []
    for question_id in mapped_question_ids():
        payload = session.get("%s/question--%s.json" % (BASE, question_id),
                              timeout=TIMEOUT).json()
        market, outcomes = parse_question(question_id, payload)
        paths.append(save_observation(SOURCE, market, outcomes, raw_dir=raw_dir))
    return paths
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_botten_ada.py -v` — Expected: 2 passed.

- [ ] **Step 5: Smoke-test live scrape**

Run: `python3 -c "from scrapers.botten_ada import scrape; print(len(scrape(raw_dir='/tmp/odds_raw')))"`
Expected: 6 files (the six in_ada_ontology questions).

- [ ] **Step 6: Commit**

```bash
git add scrapers/botten_ada.py tests/test_botten_ada.py && git commit -m "feat: botten ada fetcher"
```

---

### Task 10: `pipeline/build_clean.py` — clean CSVs + QUESTIONS.md

**Files:**
- Create: `pipeline/build_clean.py`
- Test: `tests/test_build_clean.py`

- [ ] **Step 1: Write failing tests**

`tests/test_build_clean.py`:
```python
import json

from pipeline.build_clean import build_clean


def _write_raw(tmp_path, source, slug, doc):
    path = tmp_path / "raw" / source / (slug + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))


MAPPINGS = [{
    "question_id": "is_L_above_4_pct",
    "description": "Ligger L över spärren?",
    "in_ada_ontology": True,
    "sources": {
        "botten_ada": {"market_slug": "is_L_above_4_pct", "outcome_label": "yes"},
        "kambi": {"market_slug": "ou_l", "outcome_label": "Over", "require_line": 4.0},
    },
}]


def test_build_clean(tmp_path):
    _write_raw(tmp_path, "botten_ada", "is_L_above_4_pct", {
        "source": "botten_ada", "market_name": "is_L_above_4_pct",
        "url": "http://example.com", "odds_format": "probability",
        "observations": [
            {"date": "2026-06-10", "outcomes": [{"label": "yes", "probability": 0.62}]},
            {"date": "2026-06-11", "outcomes": [{"label": "yes", "probability": 0.65}]},
        ]})
    _write_raw(tmp_path, "kambi", "ou_l", {
        "source": "kambi", "market_name": "Percentage of votes - L",
        "url": "http://example.com", "odds_format": "decimal",
        "observations": [
            {"date": "2026-06-10", "outcomes": [
                {"label": "Over", "odds": 2.3, "line": 4.0},
                {"label": "Under", "odds": 1.55, "line": 4.0}]},
            # day 2: line moved -> kambi cell must be empty
            {"date": "2026-06-11", "outcomes": [
                {"label": "Over", "odds": 1.9, "line": 4.5},
                {"label": "Under", "odds": 1.8, "line": 4.5}]},
        ]})

    build_clean(raw_dir=tmp_path / "raw", clean_dir=tmp_path / "clean",
                mappings=MAPPINGS)

    csv_text = (tmp_path / "clean" / "is_L_above_4_pct.csv").read_text()
    lines = csv_text.strip().split("\n")
    assert lines[0] == "date,botten_ada,kambi"
    assert lines[1] == "2026-06-10,0.62,0.4026"
    assert lines[2] == "2026-06-11,0.65,"

    questions_md = (tmp_path / "clean" / "QUESTIONS.md").read_text()
    assert "is_L_above_4_pct" in questions_md
    assert "Ligger L över spärren?" in questions_md


def test_build_clean_missing_raw_file_is_skipped(tmp_path, capsys):
    build_clean(raw_dir=tmp_path / "raw", clean_dir=tmp_path / "clean",
                mappings=MAPPINGS)
    # no raw data at all -> no csv rows, but no crash
    csv_text = (tmp_path / "clean" / "is_L_above_4_pct.csv").read_text()
    assert csv_text.strip() == "date,botten_ada,kambi"
```

Expected kambi value on 2026-06-10: (1/2.3) / (1/2.3 + 1/1.55) = 0.402597… → rounded to 4 decimals = `0.4026`.

- [ ] **Step 2: Run tests, verify they fail**

Run: `python3 -m pytest tests/test_build_clean.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement `pipeline/build_clean.py`**

```python
"""Rebuild data/clean/*.csv and QUESTIONS.md from raw observations.

Rebuilt from scratch on every run: if the harmonization method or the
mappings change, history is recomputed consistently.
"""
import csv
import json
import sys
from pathlib import Path

from .harmonize import prob_from_observation
from .mappings import load_mappings

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RAW_DIR = REPO_ROOT / "data" / "raw"
DEFAULT_CLEAN_DIR = REPO_ROOT / "data" / "clean"


def _source_columns(sources):
    return sorted(sources, key=lambda s: (s != "botten_ada", s))


def _load_raw(raw_dir, source, market_slug):
    path = raw_dir / source / (market_slug + ".json")
    if not path.exists():
        print("warning: missing raw file %s" % path, file=sys.stderr)
        return None
    return json.loads(path.read_text())


def build_clean(raw_dir=None, clean_dir=None, mappings=None):
    raw_dir = Path(raw_dir) if raw_dir else DEFAULT_RAW_DIR
    clean_dir = Path(clean_dir) if clean_dir else DEFAULT_CLEAN_DIR
    clean_dir.mkdir(parents=True, exist_ok=True)
    questions = mappings if mappings is not None else load_mappings()

    doc_index = {}  # (source, slug) -> raw doc, for QUESTIONS.md
    for question in questions:
        columns = _source_columns(question["sources"])
        rows = {}  # date -> {source: prob}
        for source, config in question["sources"].items():
            doc = _load_raw(raw_dir, source, config["market_slug"])
            if doc is None:
                continue
            doc_index[(source, config["market_slug"])] = doc
            for observation in doc["observations"]:
                prob = prob_from_observation(
                    doc["odds_format"], observation, config["outcome_label"],
                    require_line=config.get("require_line"))
                if prob is None:
                    continue
                rows.setdefault(observation["date"], {})[source] = round(prob, 4)

        out_path = clean_dir / (question["question_id"] + ".csv")
        with out_path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date"] + columns)
            for date in sorted(rows):
                writer.writerow([date] + [rows[date].get(c, "") for c in columns])

    _write_questions_md(clean_dir, questions, doc_index)


def _write_questions_md(clean_dir, questions, doc_index):
    lines = ["# Questions", "",
             "Auto-generated from `pipeline/mappings.yaml` and raw metadata. "
             "Do not edit by hand.", ""]
    for question in questions:
        lines.append("## `%s`" % question["question_id"])
        lines.append("")
        lines.append(question["description"])
        lines.append("")
        lines.append("In Botten Ada ontology: %s"
                     % ("yes" if question["in_ada_ontology"] else "no"))
        lines.append("")
        lines.append("| Source | Market | Outcome | URL |")
        lines.append("| --- | --- | --- | --- |")
        for source in _source_columns(question["sources"]):
            config = question["sources"][source]
            doc = doc_index.get((source, config["market_slug"])) or {}
            label = config["outcome_label"]
            if config.get("require_line") is not None:
                label += " (line %s)" % config["require_line"]
            lines.append("| %s | %s | %s | %s |" % (
                source, doc.get("market_name", config["market_slug"]),
                label, doc.get("url", "")))
        lines.append("")
    (clean_dir / "QUESTIONS.md").write_text("\n".join(lines))
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest tests/test_build_clean.py -v` — Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add pipeline/build_clean.py tests/test_build_clean.py && git commit -m "feat: clean csv builder with QUESTIONS.md generation"
```

---

### Task 11: `run.py` CLI + scraper registry

**Files:**
- Modify: `scrapers/__init__.py`
- Create: `run.py`
- Test: `tests/test_run.py`

- [ ] **Step 1: Write failing test**

`tests/test_run.py`:
```python
import run
from scrapers import SCRAPERS


def test_registry_complete():
    assert set(SCRAPERS) == {"botten_ada", "kambi", "betsson", "smarkets", "polymarket"}


def test_run_isolates_scraper_failures(monkeypatch, tmp_path, capsys):
    calls = []

    def ok(raw_dir=None):
        calls.append("ok")
        return [tmp_path / "x.json"]

    def boom(raw_dir=None):
        raise RuntimeError("api down")

    monkeypatch.setattr(run, "SCRAPERS", {"good": ok, "bad": boom})
    monkeypatch.setattr(run, "build_clean", lambda: calls.append("clean"))
    exit_code = run.main([])
    assert exit_code == 0  # at least one source succeeded
    assert calls == ["ok", "clean"]
    assert "bad" in capsys.readouterr().err


def test_run_fails_when_all_sources_fail(monkeypatch):
    def boom(raw_dir=None):
        raise RuntimeError("api down")

    monkeypatch.setattr(run, "SCRAPERS", {"bad": boom})
    monkeypatch.setattr(run, "build_clean", lambda: None)
    assert run.main([]) == 1
```

- [ ] **Step 2: Run test, verify it fails**

Run: `python3 -m pytest tests/test_run.py -v` — Expected: ImportError.

- [ ] **Step 3: Implement**

`scrapers/__init__.py`:
```python
from . import betsson, botten_ada, kambi, polymarket, smarkets

SCRAPERS = {
    "botten_ada": botten_ada.scrape,
    "kambi": kambi.scrape,
    "betsson": betsson.scrape,
    "smarkets": smarkets.scrape,
    "polymarket": polymarket.scrape,
}
```

`run.py`:
```python
#!/usr/bin/env python3
"""Daily entry point: scrape all sources, then rebuild clean CSVs.

Each scraper fails in isolation; the run succeeds (exit 0) if at least one
source delivered data."""
import argparse
import sys
import traceback

from pipeline.build_clean import build_clean
from scrapers import SCRAPERS


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", action="append",
                        help="scrape only this source (repeatable)")
    parser.add_argument("--skip-scrape", action="store_true")
    parser.add_argument("--skip-clean", action="store_true")
    args = parser.parse_args(argv)

    succeeded, failed = [], []
    if not args.skip_scrape:
        for name in (args.source or sorted(SCRAPERS)):
            try:
                paths = SCRAPERS[name]()
                print("[%s] OK - %d markets" % (name, len(paths)))
                succeeded.append(name)
            except Exception:
                print("[%s] FAILED" % name, file=sys.stderr)
                traceback.print_exc()
                failed.append(name)

    if not args.skip_clean:
        build_clean()
        print("[clean] rebuilt CSVs")

    if failed:
        print("failed sources: %s" % ", ".join(failed), file=sys.stderr)
    if not args.skip_scrape and not succeeded:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, verify they pass**

Run: `python3 -m pytest -v` — Expected: ALL tests pass (whole suite).

- [ ] **Step 5: Commit**

```bash
git add run.py scrapers/__init__.py tests/test_run.py && git commit -m "feat: run.py CLI with per-source failure isolation"
```

---

### Task 12: GitHub Actions workflow, README, LICENSE

**Files:**
- Create: `.github/workflows/scrape.yml`, `README.md`, `LICENSE`

- [ ] **Step 1: Write `.github/workflows/scrape.yml`**

```yaml
name: Daily odds scrape

on:
  schedule:
    - cron: "0 5 * * *"   # 05:00 UTC daily
  workflow_dispatch:

permissions:
  contents: write

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -r requirements.txt
      - run: python -m pytest
      - run: python run.py
      - name: Commit and push if data changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add data
          if git diff --cached --quiet; then
            echo "No changes."
          else
            git commit -m "Daily odds update $(date -u +%F)"
            git push
          fi
```

- [ ] **Step 2: Write `LICENSE`** — standard MIT license text, copyright `2026 Newsworthy / Jens Finnäs`.

- [ ] **Step 3: Write `README.md`** (English). Must cover, in this order:

1. **What this is** — daily tracking of betting odds and prediction-market prices for the 2026 Swedish parliamentary election (Sept 13), harmonized into probabilities and compared with [Botten Ada](https://www.bottenada.se)'s model forecasts. Data updated daily by GitHub Actions, committed to this repo.
2. **Data layout** — `data/raw/<source>/<market>.json` (odds as published, one observation appended per day, market metadata included) and `data/clean/<question_id>.csv` (`date,botten_ada,betsson,kambi,polymarket,smarkets` with probabilities 0–1, empty cell = no data that day). Questions are binary and named after Botten Ada's question ontology; `data/clean/QUESTIONS.md` lists every question with exact source market wordings. Questions without an Ada counterpart are marked as such.
3. **Sources** — table: Botten Ada (model), Kambi (odds feed powering Unibet, Svenska Spel Oddset, ATG and Paf — identical odds, hence ONE source), Betsson (independent bookmaker), Smarkets (betting exchange), Polymarket (prediction market). Note which other sites were evaluated and rejected (Bet365: anti-bot; Betfair/William Hill: left the Swedish market; Pinnacle/bwin/Coolbet: no markets).
4. **Method: from odds to probabilities** — with the formulas:
   - Bookmakers quote decimal odds including a margin (overround): implied probabilities `1/odds` sum to >1. We remove the margin by proportional normalization: `p_i = (1/o_i) / Σ_j (1/o_j)`. Exact for two-way markets; for multi-outcome markets this is the standard baseline method (known favourite–longshot bias; Shin's method is a possible refinement).
   - Smarkets: midpoint of best back/lay quote (prices are probability basis points). No overround to remove; commission is charged on winnings, not embedded in prices.
   - Polymarket: prices are probabilities; midpoint of best bid/ask.
   - Over/under markets map to threshold questions (e.g. `is_L_above_4_pct`) **only** when the bookmaker's line is exactly 4.0 — if the line moves, the series stops rather than silently changing question.
5. **Caveats** — bookmaker outcome lists may not be exhaustive (e.g. PM market lists only 3 candidates), so normalized probabilities are slight overestimates; two-way seat-duel markets ignore the (tiny) probability of an exact tie, while Botten Ada's mirror questions treat it separately; thin liquidity on Smarkets/some Polymarket markets; Betsson responses are jurisdiction-filtered and may break from non-EU runner IPs.
6. **Running locally** — `pip install -r requirements.txt`, `python run.py` (flags: `--source`, `--skip-scrape`, `--skip-clean`), `python -m pytest`.
7. **Adding a question or source** — a question = one entry in `pipeline/mappings.yaml`; a source = a module in `scrapers/` exposing `scrape(raw_dir=None)` plus registry entry.

- [ ] **Step 4: Update spec note on Smarkets** — in `docs/superpowers/specs/2026-06-10-odds-tracker-design.md`, replace the sentence "Normalisering över utfallen om summan ändå avviker från 1." with "Ingen normalisering över utfallen — varje kontrakt prissätts oberoende på börsen och tunna böcker skulle förvrängas av normalisering." (decision made during implementation planning).

- [ ] **Step 5: Commit**

```bash
git add .github README.md LICENSE docs && git commit -m "feat: daily github actions workflow, readme, license"
```

---

### Task 13: End-to-end live run + first data commit

- [ ] **Step 1: Full live run**

Run: `python3 run.py`
Expected: all five sources print `OK`, `[clean] rebuilt CSVs`, exit 0.

- [ ] **Step 2: Inspect results**

```bash
ls data/raw/*/ | head -30
column -s, -t data/clean/is_L_above_4_pct.csv
column -s, -t data/clean/does_lw_get_more_seats_than_rw.csv
head -40 data/clean/QUESTIONS.md
```

Sanity checks:
- `does_lw_get_more_seats_than_rw`: botten_ada ≈ 0.97 region, kambi ≈ 0.75, betsson ≈ 0.79 — plausible spread.
- `is_L_above_4_pct`: kambi ≈ 0.40, betsson ≈ 0.38.
- `does_M_L_KD_SD_have_seat_majority`: polymarket ≈ 0.28.
- Every mapped raw file exists (no `warning: missing raw file` lines except possibly none).

If a mapping warning appears, fix the slug/label in `mappings.yaml` against the actual raw filename — do NOT change scraper slug logic to fit the mapping.

- [ ] **Step 3: Idempotency check**

Run `python3 run.py` a second time; `git status` should show the same files with only `fetched_at` timestamps changed (same date replaced, no duplicate observations).

- [ ] **Step 4: Run full test suite**

Run: `python3 -m pytest -v` — Expected: all pass.

- [ ] **Step 5: Commit data**

```bash
git add data && git commit -m "data: first scrape 2026-06-10"
```

---

### Task 14: Publish (requires user)

- [ ] Create public GitHub repo (e.g. `botten-ada-odds-tracker`), push `main`.
- [ ] Trigger `workflow_dispatch` run; verify all sources succeed from the Actions runner — **especially Betsson** (jurisdiction risk from datacenter IPs).
- [ ] If Betsson fails from the runner: keep the source, note the limitation in README, evaluate alternatives later.
- [ ] Check that the workflow's commit shows up and clean CSVs gained the day's row.
