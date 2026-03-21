from __future__ import annotations

from services.vocab_runtime.entrypoints import run_vocab_callback, run_vocab_start


def _handle_vocab_start_base(*, conn, user_id: int) -> dict[str, object]:
    out = run_vocab_start(conn=conn, user_id=user_id)
    return {
        "ok": True,
        "text": out["text"],
        "keyboard": out["keyboard"],
        "fsm": out["fsm"],
        "finished": False,
        **({k: v for k, v in out.items() if k not in {"text", "keyboard", "fsm"}}),
    }


def _handle_vocab_callback_base(*, conn, fsm, callback_data: str) -> dict[str, object]:
    out = run_vocab_callback(conn=conn, fsm=fsm, callback_data=callback_data)
    finished = bool(out.get("finished", False))
    return {
        "ok": bool(out.get("ok", True)),
        "text": out["text"],
        "keyboard": out["keyboard"],
        "fsm": out.get("fsm"),
        "answer_result": out.get("answer_result"),
        "finished": finished,
        **({k: v for k, v in out.items() if k not in {"ok", "text", "keyboard", "fsm", "answer_result", "finished"}}),
    }


def _runtime_payload_to_handler_fields(payload) -> dict[str, object]:
    if payload is None:
        return {
            "runtime_branch": "legacy",
            "cat_payload_kind": None,
            "cat_native": False,
            "visible_mode": "legacy",
            "visible_semantics": "static",
            "runtime_native_payload": None,
        }

    kind = str(getattr(payload, "kind", "") or "")
    mode = str(getattr(payload, "mode", "") or "vocab")
    session_id = str(getattr(payload, "session_id", "") or "")
    status = str(getattr(payload, "status", "") or "")
    theta = getattr(payload, "theta", None)
    se = getattr(payload, "se", None)
    item_id = getattr(payload, "item_id", None)
    prompt_text = getattr(payload, "prompt_text", None)
    answer_key = getattr(payload, "answer_key", None)
    stop_reason = getattr(payload, "stop_reason", None)
    payload_version = str(getattr(payload, "payload_version", "") or "cat_runtime_payload_v1")

    return {
        "runtime_branch": "cat",
        "cat_payload_kind": kind or None,
        "cat_native": True,
        "visible_mode": "cat",
        "visible_semantics": "adaptive",
        "runtime_native_payload": {
            "kind": kind,
            "mode": mode,
            "session_id": session_id,
            "status": status,
            "theta": theta,
            "se": se,
            "item_id": item_id,
            "prompt_text": prompt_text,
            "answer_key": answer_key,
            "stop_reason": stop_reason,
            "payload_version": payload_version,
        },
    }


def _attach_cat_native_payload_from_handler(out):
    if not isinstance(out, dict):
        return out

    payload = out.get("payload")
    if payload is not None:
        rendered = dict(out)
        rendered.update(_runtime_payload_to_handler_fields(payload))
        return rendered

    branch = "cat" if str(out.get("runtime_branch", "legacy")) == "cat" else "legacy"

    payload_kind = out.get("cat_payload_kind")
    if payload_kind is None and branch == "cat":
        if bool(out.get("finished")):
            payload_kind = "result"
        elif out.get("keyboard"):
            payload_kind = "question"
        else:
            payload_kind = "message"

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

    rendered.setdefault("runtime_native_payload", None)
    return rendered


def handle_vocab_start(*, conn, user_id: int):
    out = _handle_vocab_start_base(conn=conn, user_id=user_id)
    return _attach_cat_native_payload_from_handler(out)


def handle_vocab_callback(*, conn, fsm, callback_data: str):
    out = _handle_vocab_callback_base(conn=conn, fsm=fsm, callback_data=callback_data)
    return _attach_cat_native_payload_from_handler(out)
