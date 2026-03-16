from services.vocab_runtime.repo import _build_vocab_attempt_snapshot_payload_from_stats
import json

def test_build_vocab_attempt_snapshot_payload_from_stats():
    product_band, confidence, payload_json = _build_vocab_attempt_snapshot_payload_from_stats(
        stats={
            "estimated_vocab_size": 3250,
            "correct_answers": 12,
            "total_questions": 24,
            "finished_at": "2026-03-16T12:00:00Z",
            "confidence": 0.82,
            "dont_know_count": 3,
        }
    )
    payload = json.loads(payload_json)
    assert product_band == "B1"
    assert confidence == 0.82
    assert payload["product_band"] == "B1"
    assert payload["range_min"] == 2500
    assert payload["range_max"] == 4000
    assert payload["correct_count"] == 12
    assert payload["total_questions"] == 24
