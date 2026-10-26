"""Postgres access: schema, bulk load, and the two search queries.

Everything that touches the database lives here, so the ranking logic in
``retrieve.py`` stays testable as ranking rather than as SQL.

The one thing worth reading closely is that **the applicability gate is a SQL
predicate, not a post-filter**: ``part = ANY(%s)`` runs inside both searches,
so an out-of-scope regulation never enters the candidate set. At 464 rows that
trims noise; at 300 regulations it is the difference between an ANN search over
10^6 rows and one over 10^4.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import Settings, settings
from .corpus import Provision
from .embed import to_pgvector

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schema.sql"

#: Columns written by ingest, in COPY order.  Derived once and used to build
#: each row, so a column added here cannot silently shift the tuple.
COPY_COLUMNS = (
    "node_id",
    "citation",
    "section",
    "part",
    "regulation",
    "agency",
    "heading",
    "path",
    "depth",
    "kind",
    "own_text",
    "context_text",
    "url",
    "as_of",
    "embedding",
)


@dataclass
class Hit:
    node_id: str
    score: float


class Store:
    def __init__(self, cfg: Settings | None = None) -> None:
        self.cfg = cfg or settings()
        self.pool = ConnectionPool(
            self.cfg.database_url, min_size=1, max_size=4, kwargs={"row_factory": dict_row}
        )

    def close(self) -> None:
        self.pool.close()

    # ------------------------------------------------------------------
    # schema and ingest
    # ------------------------------------------------------------------

    def apply_schema(self) -> None:
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        if self.cfg.embed_dim != 384:
            sql = sql.replace("vector(384)", f"vector({self.cfg.embed_dim})")
        with self.pool.connection() as conn:
            conn.execute(sql)

    def count(self) -> int:
        with self.pool.connection() as conn:
            row = conn.execute("SELECT count(*) AS n FROM provision").fetchone()
        return int(row["n"]) if row else 0

    def replace_all(
        self, nodes: Sequence[Provision], vectors: Sequence[Sequence[float]]
    ) -> int:
        """Load the corpus, replacing whatever was there.

        Re-runnable by construction: one transaction, so a failed ingest leaves
        the previous corpus in place rather than half of a new one.
        """
        assert len(nodes) == len(vectors), "one vector per node"
        cols = ", ".join(COPY_COLUMNS)
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE provision")
                with cur.copy(f"COPY provision ({cols}) FROM STDIN") as copy:
                    for node, vec in zip(nodes, vectors):
                        copy.write_row(_row_for_copy(node, vec))
            conn.execute("ANALYZE provision")
        return len(nodes)

    # ------------------------------------------------------------------
    # reads
    # ------------------------------------------------------------------

    def corpus_meta(self) -> dict[str, Any]:
        """What the UI states as its scope, straight from the loaded rows."""
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT regulation, agency, part, count(*) AS nodes,
                       max(as_of) AS as_of
                  FROM provision
                 GROUP BY regulation, agency, part
                 ORDER BY part
                """
            ).fetchall()
        return {
            "regulations": [
                {
                    "regulation": r["regulation"],
                    "agency": r["agency"],
                    "part": r["part"],
                    "nodes": r["nodes"],
                    "as_of": r["as_of"].isoformat() if r["as_of"] else None,
                }
                for r in rows
            ]
        }

    def fetch(self, node_ids: Sequence[str]) -> list[dict[str, Any]]:
        if not node_ids:
            return []
        with self.pool.connection() as conn:
            return conn.execute(
                """
                SELECT node_id, citation, section, part, regulation, agency,
                       heading, path, depth, kind, own_text, context_text, url,
                       as_of
                  FROM provision
                 WHERE node_id = ANY(%s)
                """,
                (list(node_ids),),
            ).fetchall()

    def search_lexical(
        self, query: str, parts: Sequence[str], limit: int
    ) -> list[Hit]:
        """Full-text arm.  `parts` is the gate, applied inside the query."""
        if not query.strip() or not parts:
            return []
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT node_id, ts_rank_cd(tsv, q) AS score
                  FROM provision, websearch_to_tsquery('english', %s) AS q
                 WHERE part = ANY(%s) AND tsv @@ q
                 ORDER BY score DESC
                 LIMIT %s
                """,
                (query, list(parts), limit),
            ).fetchall()
        return [Hit(r["node_id"], float(r["score"])) for r in rows]

    def search_semantic(
        self, vector: Sequence[float], parts: Sequence[str], limit: int
    ) -> list[Hit]:
        """Vector arm.  Cosine distance, so lower is nearer; score inverts it."""
        if not parts:
            return []
        with self.pool.connection() as conn:
            rows = conn.execute(
                """
                SELECT node_id, embedding <=> %s::vector AS distance
                  FROM provision
                 WHERE part = ANY(%s)
                 ORDER BY distance
                 LIMIT %s
                """,
                (to_pgvector(vector), list(parts), limit),
            ).fetchall()
        return [Hit(r["node_id"], 1.0 - float(r["distance"])) for r in rows]


def _row_for_copy(node: Provision, vec: Sequence[float]) -> tuple[Any, ...]:
    """One COPY row, keyed by column name so order cannot drift."""
    values = {
        "node_id": node.id,
        "citation": node.citation,
        "section": node.section,
        "part": node.part,
        "regulation": node.regulation,
        "agency": node.agency,
        "heading": node.heading,
        "path": list(node.path),
        "depth": node.depth,
        "kind": node.kind,
        "own_text": node.own_text,
        "context_text": node.context_text,
        "url": node.url,
        "as_of": node.as_of,
        "embedding": to_pgvector(vec),
    }
    return tuple(values[c] for c in COPY_COLUMNS)


def wait_for_db(cfg: Settings, attempts: int = 30, delay: float = 1.0) -> None:
    """Block until Postgres accepts a connection, so boot order is not a race."""
    import time

    for attempt in range(attempts):
        try:
            with psycopg.connect(cfg.database_url, connect_timeout=3) as conn:
                conn.execute("SELECT 1")
            return
        except Exception:  # noqa: BLE001 -- any connection failure is a retry
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
