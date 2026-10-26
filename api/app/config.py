"""Configuration, read once from the environment.

Deliberately plain: a frozen dataclass and ``os.environ``, readable top to
bottom without knowing a settings framework.

The LLM is optional. With no ``OPENAI_API_KEY`` the app runs retrieval-only --
real citations, provision text and eCFR links, no generated judgement -- which
is also the mode the test suite and a fresh clone run in.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    database_url: str
    data_dir: Path
    openai_api_key: str
    model: str
    assess_effort: str
    embed_backend: str
    embed_model: str
    embed_dim: int
    candidate_limit: int
    own_text_chars: int

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    return Settings(
        database_url=os.environ.get(
            "DATABASE_URL", "postgresql://adcheck:adcheck@db:5432/adcheck"
        ),
        data_dir=Path(os.environ.get("DATA_DIR", str(REPO_ROOT / "data"))),
        openai_api_key=os.environ.get("OPENAI_API_KEY", "").strip(),
        # A reasoning model: the request sends `reasoning.effort` and strict
        # structured outputs, which the older chat models reject.
        model=os.environ.get("LLM_MODEL", "gpt-5"),
        # Reasoning tokens dominate latency (~3x the visible output), so this
        # is the latency control: minimal ~21s, low ~35s, high ~95s per check.
        assess_effort=os.environ.get("LLM_ASSESS_EFFORT", "low"),
        # 'hash' is a deterministic offline stand-in so tests never load the
        # 90 MB ONNX model; 'fastembed' is what runs.
        embed_backend=os.environ.get("EMBED_BACKEND", "fastembed").strip().lower(),
        embed_model=os.environ.get("EMBED_MODEL", "BAAI/bge-small-en-v1.5"),
        embed_dim=_int("EMBED_DIM", 384),
        # 24 rather than 20: an APY ad needs the whole 1030.8(c) disclosure
        # checklist (six co-equal items) plus the rate rule plus the FDIC
        # statement, and 20 slots cut that list short.
        candidate_limit=_int("CANDIDATE_LIMIT", 24),
        own_text_chars=_int("OWN_TEXT_CHARS", 1_200),
    )


_SETTINGS: Settings | None = None


def settings() -> Settings:
    global _SETTINGS
    if _SETTINGS is None:
        _SETTINGS = load_settings()
    return _SETTINGS


def reset_settings() -> None:
    """Drop the cache so a test can re-read a patched environment."""
    global _SETTINGS
    _SETTINGS = None
