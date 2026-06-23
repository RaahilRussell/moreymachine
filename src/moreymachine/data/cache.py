"""JSON file cache for raw NBA API responses."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from moreymachine.utils.paths import NBA_API_RAW_DIR

JsonMapping = Mapping[str, Any]


class JsonFileCache:
    """Persist endpoint responses as deterministic JSON files."""

    def __init__(self, base_dir: str | Path = NBA_API_RAW_DIR) -> None:
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get(self, endpoint_name: str, params: JsonMapping) -> dict[str, Any] | None:
        """Return a cached payload for an endpoint call if one exists."""
        path = self.path_for(endpoint_name, params)
        if not path.exists():
            return None

        with path.open("r", encoding="utf-8") as file:
            cached = json.load(file)
        return cached["payload"]

    def set(
        self,
        endpoint_name: str,
        params: JsonMapping,
        payload: JsonMapping,
    ) -> Path:
        """Write a raw endpoint payload to the cache and return its path."""
        path = self.path_for(endpoint_name, params)
        path.parent.mkdir(parents=True, exist_ok=True)
        cache_record = {
            "endpoint": endpoint_name,
            "params": dict(params),
            "fetched_at_utc": datetime.now(UTC).isoformat(),
            "payload": payload,
        }

        tmp_path = path.with_suffix(".tmp")
        with tmp_path.open("w", encoding="utf-8") as file:
            json.dump(cache_record, file, indent=2, sort_keys=True)
        tmp_path.replace(path)
        return path

    def path_for(self, endpoint_name: str, params: JsonMapping) -> Path:
        """Return the deterministic cache path for an endpoint call."""
        endpoint_slug = _slugify(endpoint_name)
        season_slug = _slugify(str(params.get("season", "all")))
        digest = _params_digest(params)
        return self.base_dir / endpoint_slug / f"{season_slug}_{digest}.json"


def _params_digest(params: JsonMapping) -> str:
    encoded = json.dumps(dict(params), sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def _slugify(value: str) -> str:
    return "".join(char.lower() if char.isalnum() else "_" for char in value).strip("_")
