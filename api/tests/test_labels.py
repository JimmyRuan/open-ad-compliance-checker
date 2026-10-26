"""The label parser: the hardest logic in the build, so the most tested.

The golden table below is hand-derived from the regulation text, one case per
structural trap the corpus actually contains. A misreading here becomes a wrong
citation in front of a reviewer, which is the worst failure this tool has.
"""

from __future__ import annotations

import json
import time

import pytest
from hypothesis import given, settings as hyp_settings
from hypothesis import strategies as st

from app import labels



#: (section, paragraph index, expected citation, why this case is here)
GOLDEN = [
    ("1026.24", 3, "12 CFR 1026.24(d)(1)", "em-dash double label"),
    ("1026.24", 11, "12 CFR 1026.24(d)(2)(iii)", "three levels deep"),
    ("1026.24", 20, "12 CFR 1026.24(f)(2)(i)(C)", "four levels deep"),
    (
        "1026.24",
        34,
        "12 CFR 1026.24(i)",
        "(i) after (h)(2) is ALPHA, not roman -- needs lookahead",
    ),
    ("1026.1", 2, "12 CFR 1026.1(c)(1)", "period-separated double label"),
    ("740.5", 1, "12 CFR 740.5(b)(1)", "bare (b)(1) prefix, no separator"),
    ("1030.8", 12, "12 CFR 1030.8(c)(6)(ii)", "roman under a named sub-paragraph"),
    (
        "328.5",
        8,
        "12 CFR 328.5(d)(1)(i)",
        "TRIPLE label: em dash then period, three labels in one paragraph",
    ),
    (
        "1026.16",
        55,
        "12 CFR 1026.16(h)(4)(i)",
        "(i) after (h)(4) is ROMAN -- the mirror image of 1026.24[34], and the "
        "case the self-reference oracle caught when a prose fallback let a "
        "wrong parse succeed",
    ),
    ("1026.16", 57, "12 CFR 1026.16(h)(5)", "returns to level 2 after roman children"),
    (
        "1026.16",
        28,
        "12 CFR 1026.16(d)(6)(i)(B)(1)(i)",
        "six levels: exercises the full alphabet including italic digits/romans",
    ),
]


@pytest.mark.parametrize(
    "section,index,expected,why", GOLDEN, ids=[g[0] + "[" + str(g[1]) + "]" for g in GOLDEN]
)
def test_golden_citations(sections, section, index, expected, why):
    parse = labels.parse_paragraphs(sections[section]["paragraphs"], section)
    found = {p.index: p for p in parse.paragraphs}
    assert index in found, f"paragraph {index} was dropped ({why})"
    got = labels.citation(section, found[index].path)
    assert got == expected, f"{why}: expected {expected}, got {got}"


def test_no_parse_warnings_beyond_image_placeholders(sections):
    """The parser's tripwire.

    A resync warning, a duplicate path or a prose fallback each mean a citation
    somewhere is wrong, so anything but the three known image stubs fails.
    """
    unexpected = []
    for section, doc in sections.items():
        parse = labels.parse_paragraphs(doc["paragraphs"], section)
        unexpected += [w for w in parse.warnings if "image placeholder" not in w]
    assert unexpected == [], unexpected


def test_every_path_has_a_parent(sections):
    """No path may skip a level: ``(d)(2)(iii)`` requires ``(d)`` and ``(d)(2)``.

    Ancestors introduced inline count as known -- ``(c) Heading—(1) text`` is one
    paragraph that declares ``(c)`` without ``(c)`` having a paragraph of its own.
    """
    for section, doc in sections.items():
        parse = labels.parse_paragraphs(doc["paragraphs"], section)
        known = {p.path for p in parse.paragraphs}
        for p in parse.paragraphs:
            for anc, _ in p.ancestors_introduced:
                known.add(anc)
        for p in parse.paragraphs:
            for i in range(1, len(p.path)):
                assert p.path[:i] in known, (
                    f"{section}{labels.format_path(p.path)} has no parent "
                    f"{labels.format_path(p.path[:i])}"
                )


def test_labelled_paths_are_unique_per_section(sections):
    """Two provisions sharing a citation would make validation ambiguous."""
    for section, doc in sections.items():
        parse = labels.parse_paragraphs(doc["paragraphs"], section)
        seen = [p.path for p in parse.paragraphs if p.path and p.labeled]
        assert len(seen) == len(set(seen)), f"{section}: duplicate paths"


def test_citations_are_produced_for_the_whole_corpus(sections):
    """~436 labelled paragraphs; a silent shrink would mean a parser regression."""
    total = 0
    for section, doc in sections.items():
        parse = labels.parse_paragraphs(doc["paragraphs"], section)
        total += sum(1 for p in parse.paragraphs if p.path)
    assert total > 400, f"expected ~436 parsed paragraphs, got {total}"


def test_paths_are_json_serialisable(sections):
    """They cross the API boundary, so they must survive a round trip."""
    parse = labels.parse_paragraphs(sections["1026.24"]["paragraphs"], "1026.24")
    assert json.loads(json.dumps([list(p.path) for p in parse.paragraphs]))


def test_anchor_url_falls_back_at_depth_zero():
    base = "https://www.ecfr.gov/current/title-12/section-1030.8"
    assert labels.anchor_url(base, "1030.8", ()) == base
    assert labels.anchor_url(base, "1030.8", ("b",)) == f"{base}#p-1030.8(b)"


def test_parser_is_fast_enough_to_run_on_every_boot(sections):
    """Ingest parses the whole corpus; it must not be a startup cost."""
    start = time.perf_counter()
    for section, doc in sections.items():
        labels.parse_paragraphs(doc["paragraphs"], section)
    elapsed = time.perf_counter() - start
    assert elapsed < 2.0, f"parsing 25 sections took {elapsed:.2f}s"


@given(st.text(max_size=400))
@hyp_settings(max_examples=200, deadline=None)
def test_parser_never_raises_on_arbitrary_text(text):
    """The demo pastes in unseen text; a stack trace is not an acceptable answer."""
    labels.parse_paragraphs([text], "1026.24")
