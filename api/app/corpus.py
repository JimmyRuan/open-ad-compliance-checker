"""Turn ``data/regulations.json`` into provision nodes.

This is the "unit of retrieval" decision made concrete.  A **provision node**
is one labeled paragraph at its deepest label, carrying:

- ``citation`` / ``path`` -- the leaf, because that is the precision a reviewer
  needs to act on;
- ``own_text`` -- what the reviewer reads on screen;
- ``context_text`` -- what gets indexed and embedded: regulation, section
  heading, the whole ancestor intro chain, the node's own text, and (for
  non-leaf nodes) its subtree.

The split between the last two is the point.  ``1026.24(d)(2)(iii)`` reads, on
its own, *"The 'annual percentage rate,' using that term, and, if the rate may
be increased after consummation..."* -- which is meaningless without ``(d)(2)``
above it and unretrievable by any query a reviewer would write.  Embedding the
ancestor chain makes it findable; keeping the citation at the leaf makes it
actionable.  Citation precision lives at the leaf, meaning lives in the chain.

Rolling the subtree into a non-leaf node's ``context_text`` is how a block like
the whole of ``(d)`` stays retrievable when the answer is the block rather than
any one leaf.  It replaces the separate "rollup node" in the design proposal --
same retrieval behaviour, but without two rows sharing one citation, which
would have made citation validation in ``assess.py`` ambiguous.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Iterable, Sequence

from . import labels

# --------------------------------------------------------------------------
# provision kinds
# --------------------------------------------------------------------------

#: How a provision functions, inferred from heading and text cues.  Used to
#: rank candidates and -- more visibly -- to keep definitions and scope text
#: out of the findings list on screen, where they would read as accusations
#: rather than as the supporting context they are.
KINDS = ("obligation", "prohibition", "definition", "scope", "exemption")

#: ``"the term "`` is deliberately **absent**. It was meant to catch *"The term
#: 'promotional rate' means..."*, but ``" means "`` already does that, and the
#: looser form misfired on ``1030.8(b)`` -- *"it shall state the rate as an
#: 'annual percentage yield' using that term... provided the term 'annual
#: percentage yield' is stated at least once"* -- tagging the rate-disclosure
#: obligation as a definition, which would have rendered it on screen as
#: muted supporting context rather than as a requirement.
_DEFINITION_CUES = (
    "definitions.",
    "definition.",
    " means ",
    " means:",
    "has the same meaning",
    "for purposes of this part",
)
_SCOPE_CUES = (
    "scope.",
    "coverage.",
    "authority.",
    "purpose.",
    "purpose and scope",
    "applies to",
    "this part applies",
    "effect on state laws",
    "relationship to",
)
#: Cues that a provision *is* a carve-out.
#:
#: "except as provided in paragraph (e)" is deliberately **absent**. It is a
#: cross-reference *to* an exemption, not an exemption, and including it was a
#: real bug: ``1030.8(c)`` opens *"When additional disclosures are required.
#: Except as provided in paragraph (e) of this section, if the annual
#: percentage yield is stated..."* -- the core APY disclosure obligation. With
#: that cue in the list, ``(c)`` and every child inheriting its ancestry were
#: tagged `exemption` and then down-weighted in ranking, which is the exact
#: opposite of the intent.
_EXEMPTION_CUES = (
    "exemption",
    "exempt",
    "need not include",
    "need not contain",
    "do not apply",
    "does not apply",
    "are not required",
    "is not required",
    "excluded.",
)
_PROHIBITION_CUES = (
    "shall not",
    "may not",
    "must not",
    "no insured",
    "prohibited acts",
    "it is a violation",
    "misleading",
    "may use no",
    "unlawful",
)


#: How far into a paragraph to look for a kind cue.  Paragraphs open with an
#: italic heading ("Certain media."), so the cue that identifies the kind can
#: sit a clause or two in: ``1030.8(e)(1)`` reads *"Certain media. If an
#: advertisement is made through one of the following media, it need not
#: contain the information in..."* and the operative "need not contain" lands
#: past the first 90 characters.
_CUE_WINDOW = 200


def classify(heading: str, text: str, ancestry: str = "") -> str:
    """Best-effort provision kind.

    ``ancestry`` is the ancestor-intro chain, and passing it matters: the
    heading that marks ``1030.8(e)(1)`` as a carve-out is on its *parent*
    (*"(e) Exemption for certain advertisements"*), not on the paragraph
    itself. Classifying a leaf without its chain mislabels every item inside
    an exemption block as an obligation -- which then ranks carve-outs as
    though they were requirements.

    Order matters too: exemptions and definitions are checked before
    prohibitions, because an exemption usually quotes the obligation it carves
    out of and would otherwise be counted as that obligation.
    """
    blob = f"{heading}\n{ancestry}\n{text}".lower()
    head = f"{ancestry}\n{text}".lower()[:_CUE_WINDOW]
    if any(c in head for c in _EXEMPTION_CUES) or "exemption for" in blob:
        return "exemption"
    if any(c in head for c in _DEFINITION_CUES) or " means " in blob[:300]:
        return "definition"
    if any(c in head for c in _SCOPE_CUES):
        return "scope"
    if any(c in blob for c in _PROHIBITION_CUES):
        return "prohibition"
    return "obligation"


# --------------------------------------------------------------------------
# nodes
# --------------------------------------------------------------------------


@dataclass
class Provision:
    """One row of the ``provision`` table."""

    id: str
    citation: str
    section: str
    part: str
    part_title: str
    regulation: str
    agency: str
    heading: str
    path: tuple[str, ...]
    depth: int
    kind: str
    own_text: str
    context_text: str
    url: str
    as_of: date
    labeled: bool = True

    @property
    def content_sha(self) -> bytes:
        """Hash of everything a change would have to re-embed.

        Scoped to the text that feeds ``context_text`` rather than to the whole
        row, so a metadata-only edit does not trigger a pointless re-embed.
        See ``ingest.py`` for how the weekly path uses it.
        """
        h = hashlib.sha256()
        h.update(self.citation.encode())
        h.update(b"\0")
        h.update(self.own_text.encode())
        h.update(b"\0")
        h.update(self.context_text.encode())
        return h.digest()


@dataclass
class SectionDoc:
    """A section as published, plus the parse warnings it produced."""

    id: str
    citation: str
    section: str
    part: str
    part_title: str
    regulation: str
    agency: str
    heading: str
    url: str
    paragraphs: list[str]
    warnings: list[str] = field(default_factory=list)


@dataclass
class Corpus:
    as_of: date
    source: str
    sections: list[SectionDoc]

    @property
    def regulations(self) -> list[str]:
        out: list[str] = []
        for s in self.sections:
            if s.regulation not in out:
                out.append(s.regulation)
        return out


def load_corpus(path: Path) -> Corpus:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return Corpus(
        as_of=date.fromisoformat(raw["as_of"]),
        source=raw.get("source", ""),
        sections=[
            SectionDoc(
                id=s["id"],
                citation=s["citation"],
                section=s["section"],
                part=s["part"],
                part_title=s.get("part_title", ""),
                regulation=s["regulation"],
                agency=s["agency"],
                heading=s["heading"],
                url=s["url"],
                paragraphs=list(s["paragraphs"]),
            )
            for s in raw["sections"]
        ],
    )


def load_ads(path: Path) -> list[dict]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return list(raw["ads"])


# --------------------------------------------------------------------------
# section -> nodes
# --------------------------------------------------------------------------

#: Caps on indexed text.  The ancestor chain is never truncated -- it is what
#: carries meaning -- only the subtree rollup and the node's own body are.
_SUBTREE_CHARS_TOP = 2_000
_SUBTREE_CHARS_DEEP = 1_200
_WS_RE = re.compile(r"\s+")


def _squash(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    # Prefer a sentence boundary so a truncated provision still reads.
    dot = cut.rfind(". ")
    if dot > limit * 0.6:
        return cut[: dot + 1] + " [...]"
    return cut.rstrip() + " [...]"


def build_section_nodes(doc: SectionDoc, as_of: date) -> tuple[list[Provision], list[str]]:
    """Provision nodes for one section, plus parse warnings."""
    parse = labels.parse_paragraphs(doc.paragraphs, doc.section)

    # own_text per path, in document order.  A path can be declared twice: once
    # inline by a descendant paragraph (the italic heading) and once by its own
    # paragraph.  Inline declarations never overwrite a real paragraph.
    own: dict[tuple[str, ...], str] = {}
    order: list[tuple[str, ...]] = []
    declared_only: set[tuple[str, ...]] = set()
    # Unlabeled paragraphs (definition entries, lead-ins, figure captions) hang
    # off their enclosing path; they get their own row but share its citation,
    # because inventing a label would put a citation on screen that is not in
    # the CFR.
    extras: list[tuple[tuple[str, ...], int, str]] = []
    seq_by_path: dict[tuple[str, ...], int] = {}

    for p in parse.paragraphs:
        for anc_path, intro in p.ancestors_introduced:
            if anc_path not in own:
                own[anc_path] = _squash(intro)
                order.append(anc_path)
                declared_only.add(anc_path)
        if not p.labeled:
            seq = seq_by_path.get(p.path, 0)
            seq_by_path[p.path] = seq + 1
            extras.append((p.path, seq, _squash(p.text)))
            continue
        text = _squash(p.text)
        if p.path in own and p.path in declared_only:
            # The paragraph itself wins; keep the inline heading as a prefix if
            # it adds anything (740.5 declares "(b)" with no heading at all).
            intro = own[p.path]
            own[p.path] = f"{intro} {text}".strip() if intro else text
            declared_only.discard(p.path)
        elif p.path not in own:
            own[p.path] = text
            order.append(p.path)
        else:
            own[p.path] = f"{own[p.path]} {text}".strip()

    # Subtree text for the rollup half of context_text.
    children: dict[tuple[str, ...], list[tuple[str, ...]]] = {}
    for path in order:
        children.setdefault(path[:-1], []).append(path)

    def subtree_text(path: tuple[str, ...]) -> str:
        parts: list[str] = []
        for child in children.get(path, []):
            parts.append(f"{labels.format_path(child)} {own[child]}".strip())
            parts.append(subtree_text(child))
        return " ".join(p for p in parts if p)

    nodes: list[Provision] = []

    def make(
        path: tuple[str, ...], text: str, seq: int | None = None, labeled: bool = True
    ) -> Provision:
        cite = labels.citation(doc.section, path)
        header = f"{doc.regulation} ({doc.agency}) {cite} — {doc.heading}"
        ancestry = " ".join(
            f"{labels.format_path(path[:i])} {own[path[:i]]}".strip()
            for i in range(1, len(path))
            if path[:i] in own and own[path[:i]]
        )
        limit = _SUBTREE_CHARS_TOP if len(path) <= 1 else _SUBTREE_CHARS_DEEP
        sub = _truncate(subtree_text(path), limit) if labeled else ""
        context = "\n".join(p for p in (header, ancestry, text, sub) if p)

        # Some paragraphs exist only as a container: 740.5(b) is declared by
        # "(b)(1) The official advertising statement is ..." and has no text of
        # its own at all.  Showing a reviewer a citation with an empty body is
        # worse than useless, so such a node displays its block instead.
        shown = text or _truncate(sub, _SUBTREE_CHARS_DEEP)
        return Provision(
            id=labels.node_id(doc.id, path, seq),
            citation=cite,
            section=doc.section,
            part=doc.part,
            part_title=doc.part_title,
            regulation=doc.regulation,
            agency=doc.agency,
            heading=doc.heading,
            path=path,
            depth=len(path),
            kind=classify(doc.heading, shown, ancestry),
            own_text=_truncate(shown, 4_000),
            context_text=context,
            url=labels.anchor_url(doc.url, doc.section, path),
            as_of=as_of,
            labeled=labeled,
        )

    for path in order:
        nodes.append(make(path, own[path]))
    for path, seq, text in extras:
        nodes.append(make(path, text, seq=seq, labeled=False))

    return nodes, parse.warnings


def build_nodes(corpus: Corpus) -> tuple[list[Provision], list[str]]:
    """Every provision node in the corpus, plus every parse warning."""
    nodes: list[Provision] = []
    warnings: list[str] = []
    for doc in corpus.sections:
        sec_nodes, sec_warnings = build_section_nodes(doc, corpus.as_of)
        nodes.extend(sec_nodes)
        warnings.extend(sec_warnings)
    _check_unique_ids(nodes, warnings)
    return nodes, warnings


def _check_unique_ids(nodes: Sequence[Provision], warnings: list[str]) -> None:
    seen: set[str] = set()
    for n in nodes:
        if n.id in seen:
            warnings.append(f"duplicate provision id {n.id} -- parser or id bug")
        seen.add(n.id)


def citations_of(nodes: Iterable[Provision]) -> list[str]:
    """Ordered citation list, for the committed parser snapshot."""
    return [n.citation for n in nodes]
