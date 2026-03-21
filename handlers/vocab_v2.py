from __future__ import annotations

from services.vocab_runtime.handler_layer import handle_vocab_callback, handle_vocab_start


def _attach_e2e_runtime_native_payload(payload):
    if not isinstance(payload, dict):
        return payload

    out = dict(payload)
    native = out.get("runtime_native_payload")
    if not isinstance(native, dict):
        out.setdefault("e2e_runtime_native", False)
        out.setdefault("e2e_payload_kind", None)
        return out

    out["e2e_runtime_native"] = True
    out["e2e_payload_kind"] = native.get("kind")
    out.setdefault("runtime_branch", "cat")
    out.setdefault("cat_native", True)
    out.setdefault("visible_mode", "cat")
    out.setdefault("visible_semantics", "adaptive")
    return out


def _extract_cat_source(payload) -> str:
    if not isinstance(payload, dict):
        return "legacy"

    runtime_branch = str(payload.get("runtime_branch", "") or "").strip().lower()
    if runtime_branch == "cat":
        return "cat"
    if runtime_branch == "legacy":
        return "legacy"

    native = payload.get("runtime_native_payload")
    if isinstance(native, dict):
        kind = str(native.get("kind", "") or "").strip().lower()
        if kind in {"question", "result", "message"}:
            return "cat"

    cat_route = payload.get("cat_route")
    if cat_route is None:
        return "legacy"

    source = getattr(cat_route, "source", None)
    if source is None and isinstance(cat_route, dict):
        source = cat_route.get("source")

    return "cat" if source == "cat" else "legacy"


def _attach_runtime_branch(payload):
    if not isinstance(payload, dict):
        return payload

    out = dict(payload)
    out["runtime_branch"] = _extract_cat_source(payload)
    return out


def vocab_v2_start(*, conn, store, user_id: int) -> dict[str, object]:
    out = handle_vocab_start(conn=conn, user_id=user_id)
    store.set(user_id=user_id, fsm=out['fsm'])
    return _attach_e2e_runtime_native_payload(_attach_runtime_branch(out))


def vocab_v2_callback(*, conn, store, user_id: int, callback_data: str) -> dict[str, object]:
    fsm = store.get(user_id=user_id)

    if fsm is None:
        return {
            'ok': False,
            'error': 'fsm_not_found',
            'text': 'Session not found. Start again.',
            'keyboard': [],
            'finished': True,
            'runtime_branch': 'legacy',
        }

    out = handle_vocab_callback(conn=conn, fsm=fsm, callback_data=callback_data)

    if out['finished']:
        store.clear(user_id=user_id)
    else:
        store.set(user_id=user_id, fsm=out['fsm'])

    return _attach_e2e_runtime_native_payload(_attach_runtime_branch(out))
