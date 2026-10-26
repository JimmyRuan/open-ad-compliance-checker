# Ad compliance check — all seven sample ads

Generated 2026-10-26 02:38 UTC · mode: **verdicts** · model `gpt-5`

This output is **advisory**: it surfaces provisions for a human reviewer
and does not assert a legal conclusion. Scope is exactly the 25 sections
in `data/regulations.json`.

---

## `a1` — Example Bank (bank, instagram)

> Drive off in a new SUV for only $349/month! 🚙 Apply at any Example Bank branch or online today.

**Regulations searched:** 1026, 1002, 328  
**Topic flags:** states_payment_amount, is_credit_product, names_institution  
**Candidates retrieved:** 24

**Excluded by the gate:**

- Regulation DD (1030) excluded: it applies only where the advertiser is a depository institution other than a credit union and the advertisement concerns a deposit account, which this submission does not meet [12 CFR 1030.1(c)]
- Regulation N (1014) excluded: it applies only where the advertisement is a commercial communication about a mortgage credit product; Reg N reaches any person, bank or not, which this submission does not meet [12 CFR 1014.1]
- NCUA Part 740 (740) excluded: it applies only where the advertiser is a federally insured credit union, so the accuracy and official-advertising-statement rules apply, which this submission does not meet [12 CFR 740.1]

**Overall:** Because the ad states a monthly payment for closed-end auto financing, other 12 CFR 1026.24(d)(2) disclosures (such as the APR and, if applicable, downpayment) may also be required, though those specific provisions were not included in the candidate list. If the offer were actually a lease, Regulation M would apply instead.

### May violate — [12 CFR 1026.24(d)(2)(ii)](https://www.ecfr.gov/current/title-12/section-1026.24#p-1026.24(d)(2)(ii))

*Regulation Z, CFPB — Advertising.*

Because the ad states a triggering term, it must also state the terms of repayment reflecting obligations over the full term; the ad lacks any repayment terms.

> The terms of repayment, which reflect the repayment obligations over the full term of the loan, including any balloon payment.

### May violate — [12 CFR 1026.24(d)(1)(iii)](https://www.ecfr.gov/current/title-12/section-1026.24#p-1026.24(d)(1)(iii))

*Regulation Z, CFPB — Advertising.*

By stating the amount of a payment, the ad triggers the requirement to include the (d)(2) disclosures; none of those additional terms are provided.

Evidence from the ad: “$349/month”

> The amount of any payment.

### Appears met — [12 CFR 328.6(e)(1)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(e)(1))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

This prohibits using the FDIC advertising statement in ads relating solely to non-deposit products; the auto financing ad does not include any FDIC-insurance statement.

Evidence from the ad: “Drive off in a new SUV for only $349/month!”

> Non-deposit product advertisements. Except as provided in paragraph (e)(3) of this section, an insured depository institution shall not include the official advertising statement, or any other statement or symbol which implies or suggests the existence of Federal deposit insurance, in any advertisement relating solely to non-deposit products.

---

## `a2` — Example Bank (bank, facebook)

> Open Example Bank Free Checking today. No strings attached! Member FDIC.

*Reviewer context:* The account has an $8 monthly maintenance fee, waived with direct deposit.

**Regulations searched:** 1026, 1030, 1002, 328  
**Topic flags:** states_payment_amount, is_deposit_product, claims_free, names_institution, has_insurance_statement  
**Candidates retrieved:** 24

**Excluded by the gate:**

- Regulation N (1014) excluded: it applies only where the advertisement is a commercial communication about a mortgage credit product; Reg N reaches any person, bank or not, which this submission does not meet [12 CFR 1014.1]
- NCUA Part 740 (740) excluded: it applies only where the advertiser is a federally insured credit union, so the accuracy and official-advertising-statement rules apply, which this submission does not meet [12 CFR 740.1]

**Overall:** Outside these candidates, UDAP/Section 5 concerns could also be implicated by “Free”/“No strings attached!” claims, but those authorities are out of scope here.

