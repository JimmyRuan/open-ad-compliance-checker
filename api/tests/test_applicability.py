"""The applicability gate -- the highest-risk decision in the system.

A retrieval miss is recoverable: a human scanning candidates may still spot
the provision. A **gate** miss is not -- an excluded regulation is invisible to
retrieval, to the model, and to the reviewer. So this file tests the full truth
table, names each exclusion against the scope paragraph that justifies it, and
pins the fail-open behaviour.
"""

from __future__ import annotations

import itertools

import pytest

from app.applicability import (
    ALL_PARTS,
    KNOWN_ADVERTISER_TYPES,
    RULES,
    AdProfile,
    gate,
    keyword_flags,
    profile_from_advertiser,
)


def mk(advertiser_type="bank", *, fdic=False, ncua=False, **flags) -> AdProfile:
    return AdProfile(
        advertiser_type=advertiser_type,
        fdic_insured=fdic,
        ncua_insured=ncua,
        flags={k: True for k in flags if flags[k]},
    )


# --------------------------------------------------------------------------
# the named exclusions -- each references the paragraph it encodes
# --------------------------------------------------------------------------


def test_credit_union_is_excluded_from_reg_dd():
    """``1030.1(c)``: Reg DD applies to depository institutions *except credit
    unions*. This is the reason ad ``a3`` gets no APY-disclosure finding, and
    it is the exclusion most likely to look like a bug to a reviewer -- so it
    is a named test, not a row in a loop.
    """
    result = gate(mk("credit_union", ncua=True, is_deposit_product=True, states_apy=True))
    assert "1030" not in result.parts
    assert any("1030.1(c)" in note for note in result.excluded)


def test_nonbank_is_excluded_from_fdic_part_328():
    """``328.1``/``328.6(a)``: Part 328 reaches insured depository institutions.

    Ad ``a5``'s nonbank mortgage lender must never see Part 328 or Reg DD.
    """
    result = gate(mk("nonbank", is_mortgage=True, is_credit_product=True))
    assert "328" not in result.parts
    assert "1030" not in result.parts
    assert "1014" in result.parts, "Reg N reaches any person, bank or not"
    assert "1026" in result.parts, "Reg Z reaches any creditor"


def test_credit_union_is_excluded_from_part_328():
    result = gate(mk("credit_union", ncua=True, is_deposit_product=True))
    assert "328" not in result.parts
    assert "740" in result.parts


def test_bank_is_excluded_from_ncua_part_740():
    result = gate(mk("bank", fdic=True, is_deposit_product=True))
    assert "740" not in result.parts
    assert "328" in result.parts


def test_uninsured_bank_gets_no_insurance_part():
    """The flag, not the charter, drives Part 328."""
    result = gate(mk("bank", fdic=False, is_deposit_product=True))
    assert "328" not in result.parts
    assert "1030" in result.parts


def test_payment_amount_alone_puts_reg_z_in_scope():
    """Ad ``a1`` is the regression test for a real gate miss.

    *"Drive off in a new SUV for only $349/month!"* names no credit product --
    no "loan", no "financing", no "APR". Reg Z was being excluded for the one
    sample ad that most clearly violates it. "The amount of any payment" is
    itself a triggering term under ``1026.24(d)(1)(iii)``, so quoting a monthly
    payment is exactly the act that pulls an ad into scope.
    """
    result = gate(mk("bank", fdic=True, states_payment_amount=True))
    assert "1026" in result.parts


def test_a1_text_reaches_reg_z_end_to_end():
    """The same miss, exercised through the keyword fallback rather than flags."""
    text = (
        "Drive off in a new SUV for only $349/month! 🚙 Apply at any Example "
        "Bank branch or online today."
    )
    flags = keyword_flags(text)
    assert flags["states_payment_amount"], "payment amount must be detected"
    profile = profile_from_advertiser(
        {"type": "bank", "fdic_insured": True}, flags=flags
    )
    assert "1026" in gate(profile).parts


# --------------------------------------------------------------------------
# fail-open
# --------------------------------------------------------------------------


def test_unknown_advertiser_type_fails_open():
    """An unseen type must not silently hide a regulation.

    A mortgage broker, a fintech on a partner bank, a savings-and-loan holding
    company: the gate does not guess. It searches everything and says so.
    """
    result = gate(mk("fintech_on_partner_bank", is_credit_product=True))
    assert result.failed_open
    assert set(result.parts) == set(ALL_PARTS)
    assert any("not one of" in note for note in result.included)


def test_no_matching_rule_fails_open_rather_than_returning_nothing():
    """A goodwill post by a nonbank matches no scope test.

    Searching nothing would show an empty screen with no explanation, which is
    worse than searching everything.
    """
    result = gate(mk("nonbank"))
    assert result.failed_open
    assert set(result.parts) == set(ALL_PARTS)


