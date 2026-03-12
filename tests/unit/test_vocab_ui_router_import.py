from bot.router import build_root_router


def test_build_root_router_with_final_vocab_ui() -> None:
    router = build_root_router()
    assert type(router).__name__ == "Router"
