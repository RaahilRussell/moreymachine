"""Small JSON cache for narrative responses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def cache_key(payload: Any) -> str:
    """Return a stable cache key for a JSON-serializable payload."""
    raw = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_cache(path: str | Path) -> dict[str, Any]:
    """Read a JSON cache file."""
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def write_cache(path: str | Path, cache: dict[str, Any]) -> None:
    """Write a JSON cache file."""
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")