def test_fail_open_is_explained_to_the_reviewer():
    result = gate(mk("unknown_type"))
    assert result.included, "fail-open must carry a reviewer-facing explanation"
    assert "hidden" in " ".join(result.included).lower()


# --------------------------------------------------------------------------
# full truth table
# --------------------------------------------------------------------------

_PRODUCTS = ["is_deposit_product", "is_credit_product", "is_mortgage", None]


@pytest.mark.parametrize(
    "advertiser_type,fdic,ncua,product",
    list(itertools.product(KNOWN_ADVERTISER_TYPES, [True, False], [True, False], _PRODUCTS)),
)
def test_truth_table_is_total_and_self_consistent(advertiser_type, fdic, ncua, product):
    """Every combination resolves, and every exclusion carries its source."""
    flags = {product: True} if product else {}
    result = gate(mk(advertiser_type, fdic=fdic, ncua=ncua, **flags))

    assert result.parts, "the gate must never return an empty scope"
    assert set(result.parts) <= set(ALL_PARTS)

    if not result.failed_open:
        # Every rule is accounted for exactly once, and each note cites a source.
        assert len(result.included) + len(result.excluded) == len(RULES)
        for note in result.included + result.excluded:
            assert "12 CFR" in note, f"note without a source citation: {note}"

    # Insurance-driven parts require the matching flag, always.
    if "328" in result.parts and not result.failed_open:
        assert fdic
    if "740" in result.parts and not result.failed_open:
        assert ncua and advertiser_type == "credit_union"


def test_every_rule_has_a_source_and_a_rationale():
    for rule in RULES:
        assert rule.source.startswith("12 CFR"), rule.part
        assert len(rule.rationale) > 20, rule.part
        assert rule.explain(True) != rule.explain(False)


def test_savings_association_is_treated_as_a_depository():
    """A savings association is a depository institution and not a credit
    union, so Reg DD reaches it. The one inference beyond the literal text.
    """
    result = gate(mk("savings_association", fdic=True, is_deposit_product=True))
    assert "1030" in result.parts
    assert "328" in result.parts
    assert "740" not in result.parts


# --------------------------------------------------------------------------
# keyword flags -- the only classifier, and the gate runs on them
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text,flag",
    [
        ("New high-yield savings: 5.00% APY!", "states_apy"),
        ("Earn 4.75% on our 12-month certificate", "states_rate_of_return"),
        ("only $349/month", "states_payment_amount"),
        ("30-year fixed from 5.25%", "states_credit_terms"),
        ("Lowest mortgage rates in the state", "is_mortgage"),
        ("Open Example Bank Free Checking today", "is_deposit_product"),
        ("No strings attached!", "claims_free"),
        ("Our Executive Auto Loan is built for professionals", "is_credit_product"),
        ("Member FDIC.", "has_insurance_statement"),
        ("Federally insured by NCUA", "has_insurance_statement"),
        ("Students and recent grads should look elsewhere.", "mentions_applicant_class"),
        ("overdraft protection available", "mentions_overdraft"),
    ],
)
def test_keyword_flags_detect_the_sample_phrasings(text, flag):
    assert keyword_flags(text)[flag], f"{flag!r} not detected in {text!r}"


def test_context_field_is_scanned_too():
    """Ad ``a2``'s ``$8 monthly maintenance fee`` is in the reviewer context,
    and it is the only reason ``1030.8(a)(2)`` applies at all.
    """
    flags = keyword_flags(
        "Open Example Bank Free Checking today. No strings attached! Member FDIC.",
        "The account has an $8 monthly maintenance fee, waived with direct deposit.",
    )
    assert flags["claims_free"]
    assert flags["is_deposit_product"]


def test_keyword_flags_returns_every_flag_key():
    """Callers union these with model output; missing keys would silently drop."""
    from app.applicability import TOPIC_FLAGS

    assert set(keyword_flags("anything")) == set(TOPIC_FLAGS)


def test_goodwill_post_sets_no_product_flags():
    """Ad ``a4`` must not be forced into a product category."""
    flags = keyword_flags(
        "Happy Fourth of July from all of us at Example Bank! 🎆 Our branches "
        "will be closed Friday. Member FDIC."
    )
    assert not flags["states_apy"]
    assert not flags["is_mortgage"]
    assert not flags["states_payment_amount"]
    assert flags["has_insurance_statement"]


def test_profile_properties():
    p = profile_from_advertiser(
        {"type": "bank", "fdic_insured": True}, flags={"states_apy": True}
    )
    assert p.is_deposit_ad
    assert not p.is_credit_ad
    assert p.recognised
    assert p.flag("states_apy")
    assert not p.flag("nonexistent")


def test_product_type_drives_scope_without_flags():
    """The profile call returns a product type; it alone must be sufficient."""
    p = AdProfile(advertiser_type="bank", fdic_insured=True, product_type="mortgage")
    assert p.is_credit_ad
    assert "1014" in gate(p).parts
