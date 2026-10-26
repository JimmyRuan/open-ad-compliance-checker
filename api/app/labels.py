"""Reconstruct the CFR paragraph label tree from flat paragraph text.

eCFR gives us paragraphs in document order with the label inline at the start of
the text and *no* nesting information.  The citation precision the brief asks
for -- ``12 CFR 1026.24(d)(2)(iii)`` -- lives at the leaf of that tree, so
rebuilding it is the first thing that has to be right; nothing downstream is
trustworthy until it is.

The level alphabet is fixed by the Office of the Federal Register's drafting
handbook::

    1: (a) (b) (c) ...      lower alpha
    2: (1) (2) (3) ...      arabic
    3: (i) (ii) (iii) ...   lower roman
    4: (A) (B) (C) ...      upper alpha
    5: (1) (2) (3) ...      arabic (italic in print)
    6: (i) (ii) (iii) ...   lower roman (italic in print)

Two kinds of ambiguity make a single greedy pass insufficient.

*Token ambiguity.*  ``(i)`` is both the ninth lower-alpha letter (level 1) and
the first lower roman numeral (level 3).  ``(1)`` is both level 2 and level 5.
This corpus contains the hard case at ``1026.24``: paragraph 34 is ``(i)
Prohibited acts or practices ...`` arriving while the stack is ``[h, 2]``, where
*both* readings are structurally legal and no level is skipped either way.  What
resolves it is the *next* token -- ``(1)`` is legal under the level-1 reading
and illegal under the roman reading -- so the parser needs lookahead, not
greed.

*Tokenisation ambiguity.*  A single paragraph can carry several labels, in four
separating forms the data actually contains::

    (d) Advertisement of terms ...—(1) Triggering terms. If any ...   em dash
    (c) Coverage. (1) In general, this part applies ...               period
    (b)(1) The official advertising statement is ...                  adjacent
    (d) Non-deposit signage—(1) Display of ... signage. (i) An ...    all three

Rather than guess where the label run ends and then hope the structure fits,
both ambiguities are resolved *together*: ``candidate_runs`` proposes every
plausible tokenisation of a paragraph, the stack machine proposes every legal
placement, and a depth-first search over the whole section returns the first
globally consistent parse.  A tokenisation that does not fit the document
structure is rejected by the structure itself.

Nothing in here touches the database, the network, or any config -- it is pure
logic over strings, which is why it carries the repo's highest coverage gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable, Iterator, Literal, Sequence

# --------------------------------------------------------------------------
# the level alphabet
# --------------------------------------------------------------------------

Kind = Literal["alpha", "arabic", "roman", "upper"]

#: 1-indexed; ``LEVEL_KIND[n]`` is the token kind used at depth ``n``.
LEVEL_KIND: tuple[Kind, ...] = (
    "alpha",  # level 1   (a)
    "arabic",  # level 2   (1)
    "roman",  # level 3   (i)
    "upper",  # level 4   (A)
    "arabic",  # level 5   (1)
    "roman",  # level 6   (i)
)
MAX_LEVEL = len(LEVEL_KIND)

_ROMAN_VALUES = (
    ("ix", 9),
    ("iv", 4),
    ("x", 10),
    ("v", 5),
    ("i", 1),
)

# A label token: 1-2 letters, or 1-2 digits, or a short roman numeral.  Kept
# deliberately tight -- a loose pattern turns every parenthetical in the prose
# ("paragraph (d)(2) of this section") into a candidate label.
_TOKEN = r"[A-Za-z]{1,4}|\d{1,2}"
_LABEL_RE = re.compile(rf"\((?P<tok>{_TOKEN})\)")
_IMAGE_RE = re.compile(r"^\s*\[Image omitted[^\]]*\]\s*$")

#: Longest heading we will believe sits between two labels of the same
#: paragraph.  Real ones run to ~75 characters ("Disclosure of rates and
#: payments in advertisements for credit secured by a dwelling"); a cap keeps
#: the period form from reaching across a paragraph of prose.
_MAX_INLINE_HEADING = 110


def roman_to_int(tok: str) -> int | None:
    """Value of a lower-roman numeral, or ``None`` if ``tok`` is not one."""
    s = tok.lower()
    if not s or any(ch not in "ivxlcdm" for ch in s):
        return None
    total, i = 0, 0
    while i < len(s):
        for sym, val in _ROMAN_VALUES:
            if s.startswith(sym, i):
                total += val
                i += len(sym)
                break
        else:
            return None
    # Reject non-canonical spellings ("iiii", "vv") -- they are far more likely
    # to be a stray word in parentheses than a paragraph label.
    return total if int_to_roman(total) == s else None


def int_to_roman(n: int) -> str:
    """Canonical lower-roman spelling of ``n`` (1-based, small values only)."""
    if n <= 0:
        return ""
    out, rest = [], n
    for sym, val in (("x", 10), ("ix", 9), ("v", 5), ("iv", 4), ("i", 1)):
        while rest >= val:
            out.append(sym)
            rest -= val
    return "".join(out)


def render_label(kind: Kind, value: int) -> str:
    """The token text a (kind, value) pair would be printed as."""
    if kind == "arabic":
        return str(value)
    if kind == "roman":
        return int_to_roman(value)
    if kind == "alpha":
        return chr(ord("a") + value - 1)
    return chr(ord("A") + value - 1)


def _token_value(tok: str, kind: Kind) -> int | None:
    """Value ``tok`` would have if read as ``kind``, else ``None``."""
    if kind == "arabic":
        return int(tok) if tok.isdigit() and not tok.startswith("0") else None
    if kind == "roman":
        return roman_to_int(tok)
    if kind == "alpha":
        return ord(tok) - ord("a") + 1 if re.fullmatch(r"[a-z]", tok) else None
    return ord(tok) - ord("A") + 1 if re.fullmatch(r"[A-Z]", tok) else None


def token_readings(tok: str) -> list[tuple[int, int]]:
    """Every ``(level, value)`` a token could denote, shallowest level first."""
    out = []
    for level in range(1, MAX_LEVEL + 1):
        value = _token_value(tok, LEVEL_KIND[level - 1])
        if value is not None:
            out.append((level, value))
    return out


# --------------------------------------------------------------------------
# tokenisation: which labels does this paragraph carry?
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Run:
    """One candidate reading of a paragraph's leading label run.

    ``labels`` are the raw token texts in order.  ``intros`` is the text
    attributed to each label *except* the last -- the short italic heading that
    introduces a block, e.g. ``"Advertisement of terms that require additional
    disclosures"`` for ``(d)``.  ``body`` is what is left for the deepest
    label, which is the text a reviewer actually reads.
    """

    labels: tuple[str, ...]
    intros: tuple[str, ...]
    body: str


def _match_label_at(text: str, pos: int) -> re.Match[str] | None:
    m = _LABEL_RE.match(text, pos)
    return m


def candidate_runs(text: str) -> list[Run]:
    """Candidate tokenisations of ``text``, longest label run first.

    Longest-first matters: the structural search takes the first candidate that
    fits, and a longer run is only ever proposed when the separators genuinely
    look like paragraph structure.  If the structure rejects it, the shorter
    runs are still there to fall back on -- including the empty run, so an
    unlabeled paragraph always has a reading.
    """
    stripped = text.strip()
    if not stripped:
        return [Run((), (), "")]

    labels: list[str] = []
    intros: list[str] = []
    bodies: list[str] = []  # bodies[k] = remaining text after labels[:k+1]

    pos = 0
    # 1. Adjacent labels at the very start: "(b)(1) The official ...".
    while (m := _match_label_at(stripped, pos)) is not None:
        labels.append(m.group("tok"))
        pos = m.end()
        bodies.append(stripped[pos:].strip())
        if not stripped.startswith("(", pos):
            break
        intros.append("")  # no heading between adjacent labels

    # 2. Then: short heading, separator, next label.  Repeats -- 328.5 has a
    #    paragraph that chains an em dash and a period to reach three labels.
    while labels:
        rest = stripped[pos:]
        m = _inline_label(rest)
        if m is None:
            break
        heading, tok, consumed = m
        intros.append(heading)
        labels.append(tok)
        pos += consumed
        bodies.append(stripped[pos:].strip())

    runs: list[Run] = []
    for k in range(len(labels), 0, -1):
        # Reading the first k labels: everything after label k is the body.
        runs.append(
            Run(
                labels=tuple(labels[:k]),
                intros=tuple(intros[: k - 1]),
                body=bodies[k - 1],
            )
        )
    runs.append(Run((), (), stripped))
    return runs


def starts_with_label(text: str) -> bool:
    """True if ``text`` opens with something that looks like a paragraph label."""
    return _LABEL_RE.match(text.strip(), 0) is not None


def _inline_label(rest: str) -> tuple[str, str, int] | None:
    """Find ``heading <sep> (tok)`` at the start of ``rest``.

    Returns ``(heading, token, chars_consumed)``.  Two separators occur in the
    data: an em dash, and a sentence period followed by a space.  The em-dash
    form is tried first because it is unambiguous -- an em dash immediately
    before a parenthesised token is never prose in this corpus.
    """
    em = re.match(
        rf"\s*(?P<head>[^.;:—]{{0,{_MAX_INLINE_HEADING}}}?)\s*—\s*\(({_TOKEN})\)",
        rest,
    )
    if em is not None:
        return em.group("head").strip(), em.group(2), em.end()

    dot = re.match(
        rf"\s*(?P<head>.{{1,{_MAX_INLINE_HEADING}}}?[.])\s+\(({_TOKEN})\)",
        rest,
    )
    if dot is not None:
        return dot.group("head").strip(), dot.group(2), dot.end()
    return None


# --------------------------------------------------------------------------
# the stack machine
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Frame:
    level: int
    value: int


Stack = tuple[Frame, ...]

#: Placement kinds, in the order the search prefers them.  Siblings before
#: children is what makes ``(i)`` after ``(h)(2)`` read as level-1 ``(i)``
#: first; backtracking is what makes it safe to prefer.
_SIBLING, _CHILD, _RESYNC = "sibling", "child", "resync"


def _placements(stack: Stack, tok: str) -> Iterator[tuple[Stack, str]]:
    """Legal stacks after appending ``tok``, in preference order.

    Three moves, and the order is the whole disambiguation policy:

    1. **sibling** -- pop to an open level and take the exact successor.
       Shallowest first, which prefers "``(i)`` closes ``(h)``" over "``(i)``
       opens a roman list inside ``(h)(2)``".
    2. **child** -- open the next level down with its *first* value.  Levels
       may never be skipped, which is most of the pruning power here.
    3. **resync** -- a sibling jump that is not the exact successor.  Only
       reached when nothing else fits; the caller records a warning.  Without
       it one reserved-or-dropped label would strand the rest of a section.
    """
    readings = token_readings(tok)
    depth = len(stack)

    for level, value in readings:
        if level <= depth and stack[level - 1].value + 1 == value:
            yield stack[: level - 1] + (Frame(level, value),), _SIBLING

    for level, value in readings:
        if level == depth + 1 and value == 1:
            yield stack + (Frame(level, value),), _CHILD

    # A section excerpt may open at something other than (a); allow it, but
    # only once nothing cleaner matched.
    if depth == 0:
        for level, value in readings:
            if level == 1 and value != 1:
                yield (Frame(level, value),), _RESYNC

    for level, value in readings:
        if level <= depth and value > stack[level - 1].value + 1:
            yield stack[: level - 1] + (Frame(level, value),), _RESYNC


def _path_of(stack: Stack) -> tuple[str, ...]:
    return tuple(render_label(LEVEL_KIND[f.level - 1], f.value) for f in stack)


# --------------------------------------------------------------------------
# parse result
# --------------------------------------------------------------------------


@dataclass
class ParsedParagraph:
    """One paragraph of the source, placed in the label tree."""

    index: int
    """Position in the section's ``paragraphs`` array."""

    path: tuple[str, ...]
    """Label path of the deepest label this paragraph carries, e.g. ``("d","2","iii")``."""

    text: str
    """The paragraph's own text with its label run stripped."""

    raw: str
    """The paragraph exactly as published."""

    labeled: bool = True
    """False for paragraphs with no label of their own (definitions, captions)."""

    ancestors_introduced: tuple[tuple[tuple[str, ...], str], ...] = ()
    """``(path, intro_text)`` for ancestors this paragraph declared inline.

    ``1026.24`` paragraph 3 carries both ``(d)`` and ``(d)(1)``, so it declares
    ``(d)`` with the heading text and is itself cited at ``(d)(1)``.
    """

    resynced: bool = False
    """True if placement needed the non-successor fallback."""


