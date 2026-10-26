# Assumptions

The brief says to assume and write it down rather than ask. These are the calls that change the output, so they are the ones worth arguing with.

## Legal and interpretive

1.  **A social post is not "electronic media" under Reg DD `1030.8(e)(1)`.** `(e)(1)` exempts "broadcast or electronic media, such as television or radio" from several `(c)` disclosures, including `(c)(2)` — the period an APY is offered. That is the single most consequential assumption here: if an Instagram post *is* electronic media, ad `a7`'s only real gap disappears and it is compliant. My reading is that the enumerated examples are time-constrained push media where a scrolling disclosure is impractical, which a persistent, unbounded social post is not. The tool surfaces this as a caveat on the finding rather than silently picking a side.
2.  **Quoting a monthly payment makes an ad a credit advertisement.** "The amount of any payment" is itself a Reg Z triggering term under `1026.24(d)(1)(iii)`, so ad `a1` ("$349/month") is in Reg Z scope even though it names no loan, no financing and no APR. Without this, the one sample ad that most clearly violates Reg Z would have had Reg Z excluded.
3.  **A savings association is a depository institution and is not a credit union**, so Reg DD reaches it. The only inference in the gate beyond the corpus's literal scope text.
4.  **Reviewer `context` is true and material.** Ad `a2`'s `$8 monthly maintenance fee` exists only in the context field, and it is the whole reason `1030.8(a)(2)` applies. The tool treats context as fact about the product, not as ad copy — so it is never quoted as `ad_evidence`.
5.  **Advertiser type is supplied, not inferred.** The reviewer picks it; the tool does not try to detect charter type from ad text.
6.  **"Advisory, not adjudicative."** Every output is framed as provisions for a human reviewer. `unclear` is a legitimate verdict, and a definition or scope provision is marked context rather than a finding.

## Technical

7.  **eCFR's `#p-` paragraph anchor convention is stable** (e.g. `…/section-1026.24#p-1026.24(d)(2)(iii)`). Verified by clicking, not by fetching — eCFR blocks automated requests. At depth 0 the link falls back to the section URL, which is always valid.
8.  **The corpus is the whole world.** Scope is exactly the 25 sections in `data/regulations.json` as of 2026-10-05. The model is told so and instructed to put anything outside it in `overall_note` instead of inventing a citation. Known gaps: NCUA Part 707, Reg Z official interpretations, UDAAP, FTC Act §5, Reg M.
9.  **The LLM is optional, so retrieval-only must be good.** With no `OPENAI_API_KEY` the app still returns precise citations, provision text and links. The applicability gate runs on keyword flags and behaves identically either way.
10.  **Model output is not trusted.** A finding is dropped unless it echoes a candidate handle we supplied *and* its citation matches that handle. This is also the prompt-injection defence: ad copy is attacker-controllable text flowing into a prompt, and no injection can produce a citation that was not in the candidate list.
11.  **Latency is acceptable at ~20s per check** with verdicts on, because reasoning tokens dominate. `LLM_ASSESS_EFFORT` trades that against depth; retrieval alone is 0.83s.
12.  **Synthetic ads are representative enough** to drive design, but seven ads are not an eval set, and three retrieval parameters are tuned against them. That is the first thing I would replace.