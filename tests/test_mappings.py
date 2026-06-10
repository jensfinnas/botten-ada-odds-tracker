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