@dataclass
class SectionParse:
    section: str
    paragraphs: list[ParsedParagraph] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    """Human-readable notes: resyncs, skipped images, exhausted search."""


# A hard cap on search states.  The real sections settle in a few hundred; the
# cap only exists so a pathological input degrades to a warning instead of
# hanging the ingest.
_STATE_BUDGET = 200_000


def parse_paragraphs(paragraphs: Sequence[str], section: str = "") -> SectionParse:
    """Place every paragraph of a section in the label tree.

    Depth-first over paragraph order, backtracking across both the candidate
    tokenisations and the candidate placements.  Failed ``(index, stack)``
    states are memoised, which is what keeps a 58-paragraph section with
    several ambiguous tokens from exploding.

    The search runs **twice**.  The first pass refuses to read a paragraph that
    opens with a parenthesised token as unlabeled prose; only if no parse
    exists under that rule does the second pass allow it.  That ordering is not
    cosmetic -- it is what forces backtracking instead of a plausible-looking
    wrong answer.  ``1026.16`` is the case that proves it: paragraph 55 opens
    ``(i) A statement that interest will be charged ...`` while the stack is
    ``[h, 4]``, so ``(i)`` is legal as the level-1 successor of ``(h)``.  With a
    prose escape hatch available, paragraph 56's ``(ii)`` -- which fits nowhere
    under that reading -- is quietly absorbed as a continuation of ``(i)`` and
    the section parses "successfully" with three paragraphs stacked on one
    wrong path.  Denying the escape hatch makes 56 fail, which makes 55 back up
    to ``(h)(4)(i)``, which is correct.  The corpus's own cross-references
    found this; the golden table did not.
    """
    result = SectionParse(section=section)

    # Drop eCFR's image placeholders before parsing -- they carry no text and
    # would otherwise each become a node.
    items: list[tuple[int, str]] = []
    for i, raw in enumerate(paragraphs):
        if _IMAGE_RE.match(raw):
            result.warnings.append(f"{section}[{i}]: skipped image placeholder")
            continue
        items.append((i, raw))

    all_runs: list[list[Run]] = [candidate_runs(raw) for _, raw in items]
    # Pass 1 drops the empty run from paragraphs that open with a label token.
    strict_runs: list[list[Run]] = [
        [r for r in runs if r.labels] if starts_with_label(raw) else runs
        for (_, raw), runs in zip(items, all_runs)
    ]

    placed_all = _search(items, strict_runs)
    if placed_all is None:
        placed_all = _search(items, all_runs)
        if placed_all is None:
            result.warnings.append(
                f"{section}: no consistent parse found; fell back to greedy placement"
            )
            placed_all = _greedy(items, all_runs)
        else:
            result.warnings.append(
                f"{section}: no parse treats every labelled paragraph as labelled; "
                "some paragraphs were read as unlabelled prose"
            )

    result.paragraphs = placed_all
    for p in placed_all:
        if p.resynced:
            result.warnings.append(
                f"{section}[{p.index}]: label ({p.path[-1] if p.path else '?'}) is not the "
                "successor of its sibling -- check for a reserved or removed paragraph"
            )
        if not p.labeled and starts_with_label(p.raw):
            result.warnings.append(
                f"{section}[{p.index}]: opens with a label token but was placed as prose "
                f"under {format_path(p.path)} -- likely a parser gap"
            )
    _assert_unique(result)
    return result


