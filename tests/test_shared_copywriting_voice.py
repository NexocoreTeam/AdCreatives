
import pytest
from types import SimpleNamespace

from strategy import copywriting_voice


def test_client_context_cannot_replace_global_style(tmp_path, monkeypatch):
    (tmp_path / "library").mkdir()
    (tmp_path / "library/voice.md").write_text("GLOBAL BABYBAY STYLE", encoding="utf-8")
    (tmp_path / "clients/example").mkdir(parents=True)
    (tmp_path / "clients/example/voice.md").write_text("CLIENT AUDIENCE CONTEXT", encoding="utf-8")
    monkeypatch.setattr(copywriting_voice, "ROOT", tmp_path)
    block = copywriting_voice.voice_block("example")
    assert "GLOBAL BABYBAY STYLE" in block
    assert "CLIENT AUDIENCE CONTEXT" in block
    assert "do not replace" in block
    assert "Never invent" in block


def test_missing_global_voice_stops_copy_generation(tmp_path, monkeypatch):
    monkeypatch.setattr(copywriting_voice, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="Shared copywriting voice"):
        copywriting_voice.voice_block()


def test_voice_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert "babybay" in copywriting_voice.voice_block().lower()


def test_client_cannot_escape_workspace():
    with pytest.raises(ValueError, match="client"):
        copywriting_voice.voice_block("../../elsewhere")


def test_static_copy_call_receives_shared_voice(monkeypatch):
    from generators import prompt_engine
    calls = []
    def complete(prompt, system, max_tokens):
        calls.append(system)
        return '{"hero":"A short hook","supporting":"","cta":"See it"}'
    monkeypatch.setattr(prompt_engine, "claude_complete", complete)
    brief = SimpleNamespace(hook="Original hook", cta="Shop now", pain_point="pain", angle="angle", benefit_callouts=[])
    brand = SimpleNamespace(tone="Client tone", prohibited_terms=[])
    result = prompt_engine.condense_brief_for_ad(brief, brand)
    assert result["hero"] == "A short hook"
    assert "SHARED COPYWRITING STYLE" in calls[0]
    assert "Never invent" in calls[0]


def test_missing_shared_style_cannot_silently_fall_back_to_original_copy(tmp_path, monkeypatch):
    from generators import prompt_engine
    monkeypatch.setattr(copywriting_voice, "ROOT", tmp_path)
    brief = SimpleNamespace(hook="Original hook", cta="Shop now", pain_point="pain", angle="angle", benefit_callouts=[])
    brand = SimpleNamespace(tone="Client tone", prohibited_terms=[])
    with pytest.raises(ValueError, match="Shared copywriting voice"):
        prompt_engine.condense_brief_for_ad(brief, brand)
