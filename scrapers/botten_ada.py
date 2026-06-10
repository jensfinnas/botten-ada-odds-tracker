"""Botten Ada's published forecast probabilities (no scraping involved -
plain JSON files on S3). Fetches only the questions present in
pipeline/mappings.yaml. Questions mapped before Ada's pipeline has
published them are skipped with a warning instead of failing the source."""
import sys

from pipeline.mappings import load_mappings

from .base import TIMEOUT, get_session, save_observation

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
        response = session.get("%s/question--%s.json" % (BASE, question_id),
                               timeout=TIMEOUT)
        if response.status_code != 200:
            print("warning: question %s not published yet (HTTP %s) - skipping"
                  % (question_id, response.status_code), file=sys.stderr)
            continue
        market, outcomes = parse_question(question_id, response.json())
        paths.append(save_observation(SOURCE, market, outcomes, raw_dir=raw_dir))
    return paths
