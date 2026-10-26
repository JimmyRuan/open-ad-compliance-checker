"""Local embeddings.  No hosted embedding API, by design.

Retrieval runs entirely on this machine: Postgres plus an ONNX model baked into
the image at build time.  That is a privacy property, not an implementation
detail -- it means the regulations never egress, query text never egress, and
the whole hosted-embedding attack surface is simply absent.  The only outbound
request the system can make is the one assess call in ``llm.py``.

Two backends:

``fastembed``
    ``BAAI/bge-small-en-v1.5``, 384-dim, ONNX, ~90 MB.  No API key, no torch in
    the image, and the full corpus embeds in seconds.

``hash``
    A deterministic hashed-trigram stand-in.  The unit suite uses it so tests
    stay fast and offline, and it is the fallback if the model is missing from
    the image.  Retrieval quality is poor -- it is a test double, not a tier.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
from typing import Protocol, Sequence

from .config import Settings, settings

log = logging.getLogger(__name__)

_WORD_RE = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    dim: int
    name: str

    def encode(self, texts: Sequence[str]) -> list[list[float]]: ...


class HashEmbedder:
    """Deterministic bag-of-features hash embedding.

    Word unigrams and character 4-grams hashed into ``dim`` buckets with signed
    counts, L2-normalised.  Good enough for exact-ish lexical overlap, which is
    all a test needs; nowhere near good enough for the product.
    """

    name = "hash"

    def __init__(self, dim: int = 384) -> None:
        self.dim = dim

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._one(t) for t in texts]

    def _one(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        low = text.lower()
        tokens = _WORD_RE.findall(low)
        grams = [low[i : i + 4] for i in range(0, max(0, len(low) - 3))]
        for feat in tokens + grams:
            h = hashlib.blake2b(feat.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "big") % self.dim
            sign = 1.0 if h[4] & 1 else -1.0
            vec[idx] += sign
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]


class FastEmbedEmbedder:
    """``fastembed`` wrapper.  Normalised output, so cosine == dot product."""

    name = "fastembed"

    def __init__(self, model: str, dim: int) -> None:
        from fastembed import TextEmbedding  # imported lazily: ~1 s and 90 MB

        self._model = TextEmbedding(model_name=model)
        self.dim = dim
        self._model_name = model

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        out = [list(map(float, v)) for v in self._model.embed(list(texts), batch_size=256)]
        bad = [len(v) for v in out if len(v) != self.dim]
        if bad:
            raise RuntimeError(
                f"{self._model_name} returned {bad[0]}-dim vectors but EMBED_DIM={self.dim}; "
                "set EMBED_DIM to match and re-ingest"
            )
        return out


_CACHE: dict[str, Embedder] = {}


def get_embedder(cfg: Settings | None = None) -> Embedder:
    """The configured embedder, built once per process.

    Falls back to ``HashEmbedder`` with a loud warning if fastembed or its
    weights are unavailable, so a misbuilt image degrades to a working-but-bad
    demo instead of a crash loop on startup.
    """
    cfg = cfg or settings()
    key = f"{cfg.embed_backend}:{cfg.embed_model}:{cfg.embed_dim}"
    if key in _CACHE:
        return _CACHE[key]

    if cfg.embed_backend == "hash":
        emb: Embedder = HashEmbedder(cfg.embed_dim)
    else:
        try:
            emb = FastEmbedEmbedder(cfg.embed_model, cfg.embed_dim)
        except Exception as exc:  # pragma: no cover - exercised only on a bad image
            log.warning(
                "fastembed unavailable (%s); falling back to the hash embedder. "
                "Retrieval quality will be poor -- check that the model was baked "
                "into the image at build time.",
                exc,
            )
            emb = HashEmbedder(cfg.embed_dim)

    _CACHE[key] = emb
    return emb


def reset_embedder_cache() -> None:
    _CACHE.clear()


def to_pgvector(vec: Sequence[float]) -> str:
    """pgvector's text input form, e.g. ``[0.1,-0.2,...]``.

    Passed as a parameter and cast server-side; floats only, so there is
    nothing here to inject.
    """
    return "[" + ",".join(f"{v:.6g}" for v in vec) + "]"
