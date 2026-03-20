from __future__ import annotations

from dataclasses import dataclass
import re


CANNED_PATTERNS = [
    re.compile(r"\bважно отметить\b", re.I),
    re.compile(r"\bрекомендую\b", re.I),
    re.compile(r"\bв данном случае\b", re.I),
    re.compile(r"\bследует учитывать\b", re.I),
    re.compile(r"\bна самом деле\b", re.I),
    re.compile(r"\bв первую очередь\b", re.I),
    re.compile(r"\bобратитесь к специалисту\b", re.I),
]


RISK_HIGH_RE = re.compile(
    r"\b(кровь|сильная боль|температура|полиция|суд|адвокат|депортац|арест|срочно|urgent|urgente)\b",
    re.I,
)

QUESTION_RE = re.compile(r"\?\s*$")


@dataclass(slots=True)
class ThreadMessage:
    role: str
    text: str
    message_id: int | None = None
    user_id: int | None = None
    event_type: str | None = None


@dataclass(slots=True)
class ThreadSnapshot:
    post_log_id: int
    chat_id: int
    chat_key: str
    chat_type: str
    region: str | None
    thread_root_message_id: int | None
    topic: str | None
    format_type: str | None
    seed_text: str
    messages: list[ThreadMessage]
    followup_sent: bool
    replies_count: int
    unique_users_count: int
    prior_ai_plan_count: int


@dataclass(slots=True)
class CandidateReply:
    text: str
    naturalness: float
    usefulness: float
    non_salesiness: float
    brevity: float
    fit_to_thread: float
    human_like_score: float
    verbosity_score: float
    canned_pattern_score: float

    def as_dict(self) -> dict:
        return {
            "text": self.text,
            "naturalness": round(self.naturalness, 4),
            "usefulness": round(self.usefulness, 4),
            "non_salesiness": round(self.non_salesiness, 4),
            "brevity": round(self.brevity, 4),
            "fit_to_thread": round(self.fit_to_thread, 4),
            "human_like_score": round(self.human_like_score, 4),
            "verbosity_score": round(self.verbosity_score, 4),
            "canned_pattern_score": round(self.canned_pattern_score, 4),
        }


@dataclass(slots=True)
class PlanDecision:
    should_reply: bool
    reply_mode: str
    reason: str
    confidence: float
    risk_level: str
    product_bridge_allowed: bool
    human_like_score: float
    verbosity_score: float
    canned_pattern_score: float
    selected_reply_text: str | None
    candidates: list[CandidateReply]

    def as_dict(self) -> dict:
        return {
            "should_reply": self.should_reply,
            "reply_mode": self.reply_mode,
            "reason": self.reason,
            "confidence": round(self.confidence, 4),
            "risk_level": self.risk_level,
            "product_bridge_allowed": self.product_bridge_allowed,
            "human_like_score": round(self.human_like_score, 4),
            "verbosity_score": round(self.verbosity_score, 4),
            "canned_pattern_score": round(self.canned_pattern_score, 4),
            "selected_reply_text": self.selected_reply_text,
            "candidates": [c.as_dict() for c in self.candidates],
        }


def classify_risk(topic: str | None, last_user_text: str) -> str:
    if RISK_HIGH_RE.search(last_user_text or ""):
        return "high"
    if (topic or "").lower() in {"health", "documents", "financas", "work", "housing"}:
        return "medium"
    return "low"


def has_terminal_question(text: str) -> bool:
    return bool(QUESTION_RE.search((text or "").strip()))


def canned_pattern_score(text: str) -> float:
    if not text:
        return 1.0
    hits = sum(1 for rx in CANNED_PATTERNS if rx.search(text))
    return min(1.0, hits / 3.0)


def verbosity_score(text: str) -> float:
    size = len((text or "").strip())
    if size <= 0:
        return 1.0
    return min(1.0, size / 220.0)


def brevity_score(text: str) -> float:
    return max(0.0, 1.0 - verbosity_score(text))


def human_like_score(text: str) -> float:
    canned = canned_pattern_score(text)
    verbose = verbosity_score(text)
    question_bonus = 0.1 if "?" not in text else 0.0
    score = 1.0 - (0.55 * canned) - (0.35 * verbose) + question_bonus
    return max(0.0, min(1.0, score))


def base_fit_to_thread(topic: str | None, text: str) -> float:
    t = (topic or "").lower()
    s = (text or "").lower()
    topic_words = {
        "documents": ["док", "система", "запись", "формулиров"],
        "housing": ["хозяин", "арен", "квартир", "съём"],
        "services": ["мастер", "сервис", "прийти"],
        "transport": ["автобус", "поезд", "ub", "метро"],
        "health": ["centro de saúde", "врач", "запись"],
        "work": ["работ", "контракт", "hr"],
        "financas": ["finanças", "налог", "система"],
    }
    words = topic_words.get(t, [])
    if not words:
        return 0.65
    return 0.9 if any(w in s for w in words) else 0.55


def topic_candidate_texts(topic: str | None, wants_answer: bool) -> list[str]:
    t = (topic or "").lower()

    if t == "documents":
        base = [
            "Тут обычно затык не в самом документе, а в том, как это назвали в системе.",
            "Я бы тут сначала проверил формулировку, а не только сам файл.",
            "У них часто проблема не в бумаге, а в записи или категории.",
        ]
    elif t == "housing":
        base = [
            "Тут ещё зависит от хозяина, но по смыслу лучше писать коротко и без официоза.",
            "Я бы тут сказал проще и без лишней вежливой мишуры, так понятнее.",
            "Обычно лучше короткая бытовая формулировка, а не канцелярия.",
        ]
    elif t == "services":
        base = [
            "С мастерами тут обычно работает короткая и очень прямолинейная формулировка.",
            "Я бы это сказал проще, без длинного захода.",
            "Тут лучше по-человечески и в одну фразу, иначе они теряют нить.",
        ]
    elif t == "health":
        base = [
            "Тут лучше осторожно с формулировкой, особенно если вопрос уже не совсем бытовой.",
            "Я бы такое не писал слишком уверенно, потому что тут важны детали.",
            "Тут лучше сначала уточнить контекст, а потом уже формулировать ответ.",
        ]
    elif t == "financas":
        base = [
            "С Finanças подвох часто не в сути, а в названии шага или категории.",
            "Я бы тут перепроверил термин, потому что он легко уводит не туда.",
            "Тут обычно помогает не официальный перевод, а нормальная бытовая расшифровка.",
        ]
    elif t == "work":
        base = [
            "Тут ещё зависит от того, кто пишет, HR или сам начальник, оттенок там разный.",
            "Я бы тут выбрал более прямую и живую формулировку.",
            "По работе лучше писать проще, без слишком книжного португальского.",
        ]
    else:
        base = [
            "Тут ещё зависит от контекста, но я бы сказал это проще.",
            "Я бы тут убрал официоз и оставил живую бытовую формулировку.",
            "Тут лучше коротко и по-человечески, так естественнее звучит.",
        ]

    if wants_answer:
        return base + [
            "Скорее всего тут сработает короткий бытовой вариант, без тяжёлых конструкций.",
            "Я бы тут смотрел не на словарь, а на то, как это реально говорят.",
        ]
    return base


def choose_reply_mode(risk_level: str, wants_answer: bool) -> str:
    if risk_level == "high":
        return "R3"
    if wants_answer:
        return "R2"
    return "R1"
