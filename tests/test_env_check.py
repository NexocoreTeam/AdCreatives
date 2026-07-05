from strategy.env_check import check_env, missing_required


def test_presence_detected(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-something")
    monkeypatch.setenv("EXA_API_KEY", "  ")  # whitespace = absent
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)

    by_name = {s.name: s for s in check_env()}
    assert by_name["ANTHROPIC_API_KEY"].present is True
    assert by_name["EXA_API_KEY"].present is False
    assert by_name["YOUTUBE_API_KEY"].present is False


def test_missing_required_only_flags_required_tier(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-x")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)  # optional

    missing = missing_required(check_env())
    assert missing == ["EXA_API_KEY"]


def test_values_never_exposed():
    for status in check_env():
        assert not hasattr(status, "value")
