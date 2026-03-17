from pathlib import Path

def test_activation_gate_requires_playable_contract_and_no_active_lemma_pos_duplicate() -> None:
    text = Path("services/vocab_bank/validate_items.py").read_text(encoding="utf-8")

    required_fragments = [
        "UPDATE vocab_items",
        "SET is_active = 1",
        "SELECT COUNT(*)",
        "FROM vocab_choices vc",
        "WHERE vc.item_id = vocab_items.id",
        ") = 6",
        "SUM(CASE WHEN COALESCE(vc.is_correct,0)=1 THEN 1 ELSE 0 END)",
        ") = 1",
        "COUNT(DISTINCT TRIM(LOWER(vc.choice_text)))",
        "LEFT JOIN vocab_items vi2",
        "TRIM(LOWER(vi2.lemma)) = TRIM(LOWER(vc.choice_text))",
        "COALESCE(vc.is_correct,0) = 0",
        "vi2.id IS NULL",
        "FROM vocab_items v2",
        "v2.is_active = 1",
        "v2.id != vocab_items.id",
        "TRIM(LOWER(v2.lemma)) = TRIM(LOWER(vocab_items.lemma))",
        "COALESCE(TRIM(LOWER(v2.pos)), '') = COALESCE(TRIM(LOWER(vocab_items.pos)), '')",
    ]

    for fragment in required_fragments:
        assert fragment in text, f"missing activation-gate fragment: {fragment}"
