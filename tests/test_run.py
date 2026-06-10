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
