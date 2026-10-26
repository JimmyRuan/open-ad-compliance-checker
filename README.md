# Ad Compliance Check

Paste a social-media ad, pick the advertiser type, and get back the provisions
that may apply — each with a precise citation (`12 CFR 1026.24(d)(2)(iii)`), the
provision text, a one-line reason it applies, whether the ad appears to meet it,
and a link to its eCFR paragraph.

![The ad compliance check screen: ad text, advertiser type, channel, insurance
flags and reviewer context, with the corpus scope stated under the
form](app-demo.png)

- Design rationale, half a page: **[DECISIONS.md](DECISIONS.md)**
- Assumptions: **[ASSUMPTIONS.md](ASSUMPTIONS.md)**
- Output for all seven sample ads: **[outputs/ads.md](outputs/ads.md)**

---

## One command

```bash
make up
```

Then open **http://localhost:8088**.

**Docker and Make are the only requirements** — no host Python, no host Node, no
`psql`, no model download. The image carries the built UI, the API, the
regulation corpus and the embedding model, so the container downloads nothing at
runtime. Without Make: `docker compose up --build`.

First build takes a few minutes (it bakes a 90 MB ONNX embedder). First boot
parses and ingests the corpus, ~100 s, then the app is ready.

### It works with no API key

By default there is no `OPENAI_API_KEY` and **nothing leaves your machine**: you
get real citations, provision text, eCFR links and the gate's reasoning, all
from local retrieval. The brief makes the LLM optional, so this is a supported
mode, not a broken one.

To add generated verdicts — the met / not-met judgement, the reason and the
quoted evidence:

```bash
cp .env.example .env     # then paste a key
```

```dotenv
OPENAI_API_KEY=sk-proj-...
```

A check takes ~20 s with verdicts on (`LLM_ASSESS_EFFORT=minimal` is faster,
`high` is more careful); retrieval alone is under a second.

## Other commands

```bash
make test     # the test suite, in the same image
make ads      # regenerate outputs/ads.md for all seven ads
make logs     # tail the app logs
make clean    # delete the database volume (forces a fresh ingest)
```

## Try it

Pick **Load a sample ad**, or paste your own. Worth trying:

- **`a2`** — *"Free Checking… No strings attached!"* with an `$8 monthly
  maintenance fee` in the reviewer context. Nothing in the ad resembles
  `1030.8(a)(2)`, the provision it breaks; it is found because the `claims_free`
  flag contributes a query in the regulation's own words.
- **`a3`** — a credit union. Reg DD and Part 328 are **excluded by the gate**,
  and the result says which paragraph excluded them.
- **`a7`** — an APY ad whose one real gap may be exempt depending on whether a
  social post counts as "electronic media". The tool surfaces that fork as a
  caveat instead of picking a side.

## How it works

```
ingest     regulations.json → label tree → provision nodes → Postgres (tsvector + vector)
           app/labels.py  app/corpus.py  app/ingest.py  app/store.py

retrieve   applicability gate → multi-query hybrid search → RRF → collapse → 24 candidates
           app/applicability.py  app/retrieve.py

assess     one model call over all candidates → grounding checks → one screen
           app/llm.py  app/assess.py  app/main.py  web/
```

Retrieval is **entirely local** — Postgres plus an ONNX model in the image — so
the regulations never leave the machine and the single assess call is the only
outbound traffic in the system.

| File | |
|---|---|
| `app/labels.py` | label tokeniser + backtracking stack machine ← the hard part |
| `app/corpus.py` | sections → provision nodes (the unit of retrieval) |
| `app/applicability.py` | the gate; every rule cites its scope paragraph |
| `app/retrieve.py` | multi-query hybrid search, RRF, ancestor collapse |
| `app/llm.py` | the prompt, the strict schema, and the only `openai` import |
| `app/assess.py` | grounding enforced in code, and the degradation paths |
| `app/main.py` | `POST /api/check`, health, samples, and the built UI |

## Scope and limits

This tool is **advisory**. It surfaces provisions for a human reviewer and does
not assert a legal conclusion.

Scope is exactly the 25 sections in `data/regulations.json` (as of 2026-10-05),
and the UI says so on every result. Material gaps — NCUA Part 707, Reg Z
official interpretations, UDAAP, FTC Act §5 — are in
[ASSUMPTIONS.md](ASSUMPTIONS.md). Part 707's absence is why `a3` gets no
APY-disclosure finding; I did not invent a Reg DD hit for a credit union to make
the demo look better.

Measured retrieval recall is **10 of 12** expected provisions, reported as
measured rather than tuned until the table turned green.

## Troubleshooting

**Port already in use.** Set `PORT` in `.env`.

**Stale corpus after editing `data/regulations.json`.** `make clean && make up`.
