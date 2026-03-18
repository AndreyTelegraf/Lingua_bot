from tools.community_quality_rewrite_builder_v2 import targeted_rewrite


def test_rewrite_how_to_say() -> None:
    src = "Как сказать в аптеке, что нужно что-то от горла, но без ощущения, что читаешь диссертацию?"
    out = targeted_rewrite(src)
    assert out is not None
    assert out.startswith("Что обычно говорят")
    assert "диссертацию" in out


def test_rewrite_how_to_ask_here() -> None:
    src = "Как здесь правильно спросить, если сотрудник намекает, что чего-то не хватает?"
    out = targeted_rewrite(src)
    assert out == "Что обычно спрашивают здесь, когда сотрудник намекает, что чего-то не хватает?"


def test_rewrite_how_in_conversation() -> None:
    src = "Как в разговоре обычно скажут, если цена на кассе не совпала с ценником?"
    out = targeted_rewrite(src)
    assert out == "Что обычно говорят в такой ситуации, когда цена на кассе не совпала с ценником?"


def test_rewrite_how_gently() -> None:
    src = "Как мягко намекнуть продавцу, что preço fixo звучит смело?"
    out = targeted_rewrite(src)
    assert out == "Какими словами лучше намекнуть продавцу, что preço fixo звучит смело?"
