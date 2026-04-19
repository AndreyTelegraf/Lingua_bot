"""
Unit tests for build_status_snapshot() in run_vocab_10k_monitoring.py.

Tests use synthetic minimal report/policy dicts — no DB required.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts"))

from run_vocab_10k_monitoring import build_status_snapshot, MINIMUM_SESSIONS, MINIMUM_USERS


def _make_track_section(pos: str, bin_name: str, verdict: str, active_items: int, gate_met: bool):
    tr: dict = {
        "minimum_sample_met": gate_met,
        "verdict": verdict,
        "verdict_note": f"test note for {pos}/{bin_name}",
    }
    if gate_met:
        tr.update({
            "T1": {"code": "REPEAT_SATURATION", "fires": False, "mean_repeat_rate": 0.1, "threshold": 0.33},
            "T2": {"code": "POOL_DEPLETION", "fires": False, "mean_items_per_session": 2.0, "sessions_evaluated": 10, "threshold": 1.5},
            "T3": {"code": "COVERAGE_FAILURE", "fires": False, "items_with_shown_gte_3": active_items, "total_active_items": active_items, "threshold": 10},
            "T4": {"code": "EXPOSURE_SKEW", "fires": False, "max_sessions_shown": 3, "pool_median_sessions_shown": 2},
            "broken_items": [],
            "too_easy_items": [],
        })
    else:
        tr["verdict_note"] = f"Need {MINIMUM_SESSIONS} sessions. Currently 0."

    return {
        "pos": pos,
        "bin_name": bin_name,
        "summary": {
            "total_real_sessions": 0 if not gate_met else MINIMUM_SESSIONS,
            "distinct_real_users": 0 if not gate_met else MINIMUM_USERS,
            "sessions_with_items": 0,
            "mean_items_per_session": None,
            "active_items": active_items,
        },
        "signal1_items_per_session": [],
        "signal2_exposure_per_item": [],
        "signal3_repeat_rate": {},
        "signal4_correctness": [],
        "trigger_evaluation": tr,
        "verdict": verdict,
        "verdict_note": tr["verdict_note"],
    }


def _make_report(noun_verdict="INSUFFICIENT_DATA", verb_verdict="INSUFFICIENT_DATA",
                 adverb_verdict="INSUFFICIENT_DATA", sessions=0, users=0):
    return {
        "report_generated_at": "2026-04-20T00:00:00Z",
        "db_path": "data/lingua_staging.db",
        "real_session_filter": "status = 'finished'",
        "real_session_filter_note": "test",
        "summary": {
            "total_real_sessions": sessions,
            "distinct_real_users": users,
            "sessions_with_noun10k": 0,
            "mean_noun10k_per_session": None,
            "active_noun10k_items": 13,
        },
        "noun_10k": _make_track_section("noun", "10K", noun_verdict, 13, gate_met=(sessions >= MINIMUM_SESSIONS and users >= MINIMUM_USERS)),
        "verb_10k": _make_track_section("verb", "10K", verb_verdict, 50, gate_met=(sessions >= MINIMUM_SESSIONS and users >= MINIMUM_USERS)),
        "adverb_5k": _make_track_section("adverb", "5K", adverb_verdict, 16, gate_met=(sessions >= MINIMUM_SESSIONS and users >= MINIMUM_USERS)),
    }


def _make_policy(global_status: str, per_track_actions: dict, global_action: str, forbidden: list):
    return {
        "global_status": global_status,
        "per_track_next_actions": per_track_actions,
        "global_next_action": global_action,
        "global_next_action_description": "test description",
        "forbidden_actions": forbidden,
    }


class TestBuildStatusSnapshot:

    def test_insufficient_data_contains_all_three_tracks(self):
        report = _make_report(sessions=10, users=1)
        policy = _make_policy(
            "INSUFFICIENT_DATA",
            {"noun_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "verb_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "adverb_5k": "WAIT_FOR_MORE_REAL_SESSIONS"},
            "WAIT_FOR_MORE_REAL_SESSIONS",
            ["DO_NOT_ACTIVATE_ANYTHING", "DO_NOT_PREPARE_NEW_TRANCHE"],
        )
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        assert "noun/10K" in snap
        assert "verb/10K" in snap
        assert "adverb/5K" in snap

    def test_snapshot_has_all_four_sections(self):
        report = _make_report(sessions=5, users=1)
        policy = _make_policy(
            "INSUFFICIENT_DATA",
            {"noun_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "verb_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "adverb_5k": "WAIT_FOR_MORE_REAL_SESSIONS"},
            "WAIT_FOR_MORE_REAL_SESSIONS",
            ["DO_NOT_ACTIVATE_ANYTHING"],
        )
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        assert "## 1. Track Summary" in snap
        assert "## 2. Global Summary" in snap
        assert "## 3. Current Position" in snap
        assert "## 4. Exact Next Step" in snap

    def test_exact_next_step_references_gate_numbers(self):
        report = _make_report(sessions=21, users=2)
        policy = _make_policy(
            "INSUFFICIENT_DATA",
            {"noun_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "verb_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "adverb_5k": "WAIT_FOR_MORE_REAL_SESSIONS"},
            "WAIT_FOR_MORE_REAL_SESSIONS",
            [],
        )
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        assert str(MINIMUM_SESSIONS) in snap
        assert str(MINIMUM_USERS) in snap
        assert "21 sessions" in snap
        assert "2 users" in snap

    def test_forbidden_actions_all_present(self):
        forbidden = ["DO_NOT_ACTIVATE_ANYTHING", "DO_NOT_PREPARE_NEW_TRANCHE", "DO_NOT_TOUCH_SELECTOR"]
        report = _make_report()
        policy = _make_policy("INSUFFICIENT_DATA", {}, "WAIT_FOR_MORE_REAL_SESSIONS", forbidden)
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        for item in forbidden:
            assert item in snap

    def test_tranche_not_authorized_when_insufficient(self):
        report = _make_report(sessions=10, users=1)
        policy = _make_policy(
            "INSUFFICIENT_DATA",
            {"noun_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "verb_10k": "WAIT_FOR_MORE_REAL_SESSIONS", "adverb_5k": "WAIT_FOR_MORE_REAL_SESSIONS"},
            "WAIT_FOR_MORE_REAL_SESSIONS",
            ["DO_NOT_ACTIVATE_ANYTHING", "DO_NOT_PREPARE_NEW_TRANCHE"],
        )
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        assert "NO" in snap  # tranche authorized = NO
        assert "YES" not in snap.split("Any tranche")[1].split("\n")[0]

    def test_global_status_in_global_summary(self):
        for status in ["INSUFFICIENT_DATA", "HOLD", "PREPARE_NEXT_TRANCHE", "INVESTIGATE_SIGNAL"]:
            report = _make_report()
            policy = _make_policy(status, {}, "WAIT_FOR_MORE_REAL_SESSIONS", [])
            snap = build_status_snapshot(report, status, policy)
            assert status in snap

    def test_active_item_counts_present(self):
        report = _make_report(sessions=10, users=1)
        policy = _make_policy("INSUFFICIENT_DATA", {
            "noun_10k": "WAIT_FOR_MORE_REAL_SESSIONS",
            "verb_10k": "WAIT_FOR_MORE_REAL_SESSIONS",
            "adverb_5k": "WAIT_FOR_MORE_REAL_SESSIONS",
        }, "WAIT_FOR_MORE_REAL_SESSIONS", [])
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        assert "13" in snap   # noun active items
        assert "50" in snap   # verb active items
        assert "16" in snap   # adverb active items

    def test_hold_status_current_position(self):
        report = _make_report()
        policy = _make_policy("HOLD", {}, "HOLD_AND_OBSERVE", [])
        snap = build_status_snapshot(report, "HOLD", policy)
        assert "hold-and-observe" in snap.lower() or "HOLD" in snap

    def test_returns_string_ending_with_newline(self):
        report = _make_report()
        policy = _make_policy("INSUFFICIENT_DATA", {}, "WAIT_FOR_MORE_REAL_SESSIONS", [])
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        assert isinstance(snap, str)
        assert snap.endswith("\n")

    def test_no_db_references_to_writes(self):
        report = _make_report()
        policy = _make_policy("INSUFFICIENT_DATA", {}, "WAIT_FOR_MORE_REAL_SESSIONS", [])
        snap = build_status_snapshot(report, "INSUFFICIENT_DATA", policy)
        # Snapshot must clearly state read-only
        assert "no DB writes" in snap or "read-only" in snap.lower() or "Read-only" in snap
