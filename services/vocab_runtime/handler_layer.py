from __future__ import annotations

from services.vocab_runtime.entrypoints import run_vocab_callback, run_vocab_start


def _handle_vocab_start_base(*, conn, user_id: int) -> dict[str, object]:
    out = run_vocab_start(conn=conn, user_id=user_id)
    return {
        'ok': True,
        'fsm': out['fsm'],
        'text': out['text'],
        'keyboard': out['keyboard'],
        'finished': bool(out.get('finished', False)),
    }


def _handle_vocab_callback_base(*, conn, fsm, callback_data: str) -> dict[str, object]:
    out = run_vocab_callback(conn=conn, fsm=fsm, callback_data=callback_data)

    finished = bool(out.get('finished', False))
    return {
        'ok': True,
        'fsm': out['fsm'],
        'text': out['text'],
        'keyboard': out.get('keyboard', []),
        'answer_result': out.get('answer_result'),
        'finished': finished,
    }
# ===== CAT layer 27: handler_layer native payload contract =====

def _detect_cat_payload_kind_from_handler(out: dict[str, object]) -> str | None:
    branch = "cat" if str(out.get("runtime_branch", "legacy")) == "cat" else "legacy"
    if branch != "cat":
        return None
    if bool(out.get("finished")):
        return "result"
    if out.get("keyboard"):
        return "question"
    return "message"


def _attach_cat_native_payload_from_handler(out):
    if not isinstance(out, dict):
        return out

    branch = "cat" if str(out.get("runtime_branch", "legacy")) == "cat" else "legacy"
    payload_kind = _detect_cat_payload_kind_from_handler(out)

    rendered = dict(out)
    rendered["runtime_branch"] = branch
    rendered["cat_payload_kind"] = payload_kind
    rendered["cat_native"] = branch == "cat"

    if branch == "cat":
        rendered.setdefault("visible_mode", "cat")
        rendered.setdefault("visible_semantics", "adaptive")
    else:
        rendered.setdefault("visible_mode", "legacy")
        rendered.setdefault("visible_semantics", "static")

    return rendered


def handle_vocab_start(*, conn, user_id: int):
    out = _handle_vocab_start_base(conn=conn, user_id=user_id)
    return _attach_cat_native_payload_from_handler(out)


def handle_vocab_callback(*, conn, fsm, callback_data: str):
    out = _handle_vocab_callback_base(conn=conn, fsm=fsm, callback_data=callback_data)
    return _attach_cat_native_payload_from_handler(out)
