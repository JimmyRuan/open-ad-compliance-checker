"""FastAPI surface: ``POST /api/check``, plus health, samples, and the UI.

Deliberately small. The interesting decisions are in ``labels.py``,
``applicability.py``, ``retrieve.py`` and ``assess.py``; this module wires them
together, owns process lifecycle and first-boot ingest, and serves the built
single-page app so the whole thing is one container behind one port.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import assess as assess_mod
from .config import settings
from .corpus import load_ads
from .ingest import ingest_if_empty
from .llm import LLMClient
from .store import Store, wait_for_db

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
)
log = logging.getLogger(__name__)

#: Where the Vite build lands in the image. Absent in a local dev run, in which
#: case the API still serves and the UI is run by Vite.
STATIC_DIR = Path("/srv/static")

STATE: dict[str, Any] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = settings()
    wait_for_db(cfg)
    store = Store(cfg)
    STATE["store"] = store
    STATE["cfg"] = cfg
    # First boot loads the corpus, so "one command" really is one command.
    result = ingest_if_empty(store, cfg)
    STATE["ingest"] = result.as_dict() if result else None
    STATE["client"] = LLMClient(cfg) if cfg.llm_enabled else None
    log.info(
        "ready: %d provisions, verdicts %s",
        store.count(),
        "enabled" if cfg.llm_enabled else "disabled (no OPENAI_API_KEY)",
    )
    yield
    store.close()


app = FastAPI(title="Ad Compliance Check", lifespan=lifespan)


class Advertiser(BaseModel):
    name: str = ""
    type: str = "unknown"
    fdic_insured: bool = False
    ncua_insured: bool = False


class CheckRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    advertiser: Advertiser = Advertiser()
    channel: str = ""
    context: str = Field(default="", max_length=20_000)
    use_llm: bool = True
    """The reviewer's switch. False keeps the check entirely local."""


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Row count, scope and mode -- what the UI states on every result."""
    store: Store = STATE["store"]
    cfg = STATE["cfg"]
    return {
        "status": "ok",
        "provisions": store.count(),
        "verdicts_enabled": cfg.llm_enabled,
        "model": cfg.model if cfg.llm_enabled else None,
        "ingest": STATE.get("ingest"),
        **store.corpus_meta(),
    }


@app.get("/api/samples")
def samples() -> list[dict[str, Any]]:
    """The seven sample ads, so the UI can load one without copy-paste."""
    cfg = STATE["cfg"]
    return load_ads(cfg.data_dir / "ads.json")


@app.post("/api/check")
def check(req: CheckRequest) -> dict[str, Any]:
    try:
        result = assess_mod.check(
            STATE["store"],
            ad_text=req.text,
            advertiser=req.advertiser.model_dump(),
            channel=req.channel,
            context=req.context,
            use_llm=req.use_llm,
            cfg=STATE["cfg"],
            client=STATE.get("client"),
        )
    except Exception as exc:  # noqa: BLE001
        # The call demo pastes in unseen ads; a stack trace on screen is not an
        # acceptable answer, a 500 with a message is.
        log.exception("check failed")
        raise HTTPException(status_code=500, detail=f"check failed: {type(exc).__name__}") from exc
    return result.as_dict()


# --------------------------------------------------------------------------
# the single page, served from the same origin as the API so there is no CORS
# configuration and no second container
# --------------------------------------------------------------------------

if STATIC_DIR.is_dir():
    app.mount(
        "/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets"
    )

    @app.get("/")
    def index() -> FileResponse:
        # The shell must never be cached. Asset filenames are content-hashed,
        # so a cached index.html points at a bundle the next build deleted --
        # a returning browser then gets a blank page until someone thinks to
        # hard-reload. The assets themselves are immutable and cache freely.
        return FileResponse(
            STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"}
        )
