from __future__ import annotations

import re
from dataclasses import dataclass, asdict

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_RE = re.compile(r"[A-Za-z]")
TOKEN_RE = re.compile(r"[А-Яа-яЁёA-Za-z0-9-]+")
MULTISPACE_RE = re.compile(r"\s+")

RU_ADV_RE = re.compile(r"(о|е|ски|цки|ьи|ьй)$")
RU_ADJ_RE = re.compile(r"(ый|ий|ой|ая|яя|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ых|их|ую|юю)$")
RU_INF_RE = re.compile(r"(ться|тись|чься|ать|ять|еть|ить|ыть|уть|оть|ти|чь)$")

TRANSLIT_EXACT = {
    "седо",
    "талвез",
}

GENERIC_AI_GLOSSES = {
    "хорошо",
    "плохо",
}

BAD_NON_ADVERB_SINGLE_WORDS = {
    "дом",
    "кровать",
    "женщина",
    "радость",
    "скорость",
    "сеть",
    "путь",
    "клей",
    "хороший",
    "плохой",
}

ADVERB_WHITELIST_MULTIWORD = {
    "по крайней мере",
    "в целом",
    "в общем",
    "впервые в жизни",
}

KNOWN_GOOD_ADVERBS = {
    "есть",
    "нет",
    "рано",
    "поздно",
    "возможно",
    "нельзя",
    "можно",
    "нужно",
    "недавно",
    "сегодня",
    "вчера",
    "завтра",
}

ADVERB_SAFE_LEMMA_GLOSS = {
    ("quase", "почти"),
    ("embora", "прочь"),
    ("principalmente", "главным образом"),
    ("bem", "хорошо"),
    ("mal", "плохо"),
}


@dataclass(slots=True)
class RuleResult:
    status: str
    risk_score: int
    flags: list[str]
    normalized_correct_answer: str
    suggested_action: str
    explanation: str

    def to_dict(self) -> dict:
        return asdict(self)


def normalize_text(text: str) -> str:
    text = (text or "").strip().lower().replace("ё", "е")
    text = (
        text.replace("\u0301", "")
            .replace("а́", "а")
            .replace("е́", "е")
            .replace("и́", "и")
            .replace("о́", "о")
            .replace("у́", "у")
            .replace("ы́", "ы")
            .replace("э́", "э")
            .replace("ю́", "ю")
            .replace("я́", "я")
    )
    text = MULTISPACE_RE.sub(" ", text)
    return text


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def has_cyrillic(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text))


def has_latin(text: str) -> bool:
    return bool(LATIN_RE.search(text))


def translit_like_ru(lemma: str, gloss: str) -> bool:
    l = normalize_text(lemma)
    g = normalize_text(gloss)
    if g in TRANSLIT_EXACT:
        return True
    if not l or not g or has_latin(g):
        return False
    if abs(len(l) - len(g)) <= 2:
        shared = len(set(l) & set(g))
        return shared >= max(3, min(len(set(l)), len(set(g))) - 1)
    return False


def lemma_phonetic_copy(lemma: str, gloss: str) -> bool:
    l = normalize_text(lemma)
    g = normalize_text(gloss)
    if g in TRANSLIT_EXACT:
        return True
    if not l or not g:
        return False
    if abs(len(l) - len(g)) <= 2:
        shared = sum(1 for ch in l if ch in g)
        return shared >= max(3, int(len(l) * 0.6))
    return False


def looks_like_adverb(gloss: str) -> bool:
    g = normalize_text(gloss)
    toks = TOKEN_RE.findall(g)
    if not toks:
        return False
    if g in ADVERB_WHITELIST_MULTIWORD:
        return True
    if len(toks) == 1 and toks[0] in KNOWN_GOOD_ADVERBS:
        return True
    if len(toks) == 1:
        return bool(RU_ADV_RE.search(toks[0]))
    return g in ADVERB_WHITELIST_MULTIWORD


def evaluate_adverb_ru_gloss(*, lemma: str, pos: str, gloss: str) -> RuleResult:
    flags: list[str] = []
    risk = 0
    g = normalize_text(gloss)
    tok_n = token_count(g)

    if pos != "adverb":
        flags.append("pos_not_adverb_input")
        risk += 100

    if not g or len(g) < 2:
        flags.append("too_short")
        risk += 100

    if has_latin(g) and has_cyrillic(g):
        flags.append("mixed_script")
        risk += 100
    elif has_latin(g):
        flags.append("latin_chars_in_ru_gloss")
        risk += 100
        if g.isascii():
            flags.append("english_leakage")
            risk += 100

    if tok_n >= 4 and g not in ADVERB_WHITELIST_MULTIWORD:
        flags.append("too_long_for_adverb_gloss")
        risk += 30
    if tok_n >= 6 and g not in ADVERB_WHITELIST_MULTIWORD:
        risk += 100

    if tok_n >= 2 and g not in ADVERB_WHITELIST_MULTIWORD:
        flags.append("phrase_like_gloss")
        risk += 10
    if tok_n >= 3 and g not in ADVERB_WHITELIST_MULTIWORD:
        risk += 40

    if (normalize_text(lemma), g) not in ADVERB_SAFE_LEMMA_GLOSS and g in GENERIC_AI_GLOSSES:
        flags.append("generic_ai_gloss")
        risk += 35

    if translit_like_ru(lemma, g):
        flags.append("translit_like_ru")
        risk += 80

    if lemma_phonetic_copy(lemma, g):
        flags.append("lemma_phonetic_copy")
        risk += 50

    toks = TOKEN_RE.findall(g)
    if toks and toks[0] in BAD_NON_ADVERB_SINGLE_WORDS:
        flags.append("non_adverb_gloss_candidate")
        risk += 60

    if (normalize_text(lemma), g) not in ADVERB_SAFE_LEMMA_GLOSS and toks and RU_ADJ_RE.search(toks[0]):
        flags.append("adjective_like_gloss")
        risk += 25

    if (normalize_text(lemma), g) not in ADVERB_SAFE_LEMMA_GLOSS and toks and RU_INF_RE.search(toks[0]):
        flags.append("verb_like_gloss")
        risk += 50

    if (normalize_text(lemma), g) not in ADVERB_SAFE_LEMMA_GLOSS and not looks_like_adverb(g):
        flags.append("not_adverb_like")
        risk += 20

    strong_reject = {
        "latin_chars_in_ru_gloss",
        "english_leakage",
        "mixed_script",
        "too_short",
    }

    reject = False
    if "translit_like_ru" in flags and "lemma_phonetic_copy" in flags:
        reject = True
    if any(f in strong_reject for f in flags):
        reject = True
    if tok_n >= 6 and g not in ADVERB_WHITELIST_MULTIWORD:
        reject = True

    if reject:
        status = "reject"
        action = "deactivate"
    elif (
        risk >= 50
        or "generic_ai_gloss" in flags
        or "non_adverb_gloss_candidate" in flags
        or "verb_like_gloss" in flags
    ):
        status = "review"
        action = "fix_needed"
    else:
        status = "ok"
        action = "keep"

    return RuleResult(
        status=status,
        risk_score=risk,
        flags=sorted(set(flags)),
        normalized_correct_answer=g,
        suggested_action=action,
        explanation=f"lemma={lemma}; pos={pos}; gloss={g}; flags={','.join(sorted(set(flags))) or 'none'}; risk={risk}",
    )
