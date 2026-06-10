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
