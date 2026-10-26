"""Grounding, and the degradation path -- both offline.

The point being proved is that **grounding is enforced in code**, not merely
requested in the prompt. Each case here is also a prompt-injection case: an ad
that successfully talks the model into inventing a citation still cannot get
that citation onto the screen.
"""

from __future__ import annotations

from typing import Any

import pytest

from app import assess as assess_mod
from app.applicability import AdProfile, gate
from app.assess import Finding
from app.config import load_settings
from app.llm import LLMClient
from app.retrieve import Candidate, Retrieval

AD = "New high-yield savings: 5.00% APY! Member FDIC."


def findings_fixture() -> list[Finding]:
    return [
        Finding(
            ref="C1",
            citation="12 CFR 1030.8(b)",
            regulation="Regulation DD",
            agency="CFPB",
            heading="Advertising.",
            kind="obligation",
            url="https://example.test/#p-1030.8(b)",
            as_of="2026-10-05",
            provision_text="If an advertisement states a rate of return...",
            ancestor_context="",
        ),
        Finding(
            ref="C2",
            citation="12 CFR 328.6",
            regulation="FDIC Part 328",
            agency="FDIC",
            heading="Advertising.",
            kind="obligation",
            url="https://example.test/#p-328.6",
            as_of="2026-10-05",
            provision_text="Official advertising statement requirements...",
            ancestor_context="",
        ),
    ]


def test_hallucinated_citation_is_dropped_and_others_survive():
    """The headline grounding case.

    A provision that was not in the candidate list cannot reach the screen, and
    dropping it must not take the legitimate finding with it.
    """
    findings, dropped, _ = assess_mod._apply_findings(
        findings_fixture(),
        {
            "findings": [
                {
                    "ref": "C99",
                    "citation": "12 CFR 9999.99(z)",
                    "applies": True,
                    "verdict": "violates",
                    "reason": "invented",
                },
                {
                    "ref": "C1",
                    "citation": "12 CFR 1030.8(b)",
                    "applies": True,
                    "verdict": "meets",
                    "reason": "states the APY",
                    "ad_evidence": "5.00% APY",
                },
            ]
        },
    )
    assert len(dropped) == 1
    assert dropped[0]["citation"] == "12 CFR 9999.99(z)"
    assert "not in the candidate list" in dropped[0]["reason"]
    kept = {f.ref: f for f in findings}
    assert kept["C1"].verdict == "meets"
    assert kept["C1"].ad_evidence == "5.00% APY"
    assert all(f.citation != "12 CFR 9999.99(z)" for f in findings)


def test_citation_that_disagrees_with_its_ref_is_dropped():
    """A real handle with the wrong citation attached is still ungrounded."""
    _, dropped, _ = assess_mod._apply_findings(
        findings_fixture(),
        {
            "findings": [
                {
                    "ref": "C1",
                    "citation": "12 CFR 328.6",  # C1 is 1030.8(b)
                    "applies": True,
                    "verdict": "violates",
                    "reason": "transposed",
                }
            ]
        },
    )
    assert len(dropped) == 1
    # The reason names both strings, so the next wholesale drop is diagnosable
    # from the response alone.
    assert "12 CFR 328.6" in dropped[0]["reason"]
    assert "12 CFR 1030.8(b)" in dropped[0]["reason"]


@pytest.mark.parametrize(
    "claimed",
    [
        "12 CFR 1030.8(b)",
        "§ 1030.8(b)",
        "1030.8(b)",
        "12 C.F.R. § 1030.8(b)",
        "  12 cfr 1030.8(b) ",
    ],
)
def test_citation_formatting_variants_are_accepted(claimed):
    """Format is not identity.

    Observed live: the model wrote every citation one way, exact-equality
    rejected all 24 findings at once, and the screen was indistinguishable
    from "nothing found". The citation shown to the reviewer always comes from
    the store, so this only asks whether the right handle was cited.
    """
    findings, dropped, _ = assess_mod._apply_findings(
        findings_fixture(),
        {
            "findings": [
                {
                    "ref": "C1",
                    "citation": claimed,
                    "applies": True,
                    "verdict": "violates",
                    "reason": "states a rate without the APY term",
                }
            ]
        },
    )
    assert dropped == [], f"{claimed!r} should match 12 CFR 1030.8(b)"
    assert {f.ref: f for f in findings}["C1"].verdict == "violates"


