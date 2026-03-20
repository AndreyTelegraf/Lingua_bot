from __future__ import annotations

from aiogram import Router

from bot.common_handlers.start import build_start_router
from bot.common_handlers.community_ai import build_community_ai_router
from bot.common_handlers.vocab_v2 import build_vocab_v2_router
from bot.common_handlers.admin_stats import build_admin_stats_router
from modes.vocab.router import build_vocab_router
from modes.vocab.router_review_patch import build_vocab_review_router


def build_root_router() -> Router:
    router = Router(name="root")
    router.include_router(build_start_router())
    router.include_router(build_admin_stats_router())
    router.include_router(build_community_ai_router())
    router.include_router(build_vocab_router())
    router.include_router(build_vocab_review_router())
    router.include_router(build_vocab_v2_router())
    return router