### May violate — [12 CFR 1030.8(a)(2)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(a)(2))

*Regulation DD, CFPB — Advertising.*

The ad describes the account as “Free,” but a monthly maintenance fee may be imposed unless waived, which the provision prohibits.

Evidence from the ad: “Free Checking”

> Refer to or describe an account as “free” or “no cost” (or contain a similar term) if any maintenance or activity fee may be imposed on the account. The word “profit” shall not be used in referring to interest paid on an account.

### May violate — [12 CFR 1030.8(a)(1)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(a)(1))

*Regulation DD, CFPB — Advertising.*

Saying “No strings attached!” alongside “Free Checking” is likely misleading because the account may carry a monthly maintenance fee unless conditions are met, misrepresenting the deposit contract.

Evidence from the ad: “No strings attached!”

> Be misleading or inaccurate or misrepresent a depository institution's deposit contract; or

### Unclear — needs a reviewer — [12 CFR 328.6(b)(2)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(b)(2))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

When the official advertising statement is used, it must be clearly legible; the ad’s format/size is not provided, so legibility cannot be assessed from the record.

> Size and print. The official advertising statement shall be of such size and print to be clearly legible. If the symbol of the Corporation is used as the official advertising statement, and the symbol must be reduced to such proportions that the two lines of smaller type above and below “FDIC” are indistinct and illegible, those lines of smaller type may be blocked out or dropped.

### Appears met — [12 CFR 328.6(c)(1)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(c)(1))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

This ad promotes a deposit product and includes the bank’s name, so the official advertising statement is required; “Member FDIC” satisfies this requirement via the short title option.

Evidence from the ad: “Member FDIC.”

Caveat: Some may view 12 CFR 328.6(d)(10) as exempting certain ads from requiring the statement; however, the statement is included here regardless.

> General requirement. Except as provided in paragraph (d) of this section, each insured depository institution shall include the official advertising statement prescribed in paragraph (b) of this section in all advertisements that either promote deposit products and services or promote non-specific banking products and services offered by the institution. For purposes of this section, an advertisement promotes non-specific banking products and services if it includes the name of the insured depository institution but does not list or describe particular products or services offered by the insti

### Appears met — [12 CFR 328.6(b)(1)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(b)(1))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

The ad uses “Member FDIC,” which is one of the permitted short titles for the official advertising statement.

Evidence from the ad: “Member FDIC.”

> Optional short title and symbol. The short title “Member of FDIC”, “Member FDIC”, “FDIC-Insured”, or a reproduction of the symbol of the Corporation (as described in § 328.2(b)), may be used by insured depository institutions at their option as the official advertising statement.

---

## `a3` — Example Federal Credit Union (credit_union, instagram)

> Earn 4.75% on our 12-month certificate! 📈 Open yours at Example FCU this week.

**Regulations searched:** 740  
**Topic flags:** states_rate_of_return, is_deposit_product, names_institution  
**Candidates retrieved:** 24

**Excluded by the gate:**

- Regulation Z (1026) excluded: it applies only where the advertisement is for consumer credit; Reg Z reaches any person who offers or extends consumer credit, regardless of charter, which this submission does not meet [12 CFR 1026.1(c)]
- Regulation DD (1030) excluded: it applies only where the advertiser is a depository institution other than a credit union and the advertisement concerns a deposit account, which this submission does not meet [12 CFR 1030.1(c)]
- Regulation B (1002) excluded: it applies only where the advertiser is a creditor and the advertisement concerns credit, so the prohibition on discouraging applicants applies, which this submission does not meet [12 CFR 1002.4]
- Regulation N (1014) excluded: it applies only where the advertisement is a commercial communication about a mortgage credit product; Reg N reaches any person, bank or not, which this submission does not meet [12 CFR 1014.1]
- FDIC Part 328 (328) excluded: it applies only where the advertiser is an FDIC-insured depository institution, so the advertising-statement rules apply to its advertisements, which this submission does not meet [12 CFR 328.1, 328.6(a)]