@pytest.mark.parametrize(
    "claimed",
    ["12 CFR 1030.8(c)", "12 CFR 1030.9(b)", "12 CFR 328.6", "12 CFR 1030.8(b)(1)"],
)
def test_a_different_provision_is_still_dropped(claimed):
    """Normalising must not blur one paragraph into its neighbour."""
    _, dropped, _ = assess_mod._apply_findings(
        findings_fixture(),
        {
            "findings": [
                {
                    "ref": "C1",  # C1 is 12 CFR 1030.8(b)
                    "citation": claimed,
                    "applies": True,
                    "verdict": "violates",
                    "reason": "wrong provision",
                }
            ]
        },
    )
    assert len(dropped) == 1, f"{claimed!r} is not 1030.8(b) and must be dropped"
    assert claimed in dropped[0]["reason"], "the reason names what the model cited"


def test_verdict_outside_the_enum_is_demoted_not_trusted():
    findings, _, _ = assess_mod._apply_findings(
        findings_fixture(),
        {
            "findings": [
                {
                    "ref": "C1",
                    "citation": "12 CFR 1030.8(b)",
                    "applies": True,
                    "verdict": "definitely_illegal",
                    "reason": "off-enum",
                }
            ]
        },
    )
    assert {f.ref: f for f in findings}["C1"].verdict == "unclear"


def test_malformed_findings_array_is_reported():
    _, dropped, _ = assess_mod._apply_findings(findings_fixture(), {"findings": "nope"})
    assert dropped and "no findings array" in dropped[0]["reason"]


def test_non_object_finding_is_dropped():
    _, dropped, _ = assess_mod._apply_findings(
        findings_fixture(), {"findings": ["a string"]}
    )
    assert dropped and "not an object" in dropped[0]["reason"]


# --------------------------------------------------------------------------
# degradation
# --------------------------------------------------------------------------


class StubStore:
    """Only what ``check`` asks of a store."""

    def corpus_meta(self):
        return {"regulations": []}


def _stub_retrieval(monkeypatch) -> Candidate:
    cand = Candidate(
        ref="C1",
        node_id="n1",
        citation="12 CFR 1030.8(b)",
        section="1030.8",
        regulation="Regulation DD",
        agency="CFPB",
        heading="Advertising.",
        kind="obligation",
        path=("b",),
        own_text="If an advertisement states a rate of return...",
        ancestor_context="",
        url="https://example.test/#p-1030.8(b)",
        as_of="2026-10-05",
        score=0.5,
        why_retrieved=("the submission itself:semantic",),
    )
    monkeypatch.setattr(
        assess_mod,
        "retrieve",
        lambda *a, **k: Retrieval(
            candidates=[cand],
            gate=gate(AdProfile("bank", fdic_insured=True, flags={"states_apy": True})),
        ),
    )
    return cand


def test_no_api_key_still_returns_usable_results(monkeypatch):
    """Retrieval-only is a product tier, not a crippled fallback.

    The brief makes the LLM optional, so this path has to be good: real
    citations, provision text and eCFR links, with the reason it has no
    verdicts stated on screen.
    """
    _stub_retrieval(monkeypatch)
    cfg = load_settings()
    assert not cfg.llm_enabled

    result = assess_mod.check(
        StubStore(),
        ad_text=AD,
        advertiser={"type": "bank", "fdic_insured": True},
        channel="instagram",
        cfg=cfg,
    )
    assert result.mode == "retrieval_only"
    assert len(result.findings) == 1
    f = result.findings[0]
    assert f.citation == "12 CFR 1030.8(b)"
    assert f.provision_text and f.url
    assert any("OPENAI_API_KEY" in n for n in result.notices)


