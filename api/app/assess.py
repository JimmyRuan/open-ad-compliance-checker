"""Retrieve, assess, validate -- the layer that decides what reaches the screen.

Grounding is enforced **here, in code**, not merely requested in the prompt.
Two checks, each of which drops a finding:

1. **the ref must be one we supplied** -- the model echoes back a candidate
   handle (``C7``), so matching is exact rather than string-matching a citation
   that could be fabricated;
2. **the citation must agree with that ref** -- catches an invented or
   transposed citation attached to a real handle.

That doubles as the prompt-injection defence, because ad copy is
attacker-controllable text flowing into a prompt. Even a fully successful
injection cannot produce a citation that was not in the candidate list, or a
verdict outside the enum (the schema closes it).

The degradation path matters as much as the happy path: with no API key, a
refusal, a provider error or malformed JSON, this module still returns ranked
provisions with citations, text and links, and says why there are no verdicts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .applicability import AdProfile, keyword_flags, profile_from_advertiser
from .config import Settings, settings
from .llm import VERDICTS, LLMClient, user_turn
from .retrieve import Candidate, Retrieval, retrieve
from .store import Store

log = logging.getLogger(__name__)

#: Shown in this order. A reviewer needs the problems at the top and needs to
#: see what was considered and dismissed at the bottom -- that is what makes
#: the cut-off auditable instead of a black box.
VERDICT_ORDER = {"violates": 0, "unclear": 1, "meets": 2, "not_applicable": 3}

#: Kinds that are context rather than findings, so a definition never reads as
#: an accusation.
CONTEXT_KINDS = ("definition", "scope")


@dataclass
class Finding:
    ref: str
    citation: str
    regulation: str
    agency: str
    heading: str
    kind: str
    url: str
    as_of: str
    provision_text: str
    ancestor_context: str
    applies: bool = False
    verdict: str = "not_applicable"
    reason: str = ""
    ad_evidence: str = ""
    caveat: str = ""
    retrieval_score: float = 0.0
    why_retrieved: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "citation": self.citation,
            "regulation": self.regulation,
            "agency": self.agency,
            "heading": self.heading,
            "kind": self.kind,
            "url": self.url,
            "as_of": self.as_of,
            "provision_text": self.provision_text,
            "ancestor_context": self.ancestor_context,
            "applies": self.applies,
            "verdict": self.verdict,
            "reason": self.reason,
            "ad_evidence": self.ad_evidence,
            "caveat": self.caveat,
            "is_supporting_context": self.kind in CONTEXT_KINDS,
            "retrieval_score": round(self.retrieval_score, 5),
            "why_retrieved": list(self.why_retrieved),
        }


@dataclass
class CheckResult:
    findings: list[Finding]
    retrieval: Retrieval
    profile: AdProfile
    mode: str
    """``verdicts`` or ``retrieval_only``."""

    notices: list[str] = field(default_factory=list)
    overall_note: str = ""
    dropped: list[dict[str, str]] = field(default_factory=list)
    """Findings the validator refused, with the reason -- surfaced, not hidden."""

    def as_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "findings": [f.as_dict() for f in self.findings],
            "overall_note": self.overall_note,
            "notices": self.notices,
            "dropped_findings": self.dropped,
            "gate": {
                "parts_in_scope": self.retrieval.gate.parts,
                "included": self.retrieval.gate.included,
                "excluded": self.retrieval.gate.excluded,
                "failed_open": self.retrieval.gate.failed_open,
            },
            "topic_flags": {k: v for k, v in self.profile.flags.items() if v},
            "candidate_count": len(self.retrieval.candidates),
            "collapsed_ancestors": self.retrieval.collapsed,
        }


def check(
    store: Store,
    *,
    ad_text: str,
    advertiser: dict[str, Any],
    channel: str = "",
    context: str = "",
    use_llm: bool = True,
    cfg: Settings | None = None,
    client: LLMClient | None = None,
) -> CheckResult:
    """Run the whole pipeline for one submission.

    The retrieval-only result is assembled *first*, so every failure path below
    has something real to return.

    ``use_llm=False`` is the reviewer's own switch, checked here rather than in
    the caller so there is exactly one place that decides whether anything
    leaves the machine. A key makes verdicts *available*; this makes them
    *wanted*, and both have to be true.
    """
    cfg = cfg or settings()
    notices: list[str] = []

    # 1. Profile, from keywords. No model call: the gate must behave the same
    #    way with or without an API key, and ad a2's "$8 fee" lives in the
    #    reviewer context either way.
    profile = profile_from_advertiser(
        advertiser, channel=channel, flags=keyword_flags(ad_text, context)
    )

    # 2. Retrieve -- entirely local: Postgres plus the ONNX embedder.
    retrieval = retrieve(store, ad_text, profile, context=context, cfg=cfg)
    findings = [_finding_from_candidate(c) for c in retrieval.candidates]

    if not retrieval.candidates:
        return CheckResult(
            findings=[],
            retrieval=retrieval,
            profile=profile,
            mode="retrieval_only",
            notices=["No provisions in the corpus matched this submission."],
        )

    # 3. Assess, if a key is configured *and* the reviewer asked for it. One
    #    call for every candidate.
    mode = "retrieval_only"
    overall_note = ""
    dropped: list[dict[str, str]] = []

    if not use_llm:
        notices.append(
            "Verdicts are switched off for this check, so no ad text left this "
            "machine. Citations, provision text and links come from local "
            "retrieval."
        )
    elif not cfg.llm_enabled:
        notices.append(
            "No OPENAI_API_KEY is set, so no ad text leaves this machine. "
            "Citations, provision text and links come from local retrieval."
        )
    else:
        client = client or LLMClient(cfg)
        meta = store.corpus_meta()
        regulations = [r["regulation"] for r in meta["regulations"]]
        as_of = max((r["as_of"] or "" for r in meta["regulations"]), default="")
        request = client.build_request(
            user_turn(
                ad_text,
                advertiser,
                channel,
                context,
                [c.for_prompt(cfg.own_text_chars) for c in retrieval.candidates],
                as_of,
                regulations,
            )
        )
        result = client.send(request)
        if result.note:
            notices.append(result.note)
        if result.refusal:
            notices.append(result.refusal)
        elif result.error:
            notices.append(f"{result.error}; showing retrieval-only results.")
        elif result.parsed is not None:
            findings, dropped, overall_note = _apply_findings(findings, result.parsed)
            mode = "verdicts"

    findings.sort(
        key=lambda f: (
            VERDICT_ORDER.get(f.verdict, 9),
            f.kind in CONTEXT_KINDS,
            -f.retrieval_score,
        )
    )
    return CheckResult(
        findings=findings,
        retrieval=retrieval,
        profile=profile,
        mode=mode,
        notices=notices,
        overall_note=overall_note,
        dropped=dropped,
    )


#: Everything that is punctuation or prefix rather than identity.
_CITE_NOISE = re.compile(r"(?:12\s*c\.?f\.?r\.?|§|sec(?:tion)?\.?)|[^a-z0-9]")


def _same_citation(claimed: str, candidate: str) -> bool:
    """Whether two citation strings name the same provision.

    Compared on identity rather than formatting, because the model writes the
    same paragraph several ways -- ``§ 328.6(c)(1)``, ``328.6(c)(1)``,
    ``12 C.F.R. 328.6(c)(1)``. Exact string equality turned a cosmetic
    difference into a dropped finding, and because the model is consistent
    within a response it dropped *every* finding at once, which on screen is
    indistinguishable from "the tool found nothing".

    This does not weaken the check. The citation shown to the reviewer is
    always the candidate's own string from the store, never the model's; this
    only decides whether the model attached a cite to the right handle, and a
    genuinely different paragraph still differs after normalisation.
    """
    return _CITE_NOISE.sub("", claimed.lower()) == _CITE_NOISE.sub("", candidate.lower())


def _finding_from_candidate(c: Candidate) -> Finding:
    return Finding(
        ref=c.ref,
        citation=c.citation,
        regulation=c.regulation,
        agency=c.agency,
        heading=c.heading,
        kind=c.kind,
        url=c.url,
        as_of=c.as_of,
        provision_text=c.own_text,
        ancestor_context=c.ancestor_context,
        retrieval_score=c.score,
        why_retrieved=c.why_retrieved,
    )


def _apply_findings(
    findings: list[Finding], parsed: dict[str, Any]
) -> tuple[list[Finding], list[dict[str, str]], str]:
    """Merge validated model output onto the retrieval-only findings.

    Every rejection is recorded and returned, because a silently dropped
    finding is indistinguishable from a provision the model never considered,
    and the reviewer needs to tell those apart.
    """
    by_ref = {f.ref: f for f in findings}
    raw = parsed.get("findings")
    if not isinstance(raw, list):
        return findings, [{"ref": "-", "reason": "no findings array in the response"}], ""

    dropped: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            dropped.append({"ref": "-", "reason": "finding was not an object"})
            continue

        ref = str(item.get("ref", "")).strip()
        citation = str(item.get("citation", "")).strip()

        # Check 1: the ref must be one we supplied.
        target = by_ref.get(ref)
        if target is None:
            dropped.append(
                {
                    "ref": ref or "-",
                    "citation": citation,
                    "reason": "cites a provision that was not in the candidate list "
                    "supplied to the model",
                }
            )
            continue

        # Check 2: the citation must agree with the ref it was attached to.
        if citation and not _same_citation(citation, target.citation):
            dropped.append(
                {
                    "ref": ref,
                    "citation": citation,
                    "reason": f"cited {citation!r} against candidate {ref}, "
                    f"which is {target.citation!r}",
                }
            )
            continue

        verdict = str(item.get("verdict", "not_applicable"))
        if verdict not in VERDICTS:
            # The schema closes this enum, so reaching here means it was not
            # honoured; demote rather than trust it.
            verdict = "unclear"

        target.applies = bool(item.get("applies"))
        target.verdict = verdict
        target.reason = str(item.get("reason") or "").strip()
        target.ad_evidence = str(item.get("ad_evidence") or "").strip()
        target.caveat = str(item.get("caveat") or "").strip()

    if dropped:
        log.warning("dropped %d ungrounded findings", len(dropped))
    return findings, dropped, str(parsed.get("overall_note") or "").strip()