**Overall:** The ad promotes a rate for a 12‑month certificate; Truth in Savings (Regulation DD/12 CFR 707.8) advertising rules may be implicated (e.g., APY disclosures and additional terms), but no Reg DD candidates were provided for assessment here.

### May violate — [12 CFR 740.5(a)](https://www.ecfr.gov/current/title-12/section-740.5#p-740.5(a))

*NCUA Part 740, NCUA — Requirements for the official advertising statement.*

Insured credit unions must include the official advertising statement in all advertisements unless a paragraph (c) exemption applies. This Instagram ad relates to a share certificate and includes no official advertising statement.

Caveat: If a 12 CFR 740.5(c) exemption were found to apply (e.g., impractical items), the obligation would not apply; none appears to fit an Instagram post about member accounts.

> Each insured credit union must include the official advertising statement, prescribed in paragraph (b) of this section, in all of its advertisements, including on its main internet page, except as provided in paragraph (c) of this section.

### Unclear — needs a reviewer — [12 CFR 740.2](https://www.ecfr.gov/current/title-12/section-740.2)

*NCUA Part 740, NCUA — Accuracy of advertising.*

This provision applies to all insured credit union advertising and prohibits inaccurate or deceptive representations. The ad makes a rate claim, but there is no evidence in the text itself that the claim is inaccurate or deceptive.

Evidence from the ad: “Earn 4.75% on our 12-month certificate! 📈 Open yours at Example FCU this week.”

> No insured credit union may use any advertising (which includes print, electronic, or broadcast media, displays and signs, stationery, and other promotional material) or make any representation which is inaccurate or deceptive in any particular, or which in any way misrepresents its services, contracts, or financial condition, or which violates the requirements of § 707.8 of this subchapter, if applicable. This provision does not prohibit an insured credit union from using a trade name or a name other than its official charter name in advertising or signage, so long as it uses its official cha

---

## `a4` — Example Bank (bank, facebook)

> Happy Fourth of July from all of us at Example Bank! 🎆 Our branches will be closed Friday. Member FDIC.

**Regulations searched:** 328  
**Topic flags:** names_institution, has_insurance_statement  
**Candidates retrieved:** 24

**Excluded by the gate:**

- Regulation Z (1026) excluded: it applies only where the advertisement is for consumer credit; Reg Z reaches any person who offers or extends consumer credit, regardless of charter, which this submission does not meet [12 CFR 1026.1(c)]
- Regulation DD (1030) excluded: it applies only where the advertiser is a depository institution other than a credit union and the advertisement concerns a deposit account, which this submission does not meet [12 CFR 1030.1(c)]
- Regulation B (1002) excluded: it applies only where the advertiser is a creditor and the advertisement concerns credit, so the prohibition on discouraging applicants applies, which this submission does not meet [12 CFR 1002.4]
- Regulation N (1014) excluded: it applies only where the advertisement is a commercial communication about a mortgage credit product; Reg N reaches any person, bank or not, which this submission does not meet [12 CFR 1014.1]
- NCUA Part 740 (740) excluded: it applies only where the advertiser is a federally insured credit union, so the accuracy and official-advertising-statement rules apply, which this submission does not meet [12 CFR 740.1]

### Unclear — needs a reviewer — [12 CFR 328.6(b)(2)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(b)(2))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

The official advertising statement must be clearly legible; in a social media context, legibility depends on formatting not shown in the text provided.

Evidence from the ad: “Member FDIC.”

> Size and print. The official advertising statement shall be of such size and print to be clearly legible. If the symbol of the Corporation is used as the official advertising statement, and the symbol must be reduced to such proportions that the two lines of smaller type above and below “FDIC” are indistinct and illegible, those lines of smaller type may be blocked out or dropped.

### Appears met — [12 CFR 328.6(c)(1)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(c)(1))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

This Facebook post names the insured depository institution without describing specific products, making it a non-specific banking advertisement that must include the official advertising statement; the post includes it.

Evidence from the ad: “Happy Fourth of July from all of us at Example Bank! 🎆 Our branches will be closed Friday. Member FDIC.”

