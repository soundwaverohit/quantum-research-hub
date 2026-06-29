"""Optional Claude model pass utilities.

The deterministic pipeline is the default. This module is only used when
``QRH_ENABLE_MODEL_PASS=1`` and credentials are available, or when tests inject
a fake client. All model calls request JSON so callers can validate and merge
the result with deterministic artifacts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Protocol

from .config import get_config
from .logging_utils import get_logger

log = get_logger("model_pass")

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ModelPassError(RuntimeError):
    """Raised when a model pass is unavailable or returns invalid output."""


class JsonModelClient(Protocol):
    """Minimal protocol used by production and test model clients."""

    def complete_json(self, *, system: str, prompt: str, max_tokens: int) -> dict[str, Any]:
        """Return a parsed JSON object from a model response."""


def prompts_dir() -> Path:
    return Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str) -> str:
    path = prompts_dir() / name
    if not path.exists():
        raise ModelPassError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def render_prompt(name: str, payload: dict[str, Any]) -> str:
    return (
        load_prompt(name).rstrip()
        + "\n\nInput JSON:\n"
        + json.dumps(payload, indent=2, sort_keys=True, default=str)
    )


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from plain text or a fenced JSON response."""
    candidates = [text.strip()]
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fence:
        candidates.insert(0, fence.group(1).strip())

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])

    for candidate in candidates:
        if not candidate:
            continue
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {"items": value}
    raise ModelPassError("model response did not contain a JSON object")


class ClaudeJsonClient:
    """Small Anthropic Messages API client using the repo's existing httpx dependency."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        timeout: float = 60.0,
        api_url: str = ANTHROPIC_MESSAGES_URL,
    ) -> None:
        if not api_key:
            raise ModelPassError("ANTHROPIC_API_KEY or QRH_ANTHROPIC_API_KEY is required")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.api_url = api_url

    @classmethod
    def from_config(cls) -> "ClaudeJsonClient | None":
        cfg = get_config()
        if not cfg.enable_model_pass:
            return None
        if not cfg.anthropic_api_key:
            log.warning("QRH_ENABLE_MODEL_PASS=1 but no Anthropic API key is configured")
            return None
        return cls(
            api_key=cfg.anthropic_api_key,
            model=cfg.claude_model,
            timeout=cfg.claude_timeout_seconds,
        )

    def complete_json(self, *, system: str, prompt: str, max_tokens: int) -> dict[str, Any]:
        import httpx

        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }
        try:
            resp = httpx.post(self.api_url, headers=headers, json=body, timeout=self.timeout)
            resp.raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise ModelPassError(f"Claude request failed: {exc}") from exc

        data = resp.json()
        text_parts = []
        for part in data.get("content", []):
            if isinstance(part, dict) and part.get("type") == "text":
                text_parts.append(part.get("text", ""))
        text = "\n".join(text_parts).strip()
        if not text:
            raise ModelPassError("Claude response contained no text")
        return extract_json_object(text)


def get_model_client() -> JsonModelClient | None:
    return ClaudeJsonClient.from_config()


def complete_prompt_json(
    prompt_name: str,
    payload: dict[str, Any],
    *,
    system: str,
    max_tokens: int | None = None,
    client: JsonModelClient | None = None,
) -> dict[str, Any]:
    """Render a prompt and return parsed JSON from a model client."""
    cfg = get_config()
    active_client = client or get_model_client()
    if active_client is None:
        raise ModelPassError("model pass is disabled or unavailable")
    return active_client.complete_json(
        system=system,
        prompt=render_prompt(prompt_name, payload),
        max_tokens=max_tokens or cfg.claude_max_tokens,
    )
