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
