"""Tests for the protocol library and protocol context builder.

Covers:
  - System protocol library (loading, lookup, approach filtering)
  - merge_protocols (combining system + custom dicts)
  - build_protocol_context_for_patient (priority rules, output structure)
"""

import pytest
from app.core.protocols import (
    Protocol,
    get_system_protocols,
    get_protocol_by_id,
    get_protocols_for_approach,
    merge_protocols,
)
from app.core.protocol_context import build_protocol_context_for_patient


# ---------------------------------------------------------------------------
# System protocol library tests
# ---------------------------------------------------------------------------


def test_system_protocols_not_empty():
    protocols = get_system_protocols()
    assert len(protocols) > 0, "System protocol list must not be empty"


def test_all_system_protocols_are_valid():
    for p in get_system_protocols():
        assert p.id, f"Protocol missing ID: {p}"
        assert p.name, f"Protocol missing name: {p.id}"
        assert p.approach_id, f"Protocol missing approach_id: {p.id}"
        assert p.target_problem, f"Protocol missing target_problem: {p.id}"
        assert p.description, f"Protocol missing description: {p.id}"
        assert p.is_system is True, f"System protocol should have is_system=True: {p.id}"


def test_all_system_protocols_have_typical_sessions_and_techniques():
    """Every system protocol must declare typical_sessions and ≥3 core_techniques."""
    for p in get_system_protocols():
        assert p.typical_sessions is not None, (
            f"Protocol {p.id!r} is missing typical_sessions"
        )
        assert isinstance(p.typical_sessions, int) and p.typical_sessions > 0, (
            f"Protocol {p.id!r} typical_sessions must be a positive integer, got {p.typical_sessions!r}"
        )
        assert len(p.core_techniques) >= 3, (
            f"Protocol {p.id!r} should have ≥3 core_techniques, got {len(p.core_techniques)}"
        )


def test_system_protocols_ids_are_unique():
    ids = [p.id for p in get_system_protocols()]
    assert len(ids) == len(set(ids)), "System protocol IDs must be unique"


def test_get_protocol_by_id_found():
    p = get_protocol_by_id("cbt_depression")
    assert p is not None
    assert p.id == "cbt_depression"
    assert p.approach_id == "cbt"
    assert len(p.core_techniques) > 0


def test_get_protocol_by_id_not_found():
    p = get_protocol_by_id("nonexistent_protocol_xyz")
    assert p is None


def test_get_protocols_for_approach_cbt():
    cbt = get_protocols_for_approach("cbt")
    assert len(cbt) > 0
    for p in cbt:
        assert p.approach_id == "cbt"


def test_get_protocols_for_approach_ot():
    ot_func = get_protocols_for_approach("ot_functional")
    ot_sens = get_protocols_for_approach("ot_sensory")
    assert len(ot_func) > 0, "ot_functional approach should have at least 1 protocol"
    assert len(ot_sens) > 0, "ot_sensory approach should have at least 1 protocol"


def test_ot_protocols_exist():
    """OT protocols added per Section B requirements."""
    adl = get_protocol_by_id("ot_functional_adl")
    si = get_protocol_by_id("ot_sensory_integration")
    assert adl is not None, "ot_functional_adl protocol must exist"
    assert si is not None, "ot_sensory_integration protocol must exist"
    assert adl.approach_id == "ot_functional"
    assert si.approach_id == "ot_sensory"


def test_slp_protocols_exist():
    """SLP protocols added for Speech-Language Pathologist profession."""
    art = get_protocol_by_id("slp_articulation")
    lang = get_protocol_by_id("slp_language_delays")
    phon = get_protocol_by_id("slp_phonological_processes")
    assert art is not None, "slp_articulation protocol must exist"
    assert lang is not None, "slp_language_delays protocol must exist"
    assert phon is not None, "slp_phonological_processes protocol must exist"
    assert art.approach_id == "slp_phonological_articulation"
    assert lang.approach_id == "slp_communicative_social"
    assert phon.approach_id == "slp_phonological_articulation"


def test_slp_protocols_have_valid_sessions_and_techniques():
    """Each SLP protocol must have typical_sessions > 0 and ≥3 core_techniques."""
    for pid in ("slp_articulation", "slp_language_delays", "slp_phonological_processes"):
        p = get_protocol_by_id(pid)
        assert p is not None, f"{pid} must exist"
        assert p.typical_sessions is not None and p.typical_sessions > 0, (
            f"{pid}: typical_sessions must be a positive integer"
        )
        assert len(p.core_techniques) >= 3, (
            f"{pid}: expected ≥3 core_techniques, got {len(p.core_techniques)}"
        )


def test_slp_approach_filter():
    """get_protocols_for_approach returns the correct SLP protocols."""
    phon = get_protocols_for_approach("slp_phonological_articulation")
    comm = get_protocols_for_approach("slp_communicative_social")
    phon_ids = {p.id for p in phon}
    comm_ids = {p.id for p in comm}
    assert "slp_articulation" in phon_ids
    assert "slp_phonological_processes" in phon_ids
    assert "slp_language_delays" in comm_ids


# ---------------------------------------------------------------------------
# merge_protocols tests
# ---------------------------------------------------------------------------


