from __future__ import annotations

import threading
from typing import Any, Callable

_runtime = threading.local()
_fallback_lock = threading.Lock()
_fallback_context: dict[str, Any] = {}
_fallback_cancel_checker: Callable[[], bool] | None = None


def set_run_context(**kwargs: Any) -> None:
    context = dict(kwargs)
    _runtime.context = context
    with _fallback_lock:
        _fallback_context.clear()
        _fallback_context.update(context)


def get_run_context() -> dict[str, Any]:
    context = getattr(_runtime, "context", None)
    if context:
        return context
    with _fallback_lock:
        return dict(_fallback_context)


def get_context_value(key: str, default: Any = None) -> Any:
    return get_run_context().get(key, default)


def set_cancel_checker(checker: Callable[[], bool] | None) -> None:
    _runtime.cancel_checker = checker
    global _fallback_cancel_checker
    with _fallback_lock:
        _fallback_cancel_checker = checker


def is_cancel_requested() -> bool:
    checker = getattr(_runtime, "cancel_checker", None)
    if not checker:
        with _fallback_lock:
            checker = _fallback_cancel_checker
    if not checker:
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def raise_if_cancelled() -> None:
    if is_cancel_requested():
        raise InterruptedError("Agent stopped by user")
