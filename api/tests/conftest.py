"""Shared fixtures.

Two rules the suite holds to:

* **No test touches the network.** No API key is set, so ``check`` takes the
  retrieval-only path, and the embedder is the deterministic hash backend.
* **No test needs Postgres.** The database-shaped tests were cut with the rest
  of the non-MVP scope; what is left covers the parser, the gate and the
  grounding validator, which are the parts where a bug is invisible.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DATA_DIR", REPO.parent / "data"))


@pytest.fixture(autouse=True)
def _offline_env(monkeypatch):
    """Every test starts from an offline configuration."""
    # Cleared, not just unset: a developer with a real key in their shell must
    # not be able to turn the suite into a billable, network-touching run.
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("EMBED_BACKEND", "hash")
    monkeypatch.setenv("DATA_DIR", str(DATA))
    from app import config, embed

    config.reset_settings()
    embed.reset_embedder_cache()
    yield
    config.reset_settings()
    embed.reset_embedder_cache()


@pytest.fixture(scope="session")
def regulations() -> dict:
    return json.loads((DATA / "regulations.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def sections(regulations) -> dict[str, dict]:
    return {s["section"]: s for s in regulations["sections"]}


@pytest.fixture(scope="session")
def ads() -> list[dict]:
    return json.loads((DATA / "ads.json").read_text(encoding="utf-8"))["ads"]
