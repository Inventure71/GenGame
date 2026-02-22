#!/usr/bin/env python3
"""
Safe network serialization helpers.

This module provides a restricted pickle loader for wire messages.
Only primitive builtins are allowed to avoid arbitrary code execution
through pickle globals during deserialization.
"""

from __future__ import annotations

import builtins
import io
import pickle
from typing import Any


class _RestrictedUnpickler(pickle.Unpickler):
    _ALLOWED_BUILTINS = {
        "NoneType",
        "bool",
        "int",
        "float",
        "str",
        "bytes",
        "bytearray",
        "list",
        "tuple",
        "dict",
        "set",
        "frozenset",
    }

    def find_class(self, module: str, name: str):
        if module == "builtins" and name in self._ALLOWED_BUILTINS:
            return getattr(builtins, name)
        raise pickle.UnpicklingError(f"Disallowed pickle global: {module}.{name}")


def safe_pickle_loads(data: bytes, max_bytes: int | None = None) -> Any:
    """
    Deserialize pickle bytes with strict class restrictions.

    Args:
        data: Serialized pickle payload.
        max_bytes: Optional max payload size guard.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("safe_pickle_loads expects bytes-like input")

    payload = bytes(data)
    if max_bytes is not None and len(payload) > max_bytes:
        raise ValueError(f"Payload too large: {len(payload)} > {max_bytes}")

    return _RestrictedUnpickler(io.BytesIO(payload)).load()