def _search(
    items: Sequence[tuple[int, str]], options: Sequence[list[Run]]
) -> list[ParsedParagraph] | None:
    """Backtracking placement of every paragraph, or ``None`` if impossible."""
    dead: set[tuple[int, Stack]] = set()
    budget = [_STATE_BUDGET]

    def search(i: int, stack: Stack) -> list[ParsedParagraph] | None:
        if i == len(items):
            return []
        if (i, stack) in dead:
            return None
        budget[0] -= 1
        if budget[0] <= 0:
            return None

        index, raw = items[i]
        for run in options[i]:
            for placed in _place_run(stack, run):
                tail = search(i + 1, placed.stack)
                if tail is None:
                    continue
                node = ParsedParagraph(
                    index=index,
                    path=_path_of(placed.stack),
                    text=run.body,
                    raw=raw,
                    labeled=bool(run.labels),
                    ancestors_introduced=placed.ancestors,
                    resynced=placed.resynced,
                )
                return [node] + tail
        dead.add((i, stack))
        return None

    return search(0, ())


@dataclass
class _Placed:
    stack: Stack
    ancestors: tuple[tuple[tuple[str, ...], str], ...]
    resynced: bool


def _place_run(stack: Stack, run: Run) -> Iterator[_Placed]:
    """Every way ``run``'s labels can be placed starting from ``stack``.

    An unlabeled paragraph attaches to the enclosing path unchanged: a
    definition entry in ``328.1`` or a figure caption is part of whatever block
    it sits in, and inventing a label for it would put a citation on screen
    that does not exist in the CFR.
    """
    if not run.labels:
        yield _Placed(stack, (), False)
        return

    def step(k: int, cur: Stack, acc: list[tuple[tuple[str, ...], str]], resynced: bool):
        if k == len(run.labels):
            yield _Placed(cur, tuple(acc), resynced)
            return
        for nxt, how in _placements(cur, run.labels[k]):
            is_last = k == len(run.labels) - 1
            extra = acc if is_last else acc + [(_path_of(nxt), run.intros[k])]
            yield from step(k + 1, nxt, extra, resynced or how == _RESYNC)

    yield from step(0, stack, [], False)


