from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Iterable


CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")
LATIN_RE = re.compile(r"[A-Za-z]")
TOKEN_RE = re.compile(r"[А-Яа-яЁёA-Za-z0-9-]+")
MULTISPACE_RE = re.compile(r"\s+")
INF_RE = re.compile(r"(аться|яться|еться|иться|оться|уться|ать|ять|еть|ить|оть|уть)$")
ADJ_RE = re.compile(r"(ый|ий|ой|ая|ое|ее|ые|ие|ого|его|ому|ему|ым|им|ых|их|ую|юю)$")
ADV_RE = re.compile(r"о$")
BAD_BIGRAMS = (
    "дю", "тч", "чж", "кх", "гх", "джр", "ртх", "чр", "щк", "дтс"
)

TRANSLIT_EXACT = {
    "дюрант",
    "ачар",
}

SUSPICIOUS_GENERIC = {
    "лучший друг",
    "родина",
    "женщина",
    "практика",
    "ночь без сна",
}

MULTIWORD_WHITELIST = {
    "местное самоуправление",
    "населенный пункт",
    "точка зрения",
    "рабочее место",
}

ARCHAIC_WATCHLIST = {
    "градоначальство",
    "губерния",
    "верста",
    "чело",
}

NOUN_FALSE_POSITIVE_T_SOFT = {
    "смерть",
    "память",
    "кровать",
    "нефть",
    "честь",
    "доблесть",
    "радость",
    "грусть",
    "скорость",
    "реальность",
    "возможность",
    "актуальность",
    "эффективность",
    "вечность",
    "верность",
    "преданность",
    "сложность",
    "трудность",
    "дальность",
    "плотность",
    "гуманность",
    "юность",
    "мать",
    "сеть",
    "мечеть",
    "ноготь",
    "коготь",
    "путь",
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
    text = MULTISPACE_RE.sub(" ", text)
    return text


def token_count(text: str) -> int:
    return len(TOKEN_RE.findall(text))


def has_cyrillic(text: str) -> bool:
    return bool(CYRILLIC_RE.search(text))


def has_latin(text: str) -> bool:
    return bool(LATIN_RE.search(text))


def translit_like_ru(lemma: str, gloss: str) -> bool:
    g = normalize_text(gloss)
    l = normalize_text(lemma)
    if g in TRANSLIT_EXACT:
        return True
    if len(g) >= 4 and len(l) >= 4:
        if g[0] == l[0] and abs(len(g) - len(l)) <= 2:
            overlap = sum(1 for ch in set(g) if ch in set(l))
            if overlap >= max(3, min(len(set(g)), len(set(l))) - 1):
                if any(bg in g for bg in BAD_BIGRAMS):
                    return True
    return False


def lemma_phonetic_copy(lemma: str, gloss: str) -> bool:
    l = normalize_text(lemma)
    g = normalize_text(gloss)
    if not l or not g:
        return False
    if g in TRANSLIT_EXACT:
        return True
    if abs(len(l) - len(g)) <= 2:
        shared = sum(1 for ch in l if ch in g)
        return shared >= max(3, int(len(l) * 0.6))
    return False


def detect_pos_mismatch(gloss: str, *, pos: str) -> list[str]:
    flags: list[str] = []
    g = normalize_text(gloss)
    if pos != "noun":
        return flags
    toks = TOKEN_RE.findall(g)
    if not toks:
        return flags
    if any(INF_RE.search(t) and t not in NOUN_FALSE_POSITIVE_T_SOFT for t in toks):
        flags.append("ru_gloss_verb_like")
    if len(toks) == 1 and ADJ_RE.search(toks[0]):
        flags.append("ru_gloss_adj_like")
    if len(toks) == 1 and len(toks[0]) >= 4 and ADV_RE.search(toks[0]) and toks[0] not in {"окно", "село"}:
        flags.append("ru_gloss_adv_like")
    return flags


def evaluate_ru_gloss(*, lemma: str, pos: str, gloss: str) -> RuleResult:
    flags: list[str] = []
    risk = 0
    g = normalize_text(gloss)
    tok_n = token_count(g)

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

    if not has_cyrillic(g) and not has_latin(g):
        flags.append("no_letters")
        risk += 100

    if tok_n >= 4 and g not in MULTIWORD_WHITELIST:
        flags.append("too_long_for_noun_gloss")
        risk += 30
    if tok_n >= 6 and g not in MULTIWORD_WHITELIST:
        risk += 100
    if tok_n >= 2 and g not in MULTIWORD_WHITELIST:
        flags.append("phrase_like_gloss")
        risk += 10
    if tok_n >= 3 and g not in MULTIWORD_WHITELIST:
        risk += 40

    if g in SUSPICIOUS_GENERIC:
        flags.append("generic_ai_gloss")
        risk += 60

    if g in ARCHAIC_WATCHLIST:
        flags.append("archaic_ru_gloss")
        risk += 20

    if translit_like_ru(lemma, g):
        flags.append("translit_like_ru")
        risk += 80

    if lemma_phonetic_copy(lemma, g):
        flags.append("lemma_phonetic_copy")
        risk += 50

    pos_flags = detect_pos_mismatch(g, pos=pos)

    weak_pos_flags = [f for f in pos_flags if f in {"ru_gloss_adj_like", "ru_gloss_adv_like"}]
    strong_pos_flags = [f for f in pos_flags if f == "ru_gloss_verb_like"]

    independent_bad_signals = {
        "generic_ai_gloss",
        "phrase_like_gloss",
        "latin_chars_in_ru_gloss",
        "english_leakage",
        "mixed_script",
        "lemma_phonetic_copy",
        "translit_like_ru",
        "too_long_for_noun_gloss",
    }

    for f in weak_pos_flags + strong_pos_flags:
        flags.append(f)

    pos_mismatch = False
    if strong_pos_flags:
        pos_mismatch = True
    elif weak_pos_flags and any(sig in flags for sig in independent_bad_signals):
        pos_mismatch = True

    if pos_mismatch:
        flags.append("pos_mismatch_candidate")
        risk += 25

    if "generic_ai_gloss" in flags and "pos_mismatch_candidate" in flags:
        flags.append("semantic_class_mismatch")
        risk += 60

    strong_reject = {
        "latin_chars_in_ru_gloss",
        "english_leakage",
        "mixed_script",
        "too_short",
        "semantic_class_mismatch",
    }

    reject = False
    if "translit_like_ru" in flags and "lemma_phonetic_copy" in flags:
        reject = True
    if any(f in strong_reject for f in flags):
        reject = True
    if tok_n >= 6 and g not in MULTIWORD_WHITELIST:
        reject = True

    if reject:
        status = "reject"
        action = "deactivate"
    elif risk >= 50 or "generic_ai_gloss" in flags or "archaic_ru_gloss" in flags or "pos_mismatch_candidate" in flags:
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