def test_the_toggle_makes_zero_outbound_calls_even_with_a_key(monkeypatch):
    """The reviewer's switch has to actually stop the egress, not hide it.

    A key makes verdicts available; ``use_llm`` makes them wanted. Both must be
    true, and the transport here fails the test if it is ever reached.
    """
    _stub_retrieval(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-not-a-real-key")
    from app import config

    config.reset_settings()
    cfg = config.settings()
    assert cfg.llm_enabled, "the key is configured; the toggle is the only thing off"

    def spy(**request: Any):
        raise AssertionError("outbound request made with use_llm=False")

    result = assess_mod.check(
        StubStore(),
        ad_text=AD,
        advertiser={"type": "bank", "fdic_insured": True},
        use_llm=False,
        cfg=cfg,
        client=LLMClient(cfg, transport=spy),
    )
    assert result.mode == "retrieval_only"
    assert len(result.findings) == 1, "the provisions are still returned"
    assert result.findings[0].citation == "12 CFR 1030.8(b)"
    assert any("switched off" in n for n in result.notices)


def test_the_toggle_defaults_to_on(monkeypatch):
    """Leaving it unset must not silently disable verdicts for an API caller."""
    _stub_retrieval(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-not-a-real-key")
    from app import config

    config.reset_settings()
    cfg = config.settings()

    calls: list[dict[str, Any]] = []

    def transport(**request: Any):
        calls.append(request)
        return {
            "model": "gpt-5",
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {"type": "output_text", "text": '{"findings": [], "overall_note": null}'}
                    ],
                }
            ],
        }

    result = assess_mod.check(
        StubStore(),
        ad_text=AD,
        advertiser={"type": "bank", "fdic_insured": True},
        cfg=cfg,
        client=LLMClient(cfg, transport=transport),
    )
    assert len(calls) == 1
    assert result.mode == "verdicts"


def test_a_provider_failure_degrades_instead_of_raising(monkeypatch):
    """The demo must not show a stack trace when the model is unreachable."""
    _stub_retrieval(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-not-a-real-key")
    from app import config

    config.reset_settings()
    cfg = config.settings()

    def boom(**request: Any):
        raise RuntimeError("upstream exploded")

    result = assess_mod.check(
        StubStore(),
        ad_text=AD,
        advertiser={"type": "bank", "fdic_insured": True},
        cfg=cfg,
        client=LLMClient(cfg, transport=boom),
    )
    assert result.mode == "retrieval_only"
    assert len(result.findings) == 1, "the provisions are still shown"
    assert any("failed" in n for n in result.notices)


def test_a_refusal_is_surfaced_not_crashed(monkeypatch):
    _stub_retrieval(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-not-a-real-key")
    from app import config

    config.reset_settings()
    cfg = config.settings()

    refusing = lambda **request: {  # noqa: E731
        "model": "gpt-5",
        "status": "completed",
        "output": [
            {"type": "reasoning", "id": "rs_1"},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "refusal", "refusal": "I can't help with that."}],
            },
        ],
    }
    result = assess_mod.check(
        StubStore(),
        ad_text=AD,
        advertiser={"type": "bank", "fdic_insured": True},
        cfg=cfg,
        client=LLMClient(cfg, transport=refusing),
    )
    assert result.mode == "retrieval_only"
    assert any("declined" in n for n in result.notices)


def test_verdicts_mode_applies_the_model_output(monkeypatch):
    _stub_retrieval(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-not-a-real-key")
    from app import config

    config.reset_settings()
    cfg = config.settings()

    body = (
        '{"findings": [{"ref": "C1", "citation": "12 CFR 1030.8(b)", "applies": true, '
        '"verdict": "violates", "reason": "states a rate without the APY term", '
        '"ad_evidence": "5.00% APY", "caveat": null}], "overall_note": null}'
    )
    transport = lambda **request: {  # noqa: E731
        "model": "gpt-5",
        "status": "completed",
        "output": [
            {"type": "reasoning", "id": "rs_1"},
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": body}],
            },
        ],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    result = assess_mod.check(
        StubStore(),
        ad_text=AD,
        advertiser={"type": "bank", "fdic_insured": True},
        cfg=cfg,
        client=LLMClient(cfg, transport=transport),
    )
    assert result.mode == "verdicts"
    assert result.dropped == []
    f = result.findings[0]
    assert f.verdict == "violates"
    assert f.ad_evidence == "5.00% APY"
    assert f.caveat == "", "null caveat becomes empty, not the string 'None'"


def test_the_request_is_shaped_for_the_responses_api(monkeypatch):
    """Strict schema, reasoning effort, and no retention."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-proj-not-a-real-key")
    from app import config

    config.reset_settings()
    cfg = config.settings()

    request = LLMClient(cfg, transport=lambda **r: {}).build_request("USER")
    assert request["model"] == cfg.model
    assert request["reasoning"]["effort"] == cfg.assess_effort
    assert request["text"]["format"]["strict"] is True
    assert request["store"] is False
    assert "temperature" not in request and "top_p" not in request
    # Everything volatile is in `input`; the prompt prefix is a constant.
    assert request["input"][0]["content"] == "USER"