def _greedy(
    items: Sequence[tuple[int, str]], options: Sequence[list[Run]]
) -> list[ParsedParagraph]:
    """Last-resort single pass: first placement that fits, never backtrack."""
    out: list[ParsedParagraph] = []
    stack: Stack = ()
    for (index, raw), runs in zip(items, options):
        for run in runs:
            placed = next(_place_run(stack, run), None)
            if placed is None:
                continue
            out.append(
                ParsedParagraph(
                    index=index,
                    path=_path_of(placed.stack),
                    text=run.body,
                    raw=raw,
                    labeled=bool(run.labels),
                    ancestors_introduced=placed.ancestors,
                    resynced=True,
                )
            )
            stack = placed.stack
            break
    return out


def _assert_unique(parse: SectionParse) -> None:
    """A duplicate path means a parser bug.  Make it loud, not silent."""
    seen: dict[tuple[str, ...], int] = {}
    for p in parse.paragraphs:
        if not p.labeled:
            continue  # unlabeled paragraphs legitimately share their parent's path
        if p.path in seen:
            parse.warnings.append(
                f"{parse.section}: duplicate path {format_path(p.path)} at paragraphs "
                f"{seen[p.path]} and {p.index}"
            )
        seen[p.path] = p.index


# --------------------------------------------------------------------------
# citations
# --------------------------------------------------------------------------


