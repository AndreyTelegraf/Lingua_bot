from pathlib import Path

def test_modes_vocab_engine_calls_async_handoff_writer():
    text = Path("modes/vocab/engine.py").read_text(encoding="utf-8")
    assert "persist_finished_result(conn" not in text
    assert "await repo.persist_vocab_handoff_snapshot(" in text
