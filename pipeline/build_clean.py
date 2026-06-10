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
