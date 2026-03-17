from app.config import get_settings


def vocab_enabled() -> bool:
    return get_settings().feature_vocab_enabled


def level_enabled() -> bool:
    return get_settings().feature_level_enabled


def ciple_enabled() -> bool:
    return get_settings().feature_ciple_enabled


def community_enabled() -> bool:
    return get_settings().feature_community_enabled