Caveat: Paragraph (d)(10) identifies a category of ads (those that state FDIC membership) that do not require the official advertising statement, which may remove the obligation here.

> General requirement. Except as provided in paragraph (d) of this section, each insured depository institution shall include the official advertising statement prescribed in paragraph (b) of this section in all advertisements that either promote deposit products and services or promote non-specific banking products and services offered by the institution. For purposes of this section, an advertisement promotes non-specific banking products and services if it includes the name of the insured depository institution but does not list or describe particular products or services offered by the insti

### Appears met — [12 CFR 328.6(b)(1)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(b)(1))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

The provision allows the short title “Member FDIC” to be used as the official advertising statement; the ad uses that exact short title.

Evidence from the ad: “Member FDIC.”

> Optional short title and symbol. The short title “Member of FDIC”, “Member FDIC”, “FDIC-Insured”, or a reproduction of the symbol of the Corporation (as described in § 328.2(b)), may be used by insured depository institutions at their option as the official advertising statement.

### Appears met — [12 CFR 328.6(d)(10)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(d)(10))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

This provision describes a category of advertisements that do not require use of the official advertising statement; the ad contains a statement that the institution is a member of the FDIC.

Evidence from the ad: “Member FDIC.”

> Advertisements which contain a statement to the effect that the depository institution is a member of the Federal Deposit Insurance Corporation, or that the depository institution is insured by the Federal Deposit Insurance Corporation, or that its deposits or depositors are insured by the Federal Deposit Insurance Corporation to at least the standard maximum deposit insurance amount (as defined in § 330.1(o)) for each depositor.

---

## `a5` — Example Home Lending (nonbank, x)

> Lowest mortgage rates in the state, GUARANTEED. 30-year fixed from 5.25%. Call Example Home Lending today!

**Regulations searched:** 1026, 1002, 1014  
**Topic flags:** states_rate_of_return, states_credit_terms, is_mortgage, is_credit_product  
**Candidates retrieved:** 24

**Excluded by the gate:**

- Regulation DD (1030) excluded: it applies only where the advertiser is a depository institution other than a credit union and the advertisement concerns a deposit account, which this submission does not meet [12 CFR 1030.1(c)]
- FDIC Part 328 (328) excluded: it applies only where the advertiser is an FDIC-insured depository institution, so the advertising-statement rules apply to its advertisements, which this submission does not meet [12 CFR 328.1, 328.6(a)]
- NCUA Part 740 (740) excluded: it applies only where the advertiser is a federally insured credit union, so the accuracy and official-advertising-statement rules apply, which this submission does not meet [12 CFR 740.1]

**Overall:** The superlative/guarantee claim (“Lowest mortgage rates in the state, GUARANTEED.”) may raise issues under the Mortgage Acts and Practices—Advertising (Regulation N) and general UDAAP standards, but no Regulation N provisions were provided in the candidate list.

### May violate — [12 CFR 1026.24(c)](https://www.ecfr.gov/current/title-12/section-1026.24#p-1026.24(c))

*Regulation Z, CFPB — Advertising.*

The ad states a rate but does not state it as an “annual percentage rate” using that term, as required for dwelling-secured credit; no APR is disclosed.

Evidence from the ad: “30-year fixed from 5.25%.”

> Advertisement of rate of finance charge. If an advertisement states a rate of finance charge, it shall state the rate as an “annual percentage rate,” using that term. If the annual percentage rate may be increased after consummation, the advertisement shall state that fact. If an advertisement is for credit not secured by a dwelling, the advertisement shall not state any other rate, except that a simple annual rate or periodic rate that is applied to an unpaid balance may be stated in conjunction with, but not more conspicuously than, the annual percentage rate. If an advertisement is for cred

### May violate — [12 CFR 1026.24(d)(2)(iii)](https://www.ecfr.gov/current/title-12/section-1026.24#p-1026.24(d)(2)(iii))

*Regulation Z, CFPB — Advertising.*

