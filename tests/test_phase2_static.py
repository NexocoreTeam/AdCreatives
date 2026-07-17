import pytest

from strategy.phase2_static import create_static_phase2_workbook


def test_create_static_phase2_workbook_writes_required_gates(tmp_path):
    clients = tmp_path / "clients"
    client_dir = clients / "secondkind-v2"
    client_dir.mkdir(parents=True)

    result = create_static_phase2_workbook(
        "secondkind-v2",
        product="gut-balance",
        focus_avatar="Done-Everything-Right Dana",
        mass_desire="finally feel consistent again",
        clients_dir=clients,
    )

    text = result.path.read_text(encoding="utf-8")
    assert result.path.name == "phase-2-static-briefing-workbook.md"
    assert "Gate 1: Audience Research Synthesis" in text
    assert "Gate 2: Avatar Selection" in text
    assert "Gate 3: Mass Desire Selection" in text
    assert "10 Competitor Ideas" in text
    assert "10 Adjacent Niche Ideas" in text
    assert "Angle Bank By Awareness Level" in text
    assert "Visual Format / Template Selection" in text
    assert "Foreplay Library Emulation And Ad Cards" in text
    assert "Post-Emulation Ad Card Template" in text
    assert "Template-Specific Copy Set" in text
    assert "Done-Everything-Right Dana" in text
    assert "finally feel consistent again" in text
    assert "We are using this phrase because customers said" in text
    assert "Verbatim-First Quote Bank" in text
    assert "Raw quote / exact phrase" in text
    assert "Ad-ready wording" in text


def test_create_static_phase2_workbook_refuses_overwrite_without_force(tmp_path):
    clients = tmp_path / "clients"
    client_dir = clients / "acme"
    client_dir.mkdir(parents=True)

    create_static_phase2_workbook("acme", clients_dir=clients)

    with pytest.raises(FileExistsError):
        create_static_phase2_workbook("acme", clients_dir=clients)

    result = create_static_phase2_workbook("acme", clients_dir=clients, force=True)
    assert result.path.exists()
