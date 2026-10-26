"""Multi-query hybrid retrieval over the in-scope provisions.

Three ideas, in the order they matter.

**The gate runs first** (``applicability.py``), as a SQL predicate inside the
search rather than a filter after it, so an out-of-scope regulation never
enters the candidate set.

**Multi-query expansion.** The ad's own words are a poor query for the
provision it breaks. Ad ``a2`` is *"Open Example Bank Free Checking today. No
strings attached!"* and the provision it violates is ``1030.8(a)(2)``: *"refer
to or describe an account as 'free' or 'no cost' ... if any maintenance or
activity fee may be imposed"*. Nothing in the ad lexically resembles that, and
"no strings attached" is not semantically close to it either. So each active
topic flag contributes a short, regulation-shaped query written in the
*regulation's* vocabulary. Without this, recall on ``a2`` is poor.

**Fuse, then collapse.** Every (query x arm) ranking is fused with reciprocal
rank fusion, and then any ancestor retrieved alongside its own descendant is
dropped in favour of the deeper node -- because the citation the reviewer needs
is the leaf, and showing both ``(d)`` and ``(d)(1)(iii)`` as separate findings
is noise.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from .applicability import AdProfile, GateResult, gate
from .config import Settings, settings
from .embed import get_embedder
from .store import Store

log = logging.getLogger(__name__)

#: RRF constant from the original paper.  Used instead of normalising the two
#: arms' scores, because ``ts_rank_cd`` and cosine similarity are not on
#: comparable scales and any blend of raw scores needs a calibration step that
#: would have to be re-tuned per corpus.  Rank order is what survives.
RRF_K = 60


@dataclass
class Expansion:
    """One expansion query, in two forms -- the arms want different input.

    The semantic arm wants fluent, regulation-shaped prose: the embedder scores
    whole-meaning similarity, and a full sentence in the regulation's own
    register is what matches a provision the ad's words never touch.

    The lexical arm wants **short defined terms**, and getting this wrong was a
    real bug in the build. ``websearch_to_tsquery`` ANDs its terms, so feeding
    it the long prose form required every one of ~25 words to co-occur in a
    single provision -- the whole lexical arm returned *one* row for an entire
    gated part, silently reducing the hybrid search to a semantic-only search.
    So the lexical form is a short ``or``-joined set of the exact defined terms
    the corpus turns on: "annual percentage yield", "Member FDIC".
    """

    semantic: str
    lexical: str
    targets: str
    """Provisions this expansion exists to reach, for the record."""


#: One expansion per topic flag.  This table is the single highest-leverage
#: recall lever in the system.
FLAG_QUERIES: dict[str, Expansion] = {
    "states_payment_amount": Expansion(
        semantic="advertisement states the amount of a payment, a triggering term "
        "requiring additional disclosures including downpayment, terms of repayment "
        "and the annual percentage rate",
        lexical='"triggering terms" or "amount of any payment" or "terms of repayment" '
        'or "additional disclosures" or downpayment',
        targets="1026.24(d), 1026.16(b)",
    ),
    "states_credit_terms": Expansion(
        semantic="advertisement states specific credit terms that the creditor will "
        "actually arrange or offer, and a rate of finance charge stated as an annual "
        "percentage rate",
        lexical='"rate of finance charge" or "annual percentage rate" or '
        '"actually available" or "simple annual rate"',
        targets="1026.24(a), 1026.24(c), 1026.24(f)",
    ),
    "states_rate_of_return": Expansion(
        semantic="advertisement states a rate of return and must state it as an "
        "annual percentage yield using that term",
        lexical='"rate of return" or "annual percentage yield" or "permissible rates"',
        targets="1030.8(b)",
    ),
    "states_apy": Expansion(
        semantic="when the annual percentage yield is stated the advertisement shall "
        "also state variable rate, the time the annual percentage yield is offered, "
        "minimum balance, minimum opening deposit, the effect of fees and features of "
        "time accounts",
        lexical='"annual percentage yield" or "minimum balance" or "minimum opening '
        'deposit" or "effect of fees" or "variable rates" or "time accounts"',
        targets="1030.8(c)",
    ),
    "claims_free": Expansion(
        semantic="advertisement refers to or describes an account as free or no cost "
        "when a maintenance or activity fee may be imposed on the account",
        lexical='free or "no cost" or "maintenance or activity fee" or misleading',
        targets="1030.8(a)(2)",
    ),
    "is_mortgage": Expansion(
        semantic="material misrepresentation in a commercial communication about the "
        "interest rate, terms or amounts payable of a mortgage credit product, and "
        "disclosure of rates and payments in advertisements for credit secured by a "
        "dwelling",
        lexical='"mortgage credit product" or "commercial communication" or '
        '"material misrepresentation" or "secured by a dwelling"',
        targets="1014.3, 1026.24(f)",
    ),
    "is_deposit_product": Expansion(
        semantic="advertisement of a deposit account, its annual percentage yield, "
        "minimum balance and the maturity of a time account",
        lexical='"deposit account" or "time account" or "annual percentage yield" '
        'or maturity',
        targets="1030.8",
    ),
    "is_credit_product": Expansion(
        semantic="advertisement for consumer credit stating credit terms that are "
        "actually available, and prohibited acts or practices in advertisements for "
        "credit",
        lexical='"consumer credit" or "advertisement for credit" or "prohibited acts" '
        'or creditor',
        targets="1026.24",
    ),
    "has_insurance_statement": Expansion(
        semantic="the official advertising statement Member FDIC or federally insured "
        "by NCUA required in advertisements, and the advertisements that need not "
        "include it",
        lexical='"Member FDIC" or "official advertising statement" or '
        '"federally insured by NCUA" or "insured by NCUA"',
        targets="328.6, 740.5",
    ),
    "names_institution": Expansion(
        semantic="advertisement setting forth the name of the insured institution and "
        "the official advertising statement requirement",
        lexical='"official advertising statement" or "name of the insured" or '
        '"insured depository institution"',
        targets="328.6(c), 740.5(a)",
    ),
    "mentions_overdraft": Expansion(
        semantic="advertising disclosures for overdraft services including the fees "
        "imposed, the categories of transactions covered and the consumer's right to "
        "opt out",
        lexical='overdraft or "overdraft service" or "opt out"',
        targets="1030.11(b)",
    ),
    "mentions_applicant_class": Expansion(
        semantic="a creditor shall not make any oral or written statement to "
        "applicants or prospective applicants that would discourage on a prohibited "
        "basis a reasonable person from making or pursuing an application",
        lexical='discourage or "prohibited basis" or "prospective applicants" or '
        '"reasonable person"',
        targets="1002.4(b)",
    ),
}

#: Always asked, regardless of flags: the accuracy and misleading-advertising
#: catch-alls that apply to essentially every submission.
BASE_QUERIES: tuple[Expansion, ...] = (
    Expansion(
        semantic="an advertisement shall not be misleading or inaccurate and shall "
        "not misrepresent the institution's deposit contract or its advertising",
        lexical='misleading or inaccurate or misrepresent or deceptive or accuracy',
        targets="1030.8(a)(1), 740.2, 1014.3",
    ),
)

#: Dropped when turning free ad text into an ``or``-joined lexical query.  Short
#: and deliberately generic -- Postgres's own stemming and stop-word handling do
#: the rest; this list only removes words so common they add no ranking signal.
_LEXICAL_STOPWORDS = frozenset(
    """a an and are as at be but by for from has have in into is it its of on or
    our out so than that the their them then there these they this to too was
    were will with you your today any all can now get""".split()
)

_TERM_RE = re.compile(r"[A-Za-z][A-Za-z'’%-]{2,}|\d+(?:\.\d+)?%")


def to_lexical_query(text: str, max_terms: int = 14) -> str:
    """Turn free text into an ``or``-joined tsquery.

    ``websearch_to_tsquery`` ANDs bare terms, so passing raw ad copy asks
    Postgres for a provision containing *every* word of the ad -- which for
    ad ``a1`` ("Drive off in a new SUV for only $349/month! ...") is no
    provision at all.  Joining with ``or`` restores BM25-style behaviour, where
    ``ts_rank_cd`` does the discriminating instead of the matcher.
    """
    terms: list[str] = []
    for match in _TERM_RE.findall(text):
        term = match.lower().strip("'’-")
        if len(term) < 3 or term in _LEXICAL_STOPWORDS or term in terms:
            continue
        terms.append(term)
        if len(terms) >= max_terms:
            break
    return " or ".join(terms)


@dataclass
class Candidate:
    """One provision offered to the assess step, with its provenance."""

    ref: str
    """Stable handle (``C1``..``Cn``) the model echoes back, so validation is exact."""

    node_id: str
    citation: str
    section: str
    regulation: str
    agency: str
    heading: str
    kind: str
    path: tuple[str, ...]
    own_text: str
    ancestor_context: str
    url: str
    as_of: str
    score: float
    why_retrieved: tuple[str, ...]
    """Which queries found it -- what makes the cut-off auditable."""

    def for_prompt(self, own_text_chars: int) -> dict[str, Any]:
        return {
            "ref": self.ref,
            "citation": self.citation,
            "regulation": self.regulation,
            "heading": self.heading,
            "kind": self.kind,
            "own_text": _truncate(self.own_text, own_text_chars),
            "ancestor_context": _truncate(self.ancestor_context, own_text_chars),
        }


@dataclass
class Retrieval:
    candidates: list[Candidate]
    gate: GateResult
    queries: list[Expansion] = field(default_factory=list)
    collapsed: list[str] = field(default_factory=list)
    """Citations dropped because a descendant of theirs was also retrieved."""


def build_queries(ad_text: str, profile: AdProfile, context: str = "") -> list[Expansion]:
    """The ad, plus the base catch-alls, plus one query per active topic flag."""
    out: list[Expansion] = []
    primary = ad_text.strip()
    if context.strip():
        # The reviewer's context carries facts the ad omits, and those facts are
        # often what makes a provision apply -- ad a2's "$8 monthly maintenance
        # fee" is the whole reason 1030.8(a)(2) fires.
        primary = f"{primary}\n{context.strip()}"
    if primary:
        out.append(
            Expansion(
                semantic=primary,
                lexical=to_lexical_query(primary),
                targets="the submission itself",
            )
        )
    out.extend(BASE_QUERIES)
    out.extend(e for flag, e in FLAG_QUERIES.items() if profile.flag(flag))

    seen: set[str] = set()
    deduped: list[Expansion] = []
    for e in out:
        if e.semantic not in seen:
            seen.add(e.semantic)
            deduped.append(e)
    return deduped


def retrieve(
    store: Store,
    ad_text: str,
    profile: AdProfile,
    *,
    context: str = "",
    cfg: Settings | None = None,
) -> Retrieval:
    """Gate, search every query both ways, fuse, collapse, cap."""
    cfg = cfg or settings()
    gate_result = gate(profile)
    if not gate_result.parts:
        return Retrieval(candidates=[], gate=gate_result)

    queries = build_queries(ad_text, profile, context)
    embedder = get_embedder(cfg)
    vectors = embedder.encode([q.semantic for q in queries])

    # Per-arm depth. Wider than the final cut so fusion has something to fuse:
    # a provision ranked 30th by one arm and 3rd by another should survive.
    per_arm = max(cfg.candidate_limit, 20)

    rankings: list[tuple[str, list[str]]] = []
    for query, vector in zip(queries, vectors):
        label = query.targets
        lexical = store.search_lexical(query.lexical, gate_result.parts, per_arm)
        semantic = store.search_semantic(vector, gate_result.parts, per_arm)
        rankings.append((f"{label}:lexical", [h.node_id for h in lexical]))
        rankings.append((f"{label}:semantic", [h.node_id for h in semantic]))

    fused = _fuse(rankings)
    if not fused:
        return Retrieval(candidates=[], gate=gate_result, queries=queries)

    rows = {r["node_id"]: r for r in store.fetch([n for n, _, _ in fused])}
    kept, collapsed = _collapse(fused, rows)
    kept = kept[: cfg.candidate_limit]

    candidates = [
        Candidate(
            ref=f"C{i + 1}",
            node_id=node_id,
            citation=rows[node_id]["citation"],
            section=rows[node_id]["section"],
            regulation=rows[node_id]["regulation"],
            agency=rows[node_id]["agency"],
            heading=rows[node_id]["heading"],
            kind=rows[node_id]["kind"],
            path=tuple(rows[node_id]["path"]),
            own_text=rows[node_id]["own_text"],
            ancestor_context=_ancestor_context(rows[node_id]["context_text"]),
            url=rows[node_id]["url"],
            as_of=str(rows[node_id]["as_of"]),
            score=score,
            why_retrieved=why,
        )
        for i, (node_id, score, why) in enumerate(kept)
    ]
    log.info(
        "retrieved %d candidates from %d queries over parts %s",
        len(candidates),
        len(queries),
        ",".join(gate_result.parts),
    )
    return Retrieval(
        candidates=candidates,
        gate=gate_result,
        queries=queries,
        collapsed=collapsed,
    )


def _fuse(rankings: list[tuple[str, list[str]]]) -> list[tuple[str, float, tuple[str, ...]]]:
    """Reciprocal rank fusion: ``score(d) = sum over lists of 1 / (k + rank)``.

    Pure and order-sensitive, so it is kept as one readable function rather
    than threaded through the search loop.
    """
    scores: dict[str, float] = {}
    why: dict[str, list[str]] = {}
    for label, node_ids in rankings:
        for rank, node_id in enumerate(node_ids, start=1):
            scores[node_id] = scores.get(node_id, 0.0) + 1.0 / (RRF_K + rank)
            why.setdefault(node_id, []).append(label)
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
    return [(node_id, score, tuple(why[node_id])) for node_id, score in ordered]


def _collapse(
    fused: list[tuple[str, float, tuple[str, ...]]], rows: dict[str, dict]
) -> tuple[list[tuple[str, float, tuple[str, ...]]], list[str]]:
    """Drop any provision whose own descendant was also retrieved.

    The reviewer needs the deepest citation that applies; showing ``(d)`` next
    to ``(d)(1)(iii)`` as two findings is noise, and the parent's text is
    already carried as ``ancestor_context`` on the child.
    """
    paths = {
        node_id: (rows[node_id]["section"], tuple(rows[node_id]["path"]))
        for node_id, _, _ in fused
        if node_id in rows
    }
    kept: list[tuple[str, float, tuple[str, ...]]] = []
    collapsed: list[str] = []
    for node_id, score, why in fused:
        if node_id not in rows:
            continue
        section, path = paths[node_id]
        has_descendant = any(
            other != node_id
            and other_section == section
            and len(other_path) > len(path)
            and other_path[: len(path)] == path
            for other, (other_section, other_path) in paths.items()
        )
        if has_descendant:
            collapsed.append(rows[node_id]["citation"])
        else:
            kept.append((node_id, score, why))
    return kept, collapsed


def _ancestor_context(context_text: str) -> str:
    """The ancestor intro chain, which is everything before the node's own text.

    ``context_text`` is built by ``corpus.py`` as heading + ancestor intros +
    own text + subtree; the reviewer-facing half of that is the ancestor chain,
    and it is what makes a leaf citation readable on screen.
    """
    return context_text.strip()


def _truncate(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "\u2026"