By stating the period of repayment (“30-year”), the ad triggers a requirement to state the “annual percentage rate,” using that term; no APR disclosure appears.

Evidence from the ad: “30-year fixed from 5.25%.”

> The “annual percentage rate,” using that term, and, if the rate may be increased after consummation, that fact.

### Unclear — needs a reviewer — [12 CFR 1026.24(a)](https://www.ecfr.gov/current/title-12/section-1026.24#p-1026.24(a))

*Regulation Z, CFPB — Advertising.*

The ad states specific credit terms; whether those terms are actually available cannot be determined from the ad alone.

Evidence from the ad: “30-year fixed from 5.25%.”

> Actually available terms. If an advertisement for credit states specific credit terms, it shall state only those terms that actually are or will be arranged or offered by the creditor.

---

## `a6` — Example Bank (bank, linkedin)

> Our Executive Auto Loan is built for established professionals. Students and recent grads should look elsewhere.

**Regulations searched:** 1026, 1002, 328  
**Topic flags:** is_credit_product, mentions_applicant_class  
**Candidates retrieved:** 24

**Excluded by the gate:**

- Regulation DD (1030) excluded: it applies only where the advertiser is a depository institution other than a credit union and the advertisement concerns a deposit account, which this submission does not meet [12 CFR 1030.1(c)]
- Regulation N (1014) excluded: it applies only where the advertisement is a commercial communication about a mortgage credit product; Reg N reaches any person, bank or not, which this submission does not meet [12 CFR 1014.1]
- NCUA Part 740 (740) excluded: it applies only where the advertiser is a federally insured credit union, so the accuracy and official-advertising-statement rules apply, which this submission does not meet [12 CFR 740.1]

### Unclear — needs a reviewer — [12 CFR 1002.4(b)](https://www.ecfr.gov/current/title-12/section-1002.4#p-1002.4(b))

*Regulation B, CFPB — General rules.*

Reg B prohibits discouraging statements suggesting denial or worse terms due to a prohibited-basis characteristic. “Students and recent grads” could be perceived as age-related, but the ad targets occupational status, not expressly age.

Evidence from the ad: “Students and recent grads should look elsewhere.”

Caveat: If interpreted as targeting occupation/experience rather than age, it may not implicate a prohibited basis; if viewed as an age proxy, it could raise concerns.

> Discouragement. A creditor shall not make any oral or written statement, in advertising or otherwise, directed at applicants or prospective applicants that the creditor knows or should know would cause a reasonable person to believe that the creditor would deny, or would grant on less favorable terms, a credit application by the applicant or prospective applicant because of the applicant or prospective applicant's prohibited basis characteristic(s). For purposes of this paragraph (b), oral or written statements are spoken or written words, or visual images such as symbols, photographs, or vide

---

## `a7` — Example Bank (bank, instagram)

> New high-yield savings: 5.00% APY! Rate may change after the account is opened. $500 minimum balance to earn the APY. Fees could reduce earnings. Member FDIC.

**Regulations searched:** 1030, 328  
**Topic flags:** states_rate_of_return, states_apy, is_deposit_product, has_insurance_statement  
**Candidates retrieved:** 24

**Excluded by the gate:**

- Regulation Z (1026) excluded: it applies only where the advertisement is for consumer credit; Reg Z reaches any person who offers or extends consumer credit, regardless of charter, which this submission does not meet [12 CFR 1026.1(c)]
- Regulation B (1002) excluded: it applies only where the advertiser is a creditor and the advertisement concerns credit, so the prohibition on discouraging applicants applies, which this submission does not meet [12 CFR 1002.4]
- Regulation N (1014) excluded: it applies only where the advertisement is a commercial communication about a mortgage credit product; Reg N reaches any person, bank or not, which this submission does not meet [12 CFR 1014.1]
- NCUA Part 740 (740) excluded: it applies only where the advertiser is a federally insured credit union, so the accuracy and official-advertising-statement rules apply, which this submission does not meet [12 CFR 740.1]

### May violate — [12 CFR 1030.8(b)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(b))

