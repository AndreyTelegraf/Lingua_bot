from services.vocab_runtime.result_snapshot import build_vocab_result_snapshot


def test_build_vocab_result_snapshot_contains_expected_fields():
    snapshot = build_vocab_result_snapshot(
        range_min=2500,
        range_max=4000,
        correct_count=12,
        total_questions=24,
        dont_know_rate=0.25,
        fast_answer_rate=0.18,
        slow_answer_rate=0.11,
        generated_at="2026-03-16T12:00:00Z",
    ).to_json_dict()

    assert snapshot["mode"] == "vocab"
    assert snapshot["spec_version"] == "vocab_v2"
    assert snapshot["scoring_version"] == "vocab_scoring_v2"
    assert snapshot["product_band"] == "B1"
    assert snapshot["range_min"] == 2500
    assert snapshot["range_max"] == 4000
    assert snapshot["correct_count"] == 12
    assert snapshot["total_questions"] == 24
    assert snapshot["confidence"] in {"low", "medium", "high"}
    assert snapshot["fresh_until_days"] == 90
    assert snapshot["prior_bucket"] == "b1"
    assert snapshot["prior_theta_hint"] == 0.2
    assert snapshot["behavioral_flags"]["dont_know_rate"] == 0.25
    assert snapshot["generated_at"] == "2026-03-16T12:00:00Z"
