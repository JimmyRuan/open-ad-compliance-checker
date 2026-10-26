"""Ingest: ``regulations.json`` -> provision nodes -> Postgres.

Re-runnable, which the brief requires because the corpus is meant to change
weekly: it parses, embeds and replaces the whole corpus in one transaction, so
running it twice leaves exactly the state of running it once and a failure
leaves the previous corpus intact.

Replacing wholesale is the right call at 464 nodes and the wrong one at 300
regulations -- see DECISIONS.md for what changes.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .config import Settings, settings
from .corpus import build_nodes, load_corpus
from .embed import get_embedder
from .store import Store

log = logging.getLogger(__name__)


@dataclass
class IngestResult:
    nodes: int
    warnings: list[str]
    duration_ms: int

    def as_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "warnings": self.warnings,
            "duration_ms": self.duration_ms,
        }


def ingest(store: Store, cfg: Settings | None = None) -> IngestResult:
    cfg = cfg or settings()
    started = time.perf_counter()

    corpus = load_corpus(cfg.data_dir / "regulations.json")
    nodes, warnings = build_nodes(corpus)
    log.info("parsed %d provision nodes (%d warnings)", len(nodes), len(warnings))
    for warning in warnings:
        log.warning("corpus: %s", warning)

    embedder = get_embedder(cfg)
    vectors = embedder.encode([n.context_text for n in nodes])

    store.apply_schema()
    written = store.replace_all(nodes, vectors)

    duration_ms = int((time.perf_counter() - started) * 1000)
    log.info("ingested %d nodes in %d ms", written, duration_ms)
    return IngestResult(nodes=written, warnings=warnings, duration_ms=duration_ms)


def ingest_if_empty(store: Store, cfg: Settings | None = None) -> IngestResult | None:
    """Load on first boot so ``one command`` really is one command."""
    store.apply_schema()
    if store.count() > 0:
        log.info("provision store already populated; skipping ingest")
        return None
    return ingest(store, cfg)
