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