def format_path(path: Iterable[str]) -> str:
    """``("d","2","iii")`` -> ``"(d)(2)(iii)"``."""
    return "".join(f"({p})" for p in path)


def citation(section: str, path: Iterable[str], title: str = "12") -> str:
    """``"1026.24", ("d","2","iii")`` -> ``"12 CFR 1026.24(d)(2)(iii)"``."""
    return f"{title} CFR {section}{format_path(path)}"


def node_id(section_id: str, path: Sequence[str], seq: int | None = None) -> str:
    """Stable primary key: ``12-cfr-1026.24-d-2-iii``.

    ``seq`` disambiguates unlabeled paragraphs that share a parent path.
    """
    parts = [section_id, *[p.lower() for p in path]]
    if seq is not None:
        parts.append(f"t{seq}")
    return "-".join(parts)


def anchor_url(section_url: str, section: str, path: Sequence[str]) -> str:
    """eCFR paragraph deep link, falling back to the section URL at depth 0.

    The ``#p-`` anchor convention is eCFR's; see DECISIONS.md -- it is verified
    by clicking, not by fetching, because eCFR blocks automated requests.
    """
    if not path:
        return section_url
    return f"{section_url}#p-{section}{format_path(path)}"


# --------------------------------------------------------------------------
# the corpus as its own oracle
# --------------------------------------------------------------------------

