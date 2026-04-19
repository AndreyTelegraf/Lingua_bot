"""
Unit tests for run_vocab_10k_monitoring.py orchestration layer.
Covers: derive_global_status, build_operator_summary structure,
policy layer (derive_track_next_action, derive_global_next_action,
derive_forbidden_actions, build_policy).
Does NOT re-test runner signal logic (covered in test_noun10k_monitoring_runner.py).
"""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts"))
from run_vocab_10k_monitoring import (
    derive_global_status,
    build_operator_summary,
    derive_track_next_action,
    derive_global_next_action,
    derive_forbidden_actions,
    build_policy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_section(verdict: str, pos: str = "noun", bin_name: str = "10K") -> dict:
    """Minimal section dict sufficient for derive_global_status and build_operator_summary."""
    minimum_met = verdict != "INSUFFICIENT_DATA"
    trigger_eval: dict = {
        "minimum_sample_met": minimum_met,
        "total_sessions": 35 if minimum_met else 10,
        "distinct_users": 4 if minimum_met else 1,
        "verdict": verdict,
        "verdict_note": f"test note for {verdict}",
    }
    if minimum_met:
        for key, code in [
            ("T1", "REPEAT_SATURATION"),
            ("T2", "POOL_DEPLETION"),
            ("T3", "COVERAGE_FAILURE"),
            ("T4", "EXPOSURE_SKEW"),
        ]:
            trigger_eval[key] = {
                "code": code,
                "fires": False,
                "mean_repeat_rate": 0.1,
                "threshold": 0.33,
                "mean_items_per_session": 2.5,
                "sessions_evaluated": 10,
                "items_with_shown_gte_3": 8,
                "total_active_items": 13,
                "items_shown": 3,
                "max_sessions_shown": 2,
                "pool_median_sessions_shown": 1.0,
                "top_threshold": 8,
                "median_threshold": 3,
            }
        trigger_eval["broken_items"] = []
        trigger_eval["too_easy_items"] = []

    return {
        "pos": pos,
        "bin_name": bin_name,
        "summary": {
            "total_real_sessions": trigger_eval["total_sessions"],
            "distinct_real_users": trigger_eval["distinct_users"],
            "sessions_with_items": 5,
            "mean_items_per_session": 2.0,
            "active_items": 13,
        },
        "signal_scope_note": "test",
        "signal1_items_per_session": [],
        "signal2_exposure_per_item": [],
        "signal3_repeat_rate": {},
        "signal4_correctness": [],
        "trigger_evaluation": trigger_eval,
        "verdict": verdict,
        "verdict_note": f"test note for {verdict}",
    }


def _make_report(noun_verdict: str, verb_verdict: str) -> dict:
    noun_s = _make_section(noun_verdict, pos="noun")
    verb_s = _make_section(verb_verdict, pos="verb")
    return {
        "report_generated_at": "2026-04-19T10:00:00Z",
        "db_path": "/tmp/test.db",
        "real_session_filter": "status='finished'",
        "real_session_filter_note": "test",
        "summary": {
            "total_real_sessions": noun_s["summary"]["total_real_sessions"],
            "distinct_real_users": noun_s["summary"]["distinct_real_users"],
            "sessions_with_noun10k": 0,
            "mean_noun10k_per_session": None,
            "active_noun10k_items": 13,
        },
        "signal_scope_note": "test",
        "signal1_items_per_session": [],
        "signal2_exposure_per_item": [],
        "signal3_repeat_rate": {},
        "signal4_correctness": [],
        "trigger_evaluation": noun_s["trigger_evaluation"],
        "verdict": noun_verdict,
        "verdict_note": f"test note for {noun_verdict}",
        "noun_10k": noun_s,
        "verb_10k": verb_s,
    }


# ---------------------------------------------------------------------------
# derive_global_status tests
# ---------------------------------------------------------------------------


def test_global_status_both_hold():
    report = _make_report("HOLD", "HOLD")
    assert derive_global_status(report) == "HOLD"


def test_global_status_both_insufficient():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    assert derive_global_status(report) == "INSUFFICIENT_DATA"


def test_global_status_one_prepare_one_hold():
    report = _make_report("PREPARE_NEXT_TRANCHE", "HOLD")
    assert derive_global_status(report) == "PREPARE_NEXT_TRANCHE"


def test_global_status_one_prepare_one_hold_reversed():
    report = _make_report("HOLD", "PREPARE_NEXT_TRANCHE")
    assert derive_global_status(report) == "PREPARE_NEXT_TRANCHE"


def test_global_status_investigate_beats_hold():
    report = _make_report("INVESTIGATE_SIGNAL", "HOLD")
    assert derive_global_status(report) == "INVESTIGATE_SIGNAL"


def test_global_status_investigate_beats_insufficient():
    report = _make_report("INVESTIGATE_SIGNAL", "INSUFFICIENT_DATA")
    assert derive_global_status(report) == "INVESTIGATE_SIGNAL"


def test_global_status_investigate_beats_prepare():
    report = _make_report("INVESTIGATE_SIGNAL", "PREPARE_NEXT_TRANCHE")
    assert derive_global_status(report) == "INVESTIGATE_SIGNAL"


def test_global_status_insufficient_beats_prepare():
    report = _make_report("INSUFFICIENT_DATA", "PREPARE_NEXT_TRANCHE")
    assert derive_global_status(report) == "INSUFFICIENT_DATA"


def test_global_status_insufficient_beats_hold():
    report = _make_report("INSUFFICIENT_DATA", "HOLD")
    assert derive_global_status(report) == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# build_operator_summary structure tests
# ---------------------------------------------------------------------------


def test_summary_contains_global_status():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    global_status = derive_global_status(report)
    md = build_operator_summary(report, global_status, "/tmp/report.json")
    assert "INSUFFICIENT_DATA" in md


def test_summary_contains_noun_track():
    report = _make_report("HOLD", "HOLD")
    md = build_operator_summary(report, "HOLD", "/tmp/report.json")
    assert "NOUN/10K" in md


def test_summary_contains_verb_track():
    report = _make_report("HOLD", "HOLD")
    md = build_operator_summary(report, "HOLD", "/tmp/report.json")
    assert "VERB/10K" in md


def test_summary_tranche_not_authorized_when_insufficient():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    md = build_operator_summary(report, "INSUFFICIENT_DATA", "/tmp/report.json")
    assert "Any tranche prep/apply authorized | NO" in md


def test_summary_tranche_authorized_when_prepare():
    report = _make_report("PREPARE_NEXT_TRANCHE", "PREPARE_NEXT_TRANCHE")
    md = build_operator_summary(report, "PREPARE_NEXT_TRANCHE", "/tmp/report.json")
    assert "Any tranche prep/apply authorized | YES" in md


def test_summary_do_not_line_present_when_insufficient():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    md = build_operator_summary(report, "INSUFFICIENT_DATA", "/tmp/report.json")
    assert "DO NOT prepare or activate" in md


def test_summary_do_not_line_present_when_investigate():
    report = _make_report("INVESTIGATE_SIGNAL", "HOLD")
    md = build_operator_summary(report, "INVESTIGATE_SIGNAL", "/tmp/report.json")
    assert "DO NOT activate any tranche" in md


def test_summary_next_step_collect_data_when_insufficient():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    md = build_operator_summary(report, "INSUFFICIENT_DATA", "/tmp/report.json")
    assert "Collect more live sessions" in md


def test_summary_trigger_eligible_shows_track_when_prepare():
    report = _make_report("HOLD", "PREPARE_NEXT_TRANCHE")
    md = build_operator_summary(report, "PREPARE_NEXT_TRANCHE", "/tmp/report.json")
    assert "VERB/10K" in md
    assert "Any track trigger-eligible | YES" in md


def test_summary_global_status_line_present():
    report = _make_report("HOLD", "HOLD")
    md = build_operator_summary(report, "HOLD", "/tmp/report.json")
    assert "Overall status | **HOLD**" in md


def test_summary_json_path_referenced():
    report = _make_report("HOLD", "HOLD")
    md = build_operator_summary(report, "HOLD", "/tmp/my_report.json")
    assert "/tmp/my_report.json" in md


# ---------------------------------------------------------------------------
# derive_track_next_action tests
# ---------------------------------------------------------------------------


def test_track_action_insufficient_data():
    assert derive_track_next_action("INSUFFICIENT_DATA") == "WAIT_FOR_MORE_REAL_SESSIONS"


def test_track_action_hold():
    assert derive_track_next_action("HOLD") == "HOLD_AND_OBSERVE"


def test_track_action_prepare():
    assert derive_track_next_action("PREPARE_NEXT_TRANCHE") == "PREPARE_NEXT_TRANCHE_ALLOWED"


def test_track_action_investigate():
    assert derive_track_next_action("INVESTIGATE_SIGNAL") == "INVESTIGATE_REQUIRED"


def test_track_action_unknown_defaults_to_hold():
    assert derive_track_next_action("SOMETHING_NEW") == "HOLD_AND_OBSERVE"


# ---------------------------------------------------------------------------
# derive_global_next_action tests
# ---------------------------------------------------------------------------


def test_global_action_all_hold():
    per_track = {"noun_10k": "HOLD_AND_OBSERVE", "verb_10k": "HOLD_AND_OBSERVE"}
    assert derive_global_next_action(per_track) == "HOLD_AND_OBSERVE"


def test_global_action_wait_beats_hold():
    per_track = {"noun_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "verb_10k": "HOLD_AND_OBSERVE"}
    assert derive_global_next_action(per_track) == "WAIT_FOR_MORE_REAL_SESSIONS"


def test_global_action_investigate_beats_wait():
    per_track = {
        "noun_10k": "INVESTIGATE_REQUIRED",
        "verb_10k": "WAIT_FOR_MORE_REAL_SESSIONS",
    }
    assert derive_global_next_action(per_track) == "INVESTIGATE_REQUIRED"


def test_global_action_investigate_beats_prepare():
    per_track = {
        "noun_10k": "INVESTIGATE_REQUIRED",
        "verb_10k": "PREPARE_NEXT_TRANCHE_ALLOWED",
    }
    assert derive_global_next_action(per_track) == "INVESTIGATE_REQUIRED"


def test_global_action_wait_beats_prepare():
    per_track = {
        "noun_10k": "WAIT_FOR_MORE_REAL_SESSIONS",
        "verb_10k": "PREPARE_NEXT_TRANCHE_ALLOWED",
    }
    assert derive_global_next_action(per_track) == "WAIT_FOR_MORE_REAL_SESSIONS"


def test_global_action_prepare_when_both_eligible():
    per_track = {
        "noun_10k": "PREPARE_NEXT_TRANCHE_ALLOWED",
        "verb_10k": "PREPARE_NEXT_TRANCHE_ALLOWED",
    }
    assert derive_global_next_action(per_track) == "PREPARE_NEXT_TRANCHE_ALLOWED"


# ---------------------------------------------------------------------------
# derive_forbidden_actions tests
# ---------------------------------------------------------------------------


def test_forbidden_always_contains_do_not_activate():
    forbidden = derive_forbidden_actions("WAIT_FOR_MORE_REAL_SESSIONS")
    assert "DO_NOT_ACTIVATE_ANYTHING" in forbidden


def test_forbidden_always_contains_selector_and_runtime():
    forbidden = derive_forbidden_actions("HOLD_AND_OBSERVE")
    assert "DO_NOT_TOUCH_SELECTOR" in forbidden
    assert "DO_NOT_TOUCH_RUNTIME" in forbidden


def test_forbidden_always_contains_bank_guards():
    forbidden = derive_forbidden_actions("HOLD_AND_OBSERVE")
    assert "DO_NOT_MODIFY_NOUN10K" in forbidden
    assert "DO_NOT_MODIFY_VERB10K" in forbidden
    assert "DO_NOT_OPEN_ADVERBS" in forbidden


def test_forbidden_includes_no_tranche_when_not_prepare_allowed():
    for action in ["WAIT_FOR_MORE_REAL_SESSIONS", "HOLD_AND_OBSERVE", "INVESTIGATE_REQUIRED"]:
        forbidden = derive_forbidden_actions(action)
        assert "DO_NOT_PREPARE_NEW_TRANCHE" in forbidden, f"missing for {action}"


def test_forbidden_excludes_no_tranche_when_prepare_allowed():
    forbidden = derive_forbidden_actions("PREPARE_NEXT_TRANCHE_ALLOWED")
    assert "DO_NOT_PREPARE_NEW_TRANCHE" not in forbidden


def test_forbidden_still_blocks_activation_when_prepare_allowed():
    forbidden = derive_forbidden_actions("PREPARE_NEXT_TRANCHE_ALLOWED")
    assert "DO_NOT_ACTIVATE_ANYTHING" in forbidden


def test_forbidden_is_deterministic():
    a = derive_forbidden_actions("HOLD_AND_OBSERVE")
    b = derive_forbidden_actions("HOLD_AND_OBSERVE")
    assert a == b


# ---------------------------------------------------------------------------
# build_policy tests
# ---------------------------------------------------------------------------


def test_build_policy_returns_required_keys():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    assert "per_track_next_actions" in policy
    assert "global_next_action" in policy
    assert "forbidden_actions" in policy
    assert "global_next_action_description" in policy


def test_build_policy_per_track_has_both_tracks():
    report = _make_report("HOLD", "INSUFFICIENT_DATA")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    assert "noun_10k" in policy["per_track_next_actions"]
    assert "verb_10k" in policy["per_track_next_actions"]


def test_build_policy_global_action_conservative():
    report = _make_report("HOLD", "INSUFFICIENT_DATA")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    # One HOLD, one INSUFFICIENT → global must be WAIT_FOR_MORE_REAL_SESSIONS
    assert policy["global_next_action"] == "WAIT_FOR_MORE_REAL_SESSIONS"


def test_build_policy_description_not_empty():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    assert len(policy["global_next_action_description"]) > 10


# ---------------------------------------------------------------------------
# Operator summary with policy sections
# ---------------------------------------------------------------------------


def test_summary_authorized_section_present_with_policy():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    md = build_operator_summary(report, "INSUFFICIENT_DATA", "/tmp/r.json", policy=policy)
    assert "## Authorized Now" in md


def test_summary_forbidden_section_present_with_policy():
    report = _make_report("INSUFFICIENT_DATA", "INSUFFICIENT_DATA")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    md = build_operator_summary(report, "INSUFFICIENT_DATA", "/tmp/r.json", policy=policy)
    assert "## Forbidden Now" in md


def test_summary_forbidden_lists_do_not_activate():
    report = _make_report("HOLD", "HOLD")
    policy = build_policy(report, "HOLD")
    md = build_operator_summary(report, "HOLD", "/tmp/r.json", policy=policy)
    assert "DO_NOT_ACTIVATE_ANYTHING" in md


def test_summary_forbidden_lists_no_prepare_when_blocked():
    report = _make_report("INSUFFICIENT_DATA", "HOLD")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    md = build_operator_summary(report, "INSUFFICIENT_DATA", "/tmp/r.json", policy=policy)
    assert "DO_NOT_PREPARE_NEW_TRANCHE" in md


def test_summary_policy_absent_when_no_policy_arg():
    """Existing callers that omit policy arg still get a valid summary."""
    report = _make_report("HOLD", "HOLD")
    md = build_operator_summary(report, "HOLD", "/tmp/r.json")
    assert "## Authorized Now" not in md
    assert "## Forbidden Now" not in md


def test_summary_global_action_code_in_authorized_section():
    report = _make_report("HOLD", "HOLD")
    policy = build_policy(report, "HOLD")
    md = build_operator_summary(report, "HOLD", "/tmp/r.json", policy=policy)
    assert "HOLD_AND_OBSERVE" in md


def test_summary_per_track_actions_listed():
    report = _make_report("HOLD", "INSUFFICIENT_DATA")
    policy = build_policy(report, "INSUFFICIENT_DATA")
    md = build_operator_summary(report, "INSUFFICIENT_DATA", "/tmp/r.json", policy=policy)
    assert "NOUN/10K" in md
    assert "VERB/10K" in md
