from bot.common_handlers.start import build_start_router


def test_build_start_router_smoke() -> None:
    router = build_start_router()
    assert router is not None
