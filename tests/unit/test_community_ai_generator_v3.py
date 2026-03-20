from __future__ import annotations

from services.community_block.ai_generator import generate_from_prompt_payload


def test_generate_from_prompt_payload_uses_provider(monkeypatch) -> None:
    class DummyResult:
        provider = "openai"
        model = "gpt-5"
        output_text = "Короткий человеческий ответ."
        response_id = "resp_test"
        raw = {"id": "resp_test"}

    def fake_generate_reply(*, system_prompt: str, developer_prompt: str, user_prompt: str, model=None):
        assert system_prompt == "sys"
        assert developer_prompt == "dev"
        assert user_prompt == "usr"
        assert model == "gpt-5"
        return DummyResult()

    monkeypatch.setattr("services.community_block.ai_generator.generate_reply", fake_generate_reply)

    out = generate_from_prompt_payload(
        {
            "system_prompt": "sys",
            "developer_prompt": "dev",
            "user_prompt": "usr",
        },
        model="gpt-5",
    )

    assert out.provider == "openai"
    assert out.model == "gpt-5"
    assert out.text == "Короткий человеческий ответ."
    assert out.response_id == "resp_test"