*Regulation DD, CFPB — Advertising.*

When stating a rate of return, the ad may use “APY” only if the term “annual percentage yield” appears at least once; the ad uses only the abbreviation and never spells it out.

Evidence from the ad: “5.00% APY”

> Permissible rates. If an advertisement states a rate of return, it shall state the rate as an “annual percentage yield” using that term. (The abbreviation “APY” may be used provided the term “annual percentage yield” is stated at least once in the advertisement.) The advertisement shall not state any other rate, except that the “interest rate,” using that term, may be stated in conjunction with, but not more conspicuously than, the annual percentage yield to which it relates.

### May violate — [12 CFR 1030.8(c)(2)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(c)(2))

*Regulation DD, CFPB — Advertising.*

When an APY is stated, the ad must state the period the APY will be offered or that it is accurate as of a specified date; the ad includes neither.

> Time annual percentage yield is offered. The period of time the annual percentage yield will be offered, or a statement that the annual percentage yield is accurate as of a specified date.

### Unclear — needs a reviewer — [12 CFR 1030.8(c)(4)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(c)(4))

*Regulation DD, CFPB — Advertising.*

This disclosure is required only if the minimum opening deposit exceeds the minimum balance to obtain the APY; the ad does not indicate the opening deposit amount.

> Minimum opening deposit. The minimum deposit required to open the account, if it is greater than the minimum balance necessary to obtain the advertised annual percentage yield.

### Unclear — needs a reviewer — [12 CFR 1030.8(a)(1)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(a)(1))

*Regulation DD, CFPB — Advertising.*

Ads must not be misleading or inaccurate; nothing in the ad indicates a misrepresentation, but sufficiency cannot be determined from the ad alone.

> Be misleading or inaccurate or misrepresent a depository institution's deposit contract; or

### Appears met — [12 CFR 1030.8(c)(3)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(c)(3))

*Regulation DD, CFPB — Advertising.*

Because an APY is stated, the ad must disclose the minimum balance required to obtain the APY; it does so clearly.

Evidence from the ad: “$500 minimum balance to earn the APY.”

> Minimum balance. The minimum balance required to obtain the advertised annual percentage yield. For tiered-rate accounts, the minimum balance required for each tier shall be stated in close proximity and with equal prominence to the applicable annual percentage yield.

### Appears met — [12 CFR 1030.8(c)(1)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(c)(1))

*Regulation DD, CFPB — Advertising.*

For variable-rate accounts, an APY ad must state that the rate may change after opening; the ad includes that statement.

Evidence from the ad: “Rate may change after the account is opened.”

> Variable rates. For variable-rate accounts, a statement that the rate may change after the account is opened.

### Appears met — [12 CFR 1030.8(c)(5)](https://www.ecfr.gov/current/title-12/section-1030.8#p-1030.8(c)(5))

*Regulation DD, CFPB — Advertising.*

When an APY is stated, the ad must state that fees could reduce earnings; it does so.

Evidence from the ad: “Fees could reduce earnings.”

> Effect of fees. A statement that fees could reduce the earnings on the account.

### Appears met — [12 CFR 328.6(c)(1)](https://www.ecfr.gov/current/title-12/section-328.6#p-328.6(c)(1))

*FDIC Part 328, FDIC — Official advertising statement requirements.*

Ads promoting deposit products must include the official advertising statement; the ad includes “Member FDIC.”

Evidence from the ad: “Member FDIC.”

Caveat: C18 lists ads that state the institution is a member of the FDIC as not requiring the official advertising statement; reviewer may treat this phrase as satisfying or falling under that exemption.

> General requirement. Except as provided in paragraph (d) of this section, each insured depository institution shall include the official advertising statement prescribed in paragraph (b) of this section in all advertisements that either promote deposit products and services or promote non-specific banking products and services offered by the institution. For purposes of this section, an advertisement promotes non-specific banking products and services if it includes the name of the insured depository institution but does not list or describe particular products or services offered by the insti

---

_Total wall clock: 166.9s for 7 ads._