_REF_TOK = r"[A-Za-z0-9]{1,4}"
_SELFREF_RE = re.compile(
    rf"paragraphs?\s+(?P<refs>\({_REF_TOK}\)(?:\({_REF_TOK}\))*"
    rf"(?:[\s,]*(?:and|or|through|to)?[\s,]*\({_REF_TOK}\)(?:\({_REF_TOK}\))*)*)"
    r"\s+of\s+this\s+section"
)
_REF_GROUP_RE = re.compile(rf"(?:\({_REF_TOK}\))+")
_REF_TOK_RE = re.compile(rf"\((?P<tok>{_REF_TOK})\)")


def self_references(text: str) -> list[tuple[str, ...]]:
    """In-section ``paragraph (x)(y) of this section`` references found in ``text``.

    The regulation text is full of these, which makes the corpus a free
    correctness oracle for the parser: every path referenced ought to exist in
    the tree we built.  It is the check that found the ``1026.16`` bug a
    hand-written golden table could not -- 58 references across 25 sections,
    none of them written by me.

    Drafters use two shorthands inside a reference list, and both are expanded
    here rather than treated as noise, because leaving them unexpanded is what
    turns the oracle into a wall of false positives nobody reads:

    - ``paragraphs (b)(2) through (4) of this section`` -- the range endpoint
      ``(4)`` means ``(b)(4)``;
    - ``paragraphs (b)(1)(ii) and (iv) of this section`` -- the sibling ``(iv)``
      means ``(b)(1)(iv)``.

    A group shorter than the first group in the list is read as a suffix of it.
    Note this returns the *endpoints* of a range, not its interior, so a
    reference to a reserved middle paragraph is still a possible false
    positive; the caller reports rather than asserts.
    """
    out: list[tuple[str, ...]] = []
    for m in _SELFREF_RE.finditer(text):
        groups = [
            tuple(t.group("tok") for t in _REF_TOK_RE.finditer(g.group(0)))
            for g in _REF_GROUP_RE.finditer(m.group("refs"))
        ]
        if not groups:
            continue
        anchor = groups[0]
        for g in groups:
            out.append(anchor[: len(anchor) - len(g)] + g if len(g) < len(anchor) else g)
    return out


__all__ = [
    "LEVEL_KIND",
    "MAX_LEVEL",
    "ParsedParagraph",
    "Run",
    "SectionParse",
    "anchor_url",
    "candidate_runs",
    "citation",
    "format_path",
    "int_to_roman",
    "node_id",
    "parse_paragraphs",
    "render_label",
    "roman_to_int",
    "self_references",
    "starts_with_label",
    "token_readings",
]
