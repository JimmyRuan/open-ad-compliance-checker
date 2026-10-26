"""Run every sample ad and write ``outputs/ads.md`` -- a required deliverable.

    make ads

Works in both modes. With no ``OPENAI_API_KEY`` it writes the retrieval-only
report: citations, provision text, eCFR links and the gate's reasoning. With a
key it adds the verdict, the reason and the quoted evidence. The report states
which mode produced it, so the output is never ambiguous about what it is.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.assess import CheckResult, check
from app.config import settings
from app.corpus import load_ads
from app.ingest import ingest_if_empty
from app.store import Store, wait_for_db

OUT = Path("/srv/outputs") if Path("/srv/outputs").exists() else Path("outputs")

VERDICT_HEADING = {
    "violates": "May violate",
    "unclear": "Unclear — needs a reviewer",
    "meets": "Appears met",
    "not_applicable": "Considered and ruled out",
}


def render(results: list[tuple[dict, CheckResult]], elapsed: float, cfg) -> str:
    mode = "verdicts" if cfg.llm_enabled else "retrieval-only"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Ad compliance check — all seven sample ads",
        "",
        f"Generated {stamp} · mode: **{mode}**"
        + (f" · model `{cfg.model}`" if cfg.llm_enabled else ""),
        "",
    ]
    if not cfg.llm_enabled:
        lines += [
            "> Produced with no `OPENAI_API_KEY`, so **no ad text left the machine**.",
            "> Every citation, provision text and link below comes from local",
            "> retrieval. Set a key to add generated verdicts.",
            "",
        ]
    lines += [
        "This output is **advisory**: it surfaces provisions for a human reviewer",
        "and does not assert a legal conclusion. Scope is exactly the 25 sections",
        "in `data/regulations.json`.",
        "",
        "---",
        "",
    ]

    for ad, result in results:
        adv = ad["advertiser"]
        lines += [
            f"## `{ad['id']}` — {adv['name']} ({adv['type']}, {ad['channel']})",
            "",
            f"> {ad['text']}",
            "",
        ]
        if ad.get("context"):
            lines += [f"*Reviewer context:* {ad['context']}", ""]
        lines += [
            f"**Regulations searched:** {', '.join(result.retrieval.gate.parts)}  ",
            f"**Topic flags:** {', '.join(k for k, v in result.profile.flags.items() if v) or 'none'}  ",
            f"**Candidates retrieved:** {len(result.retrieval.candidates)}",
            "",
        ]
        if result.retrieval.gate.excluded:
            lines += ["**Excluded by the gate:**", ""]
            lines += [f"- {e}" for e in result.retrieval.gate.excluded]
            lines += [""]
        for notice in result.notices:
            lines += [f"> {notice}", ""]
        if result.overall_note:
            lines += [f"**Overall:** {result.overall_note}", ""]

        shown = [f for f in result.findings if f.verdict != "not_applicable"] or result.findings
        for f in shown[:12]:
            head = VERDICT_HEADING.get(f.verdict, f.verdict)
            lines.append(f"### {head} — [{f.citation}]({f.url})")
            lines.append("")
            lines.append(f"*{f.regulation}, {f.agency} — {f.heading}*")
            lines.append("")
            if f.reason:
                lines += [f.reason, ""]
            if f.ad_evidence:
                lines += [f'Evidence from the ad: “{f.ad_evidence}”', ""]
            if f.caveat:
                lines += [f"Caveat: {f.caveat}", ""]
            lines += [f"> {f.provision_text[:600]}", ""]
        if result.dropped:
            lines += ["**Dropped as ungrounded:**", ""]
            lines += [f"- {d.get('citation', '-')}: {d['reason']}" for d in result.dropped]
            lines += [""]
        lines += ["---", ""]

    lines += [f"_Total wall clock: {elapsed:.1f}s for {len(results)} ads._", ""]
    return "\n".join(lines)


def main() -> int:
    cfg = settings()
    wait_for_db(cfg)
    store = Store(cfg)
    ingest_if_empty(store, cfg)

    ads = load_ads(cfg.data_dir / "ads.json")
    started = time.perf_counter()
    results: list[tuple[dict, CheckResult]] = []
    for ad in ads:
        print(f"  {ad['id']}…", end="", flush=True)
        result = check(
            store,
            ad_text=ad["text"],
            advertiser=ad["advertiser"],
            channel=ad["channel"],
            context=ad.get("context", ""),
            cfg=cfg,
        )
        counts: dict[str, int] = {}
        for f in result.findings:
            counts[f.verdict] = counts.get(f.verdict, 0) + 1
        print(f" {result.mode}: " + ", ".join(f"{v}={n}" for v, n in sorted(counts.items())))
        results.append((ad, result))
    elapsed = time.perf_counter() - started

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "ads.md"
    out.write_text(render(results, elapsed, cfg), encoding="utf-8")
    print(f"\nwrote {out} ({out.stat().st_size:,} bytes) in {elapsed:.1f}s")
    store.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