def test_merge_protocols_system_only():
    system = get_system_protocols()
    merged = merge_protocols(system, [])
    assert len(merged) == len(system)
    assert all(p.is_system for p in merged)


def test_merge_protocols_adds_custom():
    system = get_system_protocols()
    custom = [
        {
            "id": "custom_test_001",
            "name": "פרוטוקול בדיקה",
            "approach_id": "cbt",
            "target_problem": "בדיקה",
            "description": "פרוטוקול לצורך בדיקה",
            "typical_sessions": 8,
            "core_techniques": ["טכניקה א", "טכניקה ב"],
        }
    ]
    merged = merge_protocols(system, custom)
    assert len(merged) == len(system) + 1
    custom_protocols = [p for p in merged if not p.is_system]
    assert len(custom_protocols) == 1
    assert custom_protocols[0].id == "custom_test_001"
    assert custom_protocols[0].is_system is False


def test_merge_protocols_skips_malformed_custom():
    system = get_system_protocols()
    malformed = [
        {"id": "bad_no_name"},   # missing required fields — should be skipped
        {},                       # completely empty
        {
            "id": "custom_good_001",
            "name": "פרוטוקול תקין",
            "approach_id": "act",
            "target_problem": "חרדה",
            "description": "פרוטוקול תקין לחרדה",
        },
    ]
    merged = merge_protocols(system, malformed)
    # Only the valid custom protocol should be appended
    custom = [p for p in merged if not p.is_system]
    assert len(custom) == 1
    assert custom[0].id == "custom_good_001"


# ---------------------------------------------------------------------------
# build_protocol_context_for_patient tests
# ---------------------------------------------------------------------------


def test_context_patient_protocols_take_priority():
    """Patient's protocol_ids override therapist's protocols_used."""
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["cbt_anxiety"],
        therapist_custom_protocols=[],
        patient_protocol_ids=["cbt_depression", "act_general"],
    )
    assert ctx["source"] == "patient"
    assert len(ctx["active_protocols"]) == 2
    ids = [p["id"] for p in ctx["active_protocols"]]
    assert "cbt_depression" in ids
    assert "act_general" in ids
    assert "cbt_anxiety" not in ids


def test_context_falls_back_to_therapist_when_no_patient_protocols():
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["dbt_skills"],
        therapist_custom_protocols=[],
        patient_protocol_ids=None,
    )
    assert ctx["source"] == "therapist"
    assert len(ctx["active_protocols"]) == 1
    assert ctx["active_protocols"][0]["id"] == "dbt_skills"


def test_context_empty_when_no_protocols_set():
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=[],
        therapist_custom_protocols=[],
        patient_protocol_ids=None,
    )
    assert ctx["source"] == "none"
    assert ctx["active_protocols"] == []
    assert ctx["protocol_summary"] == ""


def test_context_empty_patient_list_falls_back_to_therapist():
    """Empty patient list ([] not None) should fall back to therapist list."""
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["cbt_panic"],
        therapist_custom_protocols=[],
        patient_protocol_ids=[],   # explicit empty list → fall back
    )
    assert ctx["source"] == "therapist"
    assert ctx["active_protocols"][0]["id"] == "cbt_panic"


def test_context_includes_protocol_names_and_summary():
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["cbt_depression"],
        therapist_custom_protocols=[],
        patient_protocol_ids=None,
    )
    assert "CBT לדיכאון" in ctx["protocol_names"]
    assert "CBT לדיכאון" in ctx["protocol_summary"]
    assert ctx["protocol_summary"] != ""


def test_context_skips_unknown_protocol_ids():
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["cbt_depression", "nonexistent_xyz"],
        therapist_custom_protocols=[],
        patient_protocol_ids=None,
    )
    ids = [p["id"] for p in ctx["active_protocols"]]
    assert "cbt_depression" in ids
    assert "nonexistent_xyz" not in ids


def test_context_includes_custom_protocols():
    custom = [
        {
            "id": "custom_patient_001",
            "name": "פרוטוקול מותאם",
            "approach_id": "integrative",
            "target_problem": "פחד מבחינות",
            "description": "גישה אינטגרטיבית לחרדת בחינות",
            "typical_sessions": 6,
            "core_techniques": ["הרפיה", "דמיון מודרך"],
        }
    ]
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["custom_patient_001"],
        therapist_custom_protocols=custom,
        patient_protocol_ids=None,
    )
    assert ctx["source"] == "therapist"
    assert len(ctx["active_protocols"]) == 1
    assert ctx["active_protocols"][0]["id"] == "custom_patient_001"
    assert ctx["active_protocols"][0]["is_system"] is False


def test_context_multiple_protocols_pipe_separated_summary():
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["cbt_depression", "act_general"],
        therapist_custom_protocols=[],
        patient_protocol_ids=None,
    )
    assert " | " in ctx["protocol_summary"]
    assert len(ctx["protocol_names"]) == 2


def test_context_output_is_serialisable():
    """Context dict must be JSON-serialisable (no Pydantic models)."""
    import json
    ctx = build_protocol_context_for_patient(
        therapist_protocol_ids=["cbt_anxiety", "dbt_skills"],
        therapist_custom_protocols=[],
        patient_protocol_ids=None,
    )
    # Should not raise
    serialized = json.dumps(ctx)
    assert serialized
