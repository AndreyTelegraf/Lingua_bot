from bot.router import build_root_router


def test_root_router_builds() -> None:
    router = build_root_router()
    assert router is not None
