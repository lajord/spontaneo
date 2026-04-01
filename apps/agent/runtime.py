from __future__ import annotations

import threading
from typing import Any, Callable

_runtime = threading.local()


def set_run_context(**kwargs: Any) -> None:
    _runtime.context = dict(kwargs)


def get_run_context() -> dict[str, Any]:
    return getattr(_runtime, "context", {})


def get_context_value(key: str, default: Any = None) -> Any:
    return get_run_context().get(key, default)


def set_cancel_checker(checker: Callable[[], bool] | None) -> None:
    _runtime.cancel_checker = checker


def is_cancel_requested() -> bool:
    checker = getattr(_runtime, "cancel_checker", None)
    if not checker:
        return False
    try:
        return bool(checker())
    except Exception:
        return False


def raise_if_cancelled() -> None:
    if is_cancel_requested():
        raise InterruptedError("Agent stopped by user")
