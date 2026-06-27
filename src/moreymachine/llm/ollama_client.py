"""Minimal Ollama client with deterministic fallback behavior."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from moreymachine.utils.paths import MANUAL_DATA_DIR

LLM_CONFIG_PATH = MANUAL_DATA_DIR / "llm_config.yml"


@dataclass(frozen=True)
class OllamaConfig:
    """Runtime config for optional Ollama summaries."""

    enabled: bool = False
    model: str = "llama3.1"
    base_url: str = "http://localhost:11434"
    timeout_seconds: int = 45
    max_tokens: int = 700
    temperature: float = 0.2
    cache_enabled: bool = True


class OllamaUnavailableError(RuntimeError):
    """Raised when Ollama cannot provide a response."""


def load_ollama_config(path: str | Path = LLM_CONFIG_PATH) -> OllamaConfig:
    """Load Ollama config from YAML, defaulting to disabled."""
    file_path = Path(path)
    if not file_path.exists():
        return OllamaConfig()
    payload = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return OllamaConfig(
        enabled=bool(payload.get("enabled", False)),
        model=str(payload.get("model", "llama3.1")),
        base_url=str(payload.get("base_url", "http://localhost:11434")).rstrip("/"),
        timeout_seconds=int(payload.get("timeout_seconds", 45)),
        max_tokens=int(payload.get("max_tokens", 700)),
        temperature=float(payload.get("temperature", 0.2)),
        cache_enabled=bool(payload.get("cache_enabled", True)),
    )


def summarize_with_ollama(prompt: str, config: OllamaConfig) -> str:
    """Call Ollama's generate endpoint and return text."""
    if not config.enabled:
        raise OllamaUnavailableError("Ollama is disabled in llm_config.yml.")
    request = urllib.request.Request(
        f"{config.base_url}/api/generate",
        data=json.dumps(
            {
                "model": config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.temperature,
                    "num_predict": config.max_tokens,
                },
            }
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise OllamaUnavailableError(str(exc)) from exc
    text = str(payload.get("response") or "").strip()
    if not text:
        raise OllamaUnavailableError("Ollama returned an empty response.")
    return text

