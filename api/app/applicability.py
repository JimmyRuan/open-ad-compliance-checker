"""Which regulations are in scope for this advertiser and this ad.

This is the deterministic gate that runs **before** retrieval, and it is the
honest answer to "how do you decide which provisions to show and which to leave
out".  Every rule is derived from the corpus's own scope text and carries that
citation in the rule itself, so each exclusion is defensible rather than a
hand-wave -- and so the reviewer can be told *which paragraph* caused a
regulation to be left out.

At 25 sections this trims noise.  At 300 regulations it is what makes the
problem tractable at all: it is the difference between an ANN search over 10^6
nodes and one over 10^4 (see ``store.search_semantic``).

**The gate is the highest-risk decision in the system, so it fails open.**  A
retrieval miss is recoverable -- a human scanning candidates may still spot the
provision.  A gate miss is not: an excluded regulation is invisible to every
downstream stage, including the reviewer.  So an advertiser type this module
does not recognise disables the gate entirely rather than guessing, and every
exclusion is recorded with the rule that caused it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

#: The topics a rule or an expansion query can key off. Lives here because the
#: gate is what consumes them; ``retrieve.FLAG_QUERIES`` keys its expansion
#: table off the same names, so one vocabulary drives scope and search alike.
TOPIC_FLAGS: tuple[str, ...] = (
    "states_rate_of_return",
    "states_apy",
    "states_payment_amount",
    "states_credit_terms",
    "is_mortgage",
    "is_deposit_product",
    "is_credit_product",
    "claims_free",
    "names_institution",
    "has_insurance_statement",
    "mentions_overdraft",
    "mentions_applicant_class",
)

#: Advertiser types the gate understands.  Anything else fails open.
KNOWN_ADVERTISER_TYPES = ("bank", "credit_union", "nonbank", "savings_association")

#: Types that are depository institutions for Reg DD purposes.  A savings
#: association is a depository institution and is *not* a credit union, so Reg
#: DD reaches it -- the one inference here beyond the literal text.
_DEPOSITORY = ("bank", "savings_association")


@dataclass(frozen=True)
class Rule:
    """One gate rule: a regulation part, and the condition for including it."""

    part: str
    regulation: str
    source: str
    """The paragraph in the corpus this rule encodes."""

    rationale: str
    predicate: Callable[["AdProfile"], bool]

    def explain(self, applies: bool) -> str:
        """One line a reviewer can check against the cited paragraph.

        The two directions need different grammar: ``rationale`` states the
        condition for *including* the regulation, so an exclusion has to say
        the condition was not met rather than asserting it -- otherwise the
        line reads as its own contradiction ("excluded: the advertiser is a
        depository institution...").
        """
        if applies:
            return f"{self.regulation} ({self.part}) in scope: {self.rationale} [{self.source}]"
        return (
            f"{self.regulation} ({self.part}) excluded: it applies only where "
            f"{self.rationale}, which this submission does not meet [{self.source}]"
        )


@dataclass
class AdProfile:
    """Everything the gate needs to know about one submission.

    ``flags`` are topic flags produced either by the profile model call or by
    the keyword pass below, so the gate behaves identically with no API key.
    """

    advertiser_type: str
    fdic_insured: bool = False
    ncua_insured: bool = False
    channel: str = ""
    product_type: str = "unknown"
    flags: dict[str, bool] = field(default_factory=dict)

    def flag(self, name: str) -> bool:
        return bool(self.flags.get(name))

    @property
    def recognised(self) -> bool:
        return self.advertiser_type in KNOWN_ADVERTISER_TYPES

    @property
    def is_credit_ad(self) -> bool:
        """Whether this is an advertisement for consumer credit.

        ``states_payment_amount`` is in this list deliberately, and it is the
        case that caught a real gate miss during the build.  Ad ``a1`` --
        *"Drive off in a new SUV for only $349/month! Apply at any Example Bank
        branch or online today."* -- names no credit product at all: no "loan",
        no "financing", no "APR".  Without a payment amount counting as a
        credit signal, Reg Z was excluded for the one ad in the sample that
        most clearly violates it, and nothing downstream could recover: an
        excluded regulation is invisible to retrieval, to the model, and to the
        reviewer.

        It is also the legally right reading.  "The amount of any payment" is
        itself a Reg Z triggering term under ``1026.24(d)(1)(iii)`` -- quoting a
        monthly payment is precisely the act that pulls an ad into ``(d)(2)``.
        """
        return (
            self.flag("is_credit_product")
            or self.flag("is_mortgage")
            or self.flag("states_credit_terms")
            or self.flag("states_payment_amount")
            or self.product_type
            in ("credit_card", "auto_loan", "mortgage", "home_equity", "other_credit")
        )

    @property
    def is_deposit_ad(self) -> bool:
        return (
            self.flag("is_deposit_product")
            or self.flag("states_apy")
            or self.flag("states_rate_of_return")
            or self.product_type in ("deposit_account", "time_deposit")
        )


# --------------------------------------------------------------------------
# the rules
# --------------------------------------------------------------------------

RULES: tuple[Rule, ...] = (
    Rule(
        part="1026",
        regulation="Regulation Z",
        source="12 CFR 1026.1(c)",
        rationale="the advertisement is for consumer credit; Reg Z reaches any "
        "person who offers or extends consumer credit, regardless of charter",
        predicate=lambda p: p.is_credit_ad,
    ),
    Rule(
        part="1030",
        regulation="Regulation DD",
        source="12 CFR 1030.1(c)",
        # The exclusion that matters for ad a3: Reg DD applies to depository
        # institutions "except for credit unions", by its own terms.  Not
        # inventing a Reg DD hit for a credit union to make the demo look
        # better; the corpus gap this leaves is named in DECISIONS.md.
        rationale="the advertiser is a depository institution other than a credit "
        "union and the advertisement concerns a deposit account",
        predicate=lambda p: p.advertiser_type in _DEPOSITORY and p.is_deposit_ad,
    ),
    Rule(
        part="1002",
        regulation="Regulation B",
        source="12 CFR 1002.4",
        rationale="the advertiser is a creditor and the advertisement concerns "
        "credit, so the prohibition on discouraging applicants applies",
        predicate=lambda p: p.is_credit_ad,
    ),
    Rule(
        part="1014",
        regulation="Regulation N",
        source="12 CFR 1014.1",
        rationale="the advertisement is a commercial communication about a "
        "mortgage credit product; Reg N reaches any person, bank or not",
        predicate=lambda p: p.flag("is_mortgage") or p.product_type == "mortgage",
    ),
    Rule(
        part="328",
        regulation="FDIC Part 328",
        source="12 CFR 328.1, 328.6(a)",
        rationale="the advertiser is an FDIC-insured depository institution, so "
        "the advertising-statement rules apply to its advertisements",
        predicate=lambda p: p.fdic_insured and p.advertiser_type in _DEPOSITORY,
    ),
    Rule(
        part="740",
        regulation="NCUA Part 740",
        source="12 CFR 740.1",
        rationale="the advertiser is a federally insured credit union, so the "
        "accuracy and official-advertising-statement rules apply",
        predicate=lambda p: p.advertiser_type == "credit_union" and p.ncua_insured,
    ),
)

ALL_PARTS: tuple[str, ...] = tuple(r.part for r in RULES)


@dataclass
class GateResult:
    parts: list[str]
    included: list[str]
    excluded: list[str]
    failed_open: bool = False

    @property
    def notes(self) -> list[str]:
        return self.included + self.excluded


def gate(profile: AdProfile, rules: Iterable[Rule] = RULES) -> GateResult:
    """Parts in scope for this submission, with an explanation for each.

    Fails open on an unrecognised advertiser type: an unseen type (a mortgage
    broker, a fintech on a partner bank) must not silently hide a regulation,
    so the whole corpus stays in scope and the reviewer is told why.
    """
    rules = tuple(rules)
    if not profile.recognised:
        return GateResult(
            parts=list(ALL_PARTS),
            included=[
                f"Advertiser type {profile.advertiser_type!r} is not one of "
                f"{', '.join(KNOWN_ADVERTISER_TYPES)}, so the applicability gate was "
                "disabled and every regulation in the corpus was searched. Nothing "
                "has been hidden from you, but precision will be lower."
            ],
            excluded=[],
            failed_open=True,
        )

    parts, included, excluded = [], [], []
    for rule in rules:
        if rule.predicate(profile):
            parts.append(rule.part)
            included.append(rule.explain(True))
        else:
            excluded.append(rule.explain(False))

    if not parts:
        # Nothing matched -- a goodwill post by a nonbank, say.  Searching
        # nothing would show the reviewer an empty screen with no explanation,
        # which is worse than searching everything.
        return GateResult(
            parts=list(ALL_PARTS),
            included=[
                "No regulation's scope test matched this submission, so every "
                "regulation in the corpus was searched rather than none."
            ],
            excluded=excluded,
            failed_open=True,
        )

    return GateResult(parts=parts, included=included, excluded=excluded)


# --------------------------------------------------------------------------
# keyword fallback for the topic flags
# --------------------------------------------------------------------------

#: Patterns behind ``keyword_flags``.  A classifier would produce better
#: flags, but the gate must work identically with no API key, so this
#: is a first-class code path rather than a stub -- the retrieval-only tier is
#: a product tier, not a crippled fallback.
_FLAG_PATTERNS: dict[str, tuple[str, ...]] = {
    "states_apy": (r"\bAPY\b", r"annual percentage yield"),
    "states_rate_of_return": (
        r"\b\d+(?:\.\d+)?\s*%",
        r"\bearn\b",
        r"\binterest\b",
        r"\byield\b",
        r"\bhigh[- ]yield\b",
    ),
    "states_payment_amount": (
        r"\$\s?[\d,]+(?:\.\d+)?\s*(?:/|per\s+)?\s*(?:mo\b|month|mth)",
        r"\bper month\b",
        r"\bmonthly payment\b",
        r"\ba month\b",
    ),
    "states_credit_terms": (
        r"\bAPR\b",
        r"\bdownpayment\b",
        r"\bdown payment\b",
        r"\bfinance charge\b",
        r"\b\d+[- ]year\b",
        r"\b\d+[- ]month\b.*\b(?:loan|financing)\b",
        r"\bterm of\b",
        r"\bfixed\b",
    ),
    "is_mortgage": (
        r"\bmortgage\b",
        r"\brefinanc",
        r"\bhome (?:loan|lending|equity)\b",
        r"\bHELOC\b",
        r"\b30[- ]year\b",
        r"\b15[- ]year\b",
    ),
    "is_deposit_product": (
        r"\bchecking\b",
        r"\bsavings\b",
        r"\bcertificate\b",
        r"\bCD\b",
        r"\bmoney market\b",
        r"\bdeposit\b",
        r"\baccount\b",
        r"\bshare draft\b",
    ),
    "is_credit_product": (
        r"\bloan\b",
        r"\bcredit card\b",
        r"\bfinanc(?:e|ing|ed)\b",
        r"\bborrow\b",
        r"\bmortgage\b",
        r"\blease\b",
        r"\bapply\b.*\bcredit\b",
        r"\bauto loan\b",
        # Vehicle and purchase framing: an ad that quotes a monthly figure to
        # "drive off in" something is a credit ad even when it never says so.
        r"\bdrive (?:off|home|away)\b",
        r"\b(?:new|used)\s+(?:car|truck|SUV|vehicle)\b",
    ),
    "claims_free": (
        r"\bfree\b",
        r"\bno cost\b",
        r"\bno fees?\b",
        r"\bno strings\b",
        r"\bcomplimentary\b",
    ),
    "names_institution": (r"\bbank\b", r"\bcredit union\b", r"\bFCU\b", r"\bN\.?A\.?\b"),
    "has_insurance_statement": (
        r"member\s+FDIC",
        r"FDIC[- ]insured",
        r"insured by NCUA",
        r"federally insured by",
        r"\bNCUA\b",
    ),
    "mentions_overdraft": (r"\boverdraft\b", r"\bcourtesy pay\b", r"\bNSF\b"),
    "mentions_applicant_class": (
        r"\bstudents?\b",
        r"\brecent grads?\b",
        r"\bgraduates?\b",
        r"\bseniors?\b",
        r"\bretirees?\b",
        r"\bestablished professionals?\b",
        r"\byoung\b",
        r"\bage\b",
        r"\belderly\b",
        r"\bmarried\b",
        r"\bnationality\b",
        r"\bmust be\b",
        r"\blook elsewhere\b",
    ),
}


def keyword_flags(text: str, context: str = "") -> dict[str, bool]:
    """Topic flags from the ad text, with no model call.

    Scans the ad and the reviewer context together: ad ``a2``'s ``$8 monthly
    maintenance fee`` lives in the context field, and it is what makes
    ``1030.8(a)(2)`` fire at all.
    """
    blob = f"{text}\n{context}"
    out: dict[str, bool] = {}
    for flag in TOPIC_FLAGS:
        patterns = _FLAG_PATTERNS.get(flag, ())
        out[flag] = any(
            re.search(p, blob, re.I) for p in patterns if isinstance(p, str)
        )
    return out


def profile_from_advertiser(
    advertiser: dict,
    *,
    channel: str = "",
    flags: dict[str, bool] | None = None,
    product_type: str = "unknown",
) -> AdProfile:
    return AdProfile(
        advertiser_type=str(advertiser.get("type", "unknown")),
        fdic_insured=bool(advertiser.get("fdic_insured")),
        ncua_insured=bool(advertiser.get("ncua_insured")),
        channel=channel,
        product_type=product_type,
        flags=flags or {},
    )
