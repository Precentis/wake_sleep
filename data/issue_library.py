"""Parametric issue library for the synthetic legal benchmark.

Each issue template plants verifiable facts into specific matter documents and returns
rubric criteria whose expected values are computed here (not by an LLM), so grading has
an objective answer key.

House standards (H*) are the firm's unwritten expectations of a good deliverable. They
are NOT disclosed in task instructions; they appear only in rubrics. They are the
learnable regularity a wake-sleep memory can pick up (as expert rubrics do in LAB).
"""

from __future__ import annotations

import calendar
import datetime as dt
import random
from dataclasses import dataclass, field
from typing import Any, Callable

HOUSE_STANDARDS: dict[str, str] = {
    "H1": "Opens with a short 'Bottom line' / executive summary stating the overall conclusion and the most important risks before the detailed analysis.",
    "H2": "Gives a pinpoint citation (document name and section/clause number) for every issue or finding.",
    "H3": "States each time period both as a duration and as a computed calendar date, and gives the number of days remaining from the deliverable date, showing the arithmetic.",
    "H4": "Independently recomputes every derived monetary figure (caps, adjustments, fees, allocations), shows the arithmetic, and flags any discrepancy with the figure stated in the documents.",
    "H5": "Expressly flags inconsistencies between documents (amounts, dates, periods or defined terms that differ across documents).",
    "H6": "Gives a concrete recommended action for each issue (what to request, amend or negotiate).",
    "H7": "Assigns a risk rating (High / Medium / Low) to each issue.",
    "H8": "Includes an 'Assumptions and open questions' section listing information that is missing or should be confirmed with the client.",
    "H9": "Where a defined term or clause is ambiguous, explains how each alternative reading would work.",
    "H10": "Checks whether computed deadlines fall on a weekend and adjusts them under the documents' Business Day definition.",
    "H11": "Identifies required third-party, board or regulatory consents/approvals and whether each has been obtained.",
    "H12": "Shows proposed drafting changes as before/after (current wording vs proposed wording) with a one-line rationale.",
}

TASK_TYPE_STANDARDS: dict[str, list[str]] = {
    "issues_list": ["H1", "H2", "H6", "H7", "H5"],
    "legal_memo": ["H1", "H2", "H8", "H9"],
    "contract_review": ["H2", "H6", "H7", "H11"],
    "redline": ["H12", "H2", "H9"],
    "due_diligence": ["H2", "H5", "H11", "H7"],
    "timeline_analysis": ["H3", "H10", "H2", "H1"],
    "legal_research": ["H1", "H8"],
}

TASK_TYPE_FAMILY = {
    "issues_list": "issues_identification",
    "legal_memo": "memo_drafting",
    "contract_review": "contract_review",
    "redline": "redline",
    "due_diligence": "due_diligence",
    "timeline_analysis": "timeline_analysis",
    "legal_research": "legal_research",
}

DELIVERABLE_ASK = {
    "issues_list": "Prepare an issues list for the supervising partner covering the matter documents.",
    "legal_memo": "Prepare a legal memo for the supervising partner analysing the key legal risks in the matter documents.",
    "contract_review": "Review the principal agreement against the other matter documents and report the problematic provisions.",
    "redline": "Prepare a redline note proposing amendments to the principal agreement to protect our client.",
    "due_diligence": "Prepare a due diligence findings report on the matter documents.",
    "timeline_analysis": "Prepare a timeline and deadlines analysis of all time-sensitive obligations in the matter documents.",
    "legal_research": "Prepare a short research note answering the client's question.",
}


def fmt_date(d: dt.date) -> str:
    return f"{d.day} {d.strftime('%B')} {d.year}"


def fmt_money(x: float, cur: str = "$") -> str:
    return f"{cur}{x:,.0f}"


def add_months(d: dt.date, n: int) -> dt.date:
    m = d.month - 1 + n
    y = d.year + m // 12
    m = m % 12 + 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def next_business_day(d: dt.date) -> dt.date:
    while d.weekday() >= 5:
        d += dt.timedelta(days=1)
    return d


@dataclass
class Planted:
    issue: str
    facts: dict[str, list[str]]           # doc -> fact sentences to embed (verbatim values)
    must_contain: dict[str, list[str]]    # doc -> literal strings that must appear
    criteria: list[str]                   # substantive rubric criteria
    standards: list[str] = field(default_factory=list)  # house standards this issue triggers
    standard_criteria: dict[str, str] = field(default_factory=dict)  # concrete H-criterion text
    kind: str = "qualitative"             # qualitative | numeric | date


# ---------------------------------------------------------------- context
def weekend_date_after(rng: random.Random, base: dt.date, months: int) -> dt.date:
    """Pick a base date near `base` such that base + months lands on a weekend."""
    for off in range(0, 40):
        b = base + dt.timedelta(days=off)
        if add_months(b, months).weekday() >= 5:
            return b
    return base


# ---------------------------------------------------------------- M&A issues
def mna_indemnity_cap(rng, c):
    pct = rng.choice([10, 12, 15, 20, 25])
    correct = c["price"] * pct / 100
    wrong = correct * rng.choice([0.8, 0.9, 1.2, 1.25])
    sec = f"{rng.randint(8, 9)}.{rng.randint(2, 5)}"
    return Planted(
        "indemnity_cap",
        {"spa": [f"Section {sec} (Limitation of Liability): the aggregate liability of the Seller for warranty claims shall not exceed an amount equal to {pct}% of the Purchase Price, being {fmt_money(wrong)}. The Purchase Price is {fmt_money(c['price'])} (see Section 2.1)."]},
        {"spa": [f"{pct}%", fmt_money(wrong), fmt_money(c["price"])]},
        [f"Identifies that the warranty cap in SPA Section {sec} is stated as {fmt_money(wrong)} but {pct}% of the {fmt_money(c['price'])} Purchase Price is {fmt_money(correct)}, i.e. the stated figure is wrong."],
        ["H4"],
        {"H4": f"Shows the arithmetic for the cap ({pct}% x {fmt_money(c['price'])} = {fmt_money(correct)}) and flags the discrepancy with the stated {fmt_money(wrong)}."},
        "numeric",
    )


def mna_basket(rng, c):
    pct = rng.choice([0.5, 1.0])
    basket = c["price"] * pct / 100
    return Planted(
        "tipping_basket",
        {"spa": [f"Section 9.4 (De Minimis and Basket): the Seller shall not be liable unless the aggregate of all claims exceeds {fmt_money(basket)} ({pct}% of the Purchase Price), in which case the Seller shall be liable only for the excess over that amount."]},
        {"spa": [fmt_money(basket), "excess"]},
        [f"Identifies that the basket in SPA Section 9.4 ({fmt_money(basket)}) operates as a deductible (Seller liable only for the excess), not a tipping basket, and explains that this is less favourable to the Buyer."],
        ["H6"], {}, "qualitative",
    )


def mna_escrow_release(rng, c):
    months = rng.choice([12, 18, 24])
    closing = weekend_date_after(rng, c["closing"], months)
    c["closing"] = closing
    release = add_months(closing, months)
    adj = next_business_day(release)
    days = (release - c["today"]).days
    return Planted(
        "escrow_release",
        {"escrow": [f"Clause 4.1: the Escrow Amount shall be released to the Seller on the date falling {months} months after the Closing Date, save to the extent of pending claims notified before that date. 'Business Day' means a day other than a Saturday or Sunday on which banks are open in London.", f"The Closing Date is {fmt_date(closing)}."],
         "spa": [f"Section 1.1: 'Closing Date' means {fmt_date(closing)}."]},
        {"escrow": [f"{months} months", fmt_date(closing)]},
        [f"States that the escrow release date is {fmt_date(release)} ({months} months after the {fmt_date(closing)} Closing Date) and that pending claims must be notified before then."],
        ["H3", "H10"],
        {"H3": f"Gives the escrow release period as a duration ({months} months) and as a date ({fmt_date(release)}), with days remaining from {fmt_date(c['today'])} ({days} days).",
         "H10": f"Notes that {fmt_date(release)} is a {release.strftime('%A')} and that the release moves to the next Business Day, {fmt_date(adj)}."},
        "date",
    )


def mna_survival(rng, c):
    gen = rng.choice([12, 18, 24])
    fund = rng.choice([36, 48, 72])
    gexp = add_months(c["closing"], gen)
    fexp = add_months(c["closing"], fund)
    days = (gexp - c["today"]).days
    return Planted(
        "survival_period",
        {"spa": [f"Section 10.1 (Survival): the General Warranties survive Closing for {gen} months; the Fundamental Warranties (title, capacity, tax) survive for {fund} months. Claims must be notified in writing before expiry."]},
        {"spa": [f"{gen} months", f"{fund} months"]},
        [f"States that General Warranty claims must be notified by {fmt_date(gexp)} ({gen} months after Closing) and Fundamental Warranty claims by {fmt_date(fexp)} ({fund} months after Closing)."],
        ["H3"],
        {"H3": f"States the survival periods as durations and as dates ({fmt_date(gexp)}; {fmt_date(fexp)}) and gives days remaining to the general-warranty expiry from {fmt_date(c['today'])} ({days} days)."},
        "date",
    )


def mna_coc_consent(rng, c):
    cust = c["customer"]
    return Planted(
        "change_of_control_consent",
        {"material_contract": [f"Clause 14.2: either party may terminate this agreement on 30 days' notice if the other party undergoes a change of control without its prior written consent. The counterparty is {cust}."],
         "disclosure": ["Disclosure against Warranty 6.3 (Material Contracts): no material contract contains a change of control provision. (No further disclosure.)"]},
        {"material_contract": ["change of control", "prior written consent"]},
        [f"Identifies that the {cust} contract (Clause 14.2) allows termination on a change of control without consent, that the disclosure against Warranty 6.3 says there is no such provision, and that consent should be obtained as a condition to Closing."],
        ["H11", "H5"],
        {"H11": f"Lists the {cust} change-of-control consent as a required third-party consent and states it has not been obtained.",
         "H5": "Flags that the disclosure letter is inconsistent with the material contract on change of control."},
        "qualitative",
    )


def mna_undisclosed_claim(rng, c):
    claimant = c["claimant"]
    amt = rng.choice([450_000, 1_200_000, 2_750_000, 3_400_000])
    return Planted(
        "undisclosed_litigation",
        {"board_minutes": [f"Item 5: the board noted a letter before action from {claimant} threatening proceedings for approximately {fmt_money(amt)} in respect of alleged defective deliveries. Management to monitor."],
         "disclosure": ["Disclosure against Warranty 7.1 (Litigation): None."]},
        {"board_minutes": [claimant, fmt_money(amt)]},
        [f"Identifies the threatened {fmt_money(amt)} claim by {claimant} recorded in the board minutes and that it is not disclosed against the litigation warranty (Warranty 7.1), recommending a specific indemnity or price protection."],
        ["H5"], {"H5": "Flags that the board minutes and the disclosure letter are inconsistent about litigation."}, "qualitative",
    )


def mna_earn_out(rng, c):
    thr = rng.choice([4_000_000, 5_000_000, 6_500_000])
    ebitda = thr + rng.choice([800_000, 1_300_000, 2_100_000])
    mult = rng.choice([2, 3])
    capv = rng.choice([3_000_000, 5_000_000, 10_000_000])
    correct = min(capv, mult * (ebitda - thr))
    wrong = correct + rng.choice([-400_000, 600_000, 900_000])
    return Planted(
        "earn_out",
        {"spa": [f"Section 3.4 (Earn-out): the Earn-out Payment equals {mult} times the amount by which FY2026 EBITDA exceeds {fmt_money(thr)}, capped at {fmt_money(capv)}."],
         "client_email": [f"Management accounts show FY2026 EBITDA of {fmt_money(ebitda)}; the Seller says the Earn-out Payment will therefore be {fmt_money(wrong)}."]},
        {"spa": [fmt_money(thr), fmt_money(capv)], "client_email": [fmt_money(ebitda), fmt_money(wrong)]},
        [f"Calculates the Earn-out Payment as {fmt_money(correct)} ({mult} x ({fmt_money(ebitda)} - {fmt_money(thr)}), subject to the {fmt_money(capv)} cap) and identifies that the Seller's figure of {fmt_money(wrong)} is wrong."],
        ["H4"], {"H4": f"Shows the earn-out arithmetic and flags the discrepancy between {fmt_money(correct)} and the Seller's {fmt_money(wrong)}."}, "numeric",
    )


def mna_mac(rng, c):
    return Planted(
        "mac_definition",
        {"spa": ["Section 1.1: 'Material Adverse Change' means any event which has a material adverse effect on the business of the Company, excluding changes in general economic conditions, changes affecting the industry generally, and pandemics."]},
        {"spa": ["Material Adverse Change", "pandemics"]},
        ["Identifies that the MAC carve-outs (general economic, industry-wide and pandemic changes) contain no 'disproportionate effect' exception, so the Buyer bears those risks even where the Company is disproportionately affected, and recommends adding one."],
        ["H9"], {"H9": "Explains how 'material adverse effect' could be read narrowly or broadly and what each reading means for the Buyer's walk-away right."}, "qualitative",
    )


def mna_non_compete(rng, c):
    spa_y = rng.choice([4, 5])
    emp_m = rng.choice([12, 18])
    return Planted(
        "non_compete_conflict",
        {"spa": [f"Section 12.1: the Seller shall not compete with the business for {spa_y} years after Closing."],
         "employment": [f"Clause 18: the Founder shall not compete with the business for {emp_m} months after termination of employment."]},
        {"spa": [f"{spa_y} years"], "employment": [f"{emp_m} months"]},
        [f"Identifies that the {spa_y}-year SPA non-compete may be unenforceable as wider than reasonably necessary and is inconsistent with the {emp_m}-month restriction in the Founder's employment agreement."],
        ["H5"], {"H5": "Flags the inconsistency between the SPA and employment agreement non-compete periods."}, "qualitative",
    )


def mna_notice_conflict(rng, c):
    a, b = rng.choice([(20, 45), (30, 60), (30, 45)])
    return Planted(
        "claim_notice_conflict",
        {"spa": [f"Section 9.7: the Buyer must notify any warranty claim within {a} days of becoming aware of it."],
         "escrow": [f"Clause 5.2: a claim against the Escrow Amount must be notified within {b} days of the Buyer becoming aware of it."]},
        {"spa": [f"{a} days"], "escrow": [f"{b} days"]},
        [f"Identifies the conflict between the {a}-day claim notice period in SPA Section 9.7 and the {b}-day period in Escrow Clause 5.2, and recommends the Buyer works to the shorter {a}-day period or aligns the documents."],
        ["H5"], {"H5": f"Flags the {a}-day vs {b}-day notice-period inconsistency between the SPA and the escrow agreement."}, "date",
    )


def mna_board_quorum(rng, c):
    return Planted(
        "board_quorum",
        {"board_minutes": ["Present: 2 directors (of 5). The meeting was quorate. RESOLVED to approve entry into the Share Purchase Agreement."],
         "articles": ["Article 11: the quorum for board meetings is three directors."]},
        {"board_minutes": ["2 directors"], "articles": ["three directors"]},
        ["Identifies that the board approval was given at a meeting with only 2 directors present when Article 11 requires a quorum of three, so the approval may be invalid, and recommends a fresh or ratifying resolution."],
        ["H11"], {"H11": "Lists valid board approval of the transaction as a required approval and states it has not been validly obtained."}, "qualitative",
    )


def mna_wc_adjust(rng, c):
    target = rng.choice([2_000_000, 3_500_000, 5_000_000])
    est = target - rng.choice([350_000, 620_000, 910_000])
    shortfall = target - est
    adjusted = c["price"] - shortfall
    wrong = c["price"] - shortfall * 2
    return Planted(
        "working_capital_adjustment",
        {"spa": [f"Section 2.3: the Purchase Price shall be reduced dollar-for-dollar by any shortfall of Closing Working Capital below the Target Working Capital of {fmt_money(target)}."],
         "client_email": [f"The estimated Closing Working Capital is {fmt_money(est)}. The Seller's draft funds flow shows an adjusted purchase price of {fmt_money(wrong)}."]},
        {"spa": [fmt_money(target)], "client_email": [fmt_money(est), fmt_money(wrong)]},
        [f"Calculates the working capital shortfall as {fmt_money(shortfall)} and the adjusted Purchase Price as {fmt_money(adjusted)}, identifying that the Seller's funds flow figure of {fmt_money(wrong)} is wrong."],
        ["H4"], {"H4": f"Shows the adjustment arithmetic ({fmt_money(c['price'])} - {fmt_money(shortfall)} = {fmt_money(adjusted)}) and flags the discrepancy."}, "numeric",
    )


def mna_governing_law(rng, c):
    return Planted(
        "governing_law_mismatch",
        {"spa": ["Section 15.1: this Agreement is governed by English law and the courts of England have exclusive jurisdiction."],
         "escrow": ["Clause 12: this escrow agreement is governed by the laws of the State of New York and disputes shall be referred to arbitration in New York."]},
        {"spa": ["English law"], "escrow": ["New York"]},
        ["Identifies the mismatch between English law / English courts in the SPA and New York law / New York arbitration in the escrow agreement, and the risk of parallel proceedings on escrow claims."],
        ["H5"], {"H5": "Flags the governing law and forum inconsistency between the SPA and the escrow agreement."}, "qualitative",
    )


def mna_ip_gap(rng, c):
    dev = c["contractor"]
    return Planted(
        "ip_assignment_gap",
        {"disclosure": [f"Disclosure against Warranty 8.2 (IP): the Company's core platform software was developed in 2023 by an independent contractor, {dev}. No written assignment of intellectual property was entered into."]},
        {"disclosure": [dev, "No written assignment"]},
        [f"Identifies that the core platform was developed by contractor {dev} without a written IP assignment, so the Company may not own it, and recommends obtaining a confirmatory assignment as a condition to Closing."],
        ["H11"], {"H11": f"Lists a confirmatory IP assignment from {dev} as a required third-party action not yet obtained."}, "qualitative",
    )


def mna_long_stop(rng, c):
    n = rng.choice([90, 120, 150])
    signing = c["signing"]
    ls = signing + dt.timedelta(days=n)
    approval = ls + dt.timedelta(days=rng.choice([14, 30, 45]))
    days = (ls - c["today"]).days
    return Planted(
        "long_stop_date",
        {"spa": [f"Section 4.5: if the Conditions are not satisfied by the date falling {n} days after the date of this Agreement (signed {fmt_date(signing)}), either party may terminate."],
         "client_email": [f"Regulatory counsel expects merger clearance by {fmt_date(approval)}."]},
        {"spa": [f"{n} days", fmt_date(signing)], "client_email": [fmt_date(approval)]},
        [f"Calculates the long-stop date as {fmt_date(ls)} ({n} days after signing on {fmt_date(signing)}) and identifies that expected clearance on {fmt_date(approval)} falls after it, recommending an extension."],
        ["H3"], {"H3": f"Gives the long-stop period as {n} days and as the date {fmt_date(ls)}, with days remaining from {fmt_date(c['today'])} ({days} days)."}, "date",
    )


# ---------------------------------------------------------------- Capital markets issues
def cm_lockup(rng, c):
    days_n = rng.choice([90, 180, 365])
    pdate = c["closing"]
    for off in range(40):
        cand = pdate + dt.timedelta(days=off)
        if (cand + dt.timedelta(days=days_n)).weekday() >= 5:
            pdate = cand
            break
    c["closing"] = pdate
    exp = pdate + dt.timedelta(days=days_n)
    adj = next_business_day(exp)
    left = (exp - c["today"]).days
    return Planted(
        "lockup_expiry",
        {"lock_up": [f"Clause 2: the Shareholder shall not sell any Shares during the period ending {days_n} days after the date of the Prospectus. 'Business Day' means a day other than a Saturday or Sunday on which banks are open in New York."],
         "prospectus": [f"The date of this Prospectus is {fmt_date(pdate)}."]},
        {"lock_up": [f"{days_n} days"], "prospectus": [fmt_date(pdate)]},
        [f"States that the lock-up expires on {fmt_date(exp)} ({days_n} days after the {fmt_date(pdate)} Prospectus date)."],
        ["H3", "H10"],
        {"H3": f"Gives the lock-up as a duration ({days_n} days) and a date ({fmt_date(exp)}), with days remaining from {fmt_date(c['today'])} ({left} days).",
         "H10": f"Notes that {fmt_date(exp)} is a {exp.strftime('%A')} and identifies the next Business Day, {fmt_date(adj)}, as the first trading opportunity."},
        "date",
    )


def cm_undisclosed_litigation(rng, c):
    claimant = c["claimant"]
    amt = rng.choice([8_000_000, 12_500_000, 20_000_000])
    return Planted(
        "risk_factor_omission",
        {"board_minutes": [f"Item 3: the board discussed a class action filed by {claimant} seeking {fmt_money(amt)} in damages. Counsel assesses the claim as having reasonable prospects."],
         "prospectus": ["Legal Proceedings: the Company is not party to any legal proceedings which may have a significant effect on its financial position."]},
        {"board_minutes": [claimant, fmt_money(amt)]},
        [f"Identifies that the {fmt_money(amt)} {claimant} class action in the board minutes is omitted from the Prospectus legal proceedings and risk factors, creating disclosure liability, and recommends adding disclosure."],
        ["H5"], {"H5": "Flags that the Prospectus is inconsistent with the board minutes on legal proceedings."}, "qualitative",
    )


def cm_use_of_proceeds(rng, c):
    net = rng.choice([80_000_000, 120_000_000, 150_000_000])
    a = round(net * 0.45 / 1e6) * 1e6
    b = round(net * 0.30 / 1e6) * 1e6
    d = net - a - b
    wrong_d = d + rng.choice([5_000_000, 8_000_000])
    total_listed = a + b + wrong_d
    return Planted(
        "use_of_proceeds_math",
        {"prospectus": [f"Use of Proceeds: net proceeds of {fmt_money(net)} will be applied as follows: repayment of the revolving facility {fmt_money(a)}; capital expenditure {fmt_money(b)}; general corporate purposes {fmt_money(wrong_d)}."]},
        {"prospectus": [fmt_money(net), fmt_money(a), fmt_money(b), fmt_money(wrong_d)]},
        [f"Identifies that the Use of Proceeds allocations sum to {fmt_money(total_listed)}, not the stated net proceeds of {fmt_money(net)} (a {fmt_money(total_listed - net)} overstatement)."],
        ["H4"], {"H4": f"Shows the sum of the allocations ({fmt_money(a)} + {fmt_money(b)} + {fmt_money(wrong_d)} = {fmt_money(total_listed)}) against {fmt_money(net)}."}, "numeric",
    )


def cm_gross_spread(rng, c):
    shares = rng.choice([10_000_000, 12_500_000, 20_000_000])
    px = rng.choice([14.0, 18.5, 22.0])
    pct = rng.choice([5.5, 6.0, 7.0])
    gross = shares * px
    fee = gross * pct / 100
    wrong = fee * rng.choice([0.85, 1.15])
    return Planted(
        "underwriting_fee",
        {"underwriting": [f"Clause 3: the Company shall pay the Underwriters a commission of {pct}% of the gross proceeds of the Offering ({shares:,} shares at ${px:.2f} per share), being {fmt_money(wrong)}."]},
        {"underwriting": [f"{pct}%", f"{shares:,}", f"${px:.2f}", fmt_money(wrong)]},
        [f"Calculates the underwriting commission as {fmt_money(fee)} ({pct}% of gross proceeds of {fmt_money(gross)}) and identifies that the stated {fmt_money(wrong)} is wrong."],
        ["H4"], {"H4": f"Shows the commission arithmetic ({shares:,} x ${px:.2f} = {fmt_money(gross)}; x {pct}% = {fmt_money(fee)}) and flags the discrepancy."}, "numeric",
    )


def cm_greenshoe(rng, c):
    base = rng.choice([10_000_000, 16_000_000, 24_000_000])
    correct = int(base * 0.15)
    wrong = int(base * 0.20)
    return Planted(
        "over_allotment",
        {"underwriting": [f"Clause 4: the Company grants the Underwriters an option to purchase up to {wrong:,} additional shares (the Over-allotment Option), representing 15% of the {base:,} Firm Shares."]},
        {"underwriting": [f"{wrong:,}", f"{base:,}", "15%"]},
        [f"Identifies that 15% of {base:,} Firm Shares is {correct:,} shares, not the {wrong:,} stated in the Over-allotment Option (Clause 4)."],
        ["H4"], {"H4": f"Shows the over-allotment arithmetic (15% x {base:,} = {correct:,}) and flags the discrepancy."}, "numeric",
    )


def cm_share_count(rng, c):
    a = rng.choice([45_200_000, 61_750_000, 88_000_000])
    b = a + rng.choice([500_000, 1_250_000])
    return Planted(
        "share_count_inconsistency",
        {"prospectus": [f"Capitalisation: {a:,} ordinary shares are in issue at the date of this Prospectus."],
         "underwriting": [f"Recital C: the Company has {b:,} ordinary shares in issue."]},
        {"prospectus": [f"{a:,}"], "underwriting": [f"{b:,}"]},
        [f"Identifies the inconsistency between {a:,} shares in issue in the Prospectus and {b:,} in the Underwriting Agreement recital, which must be reconciled before pricing."],
        ["H5"], {"H5": "Flags the share-count inconsistency between the Prospectus and the Underwriting Agreement."}, "numeric",
    )


def cm_comfort_cutoff(rng, c):
    pricing = c["closing"]
    cutoff = pricing - dt.timedelta(days=rng.choice([9, 12, 15]))
    return Planted(
        "comfort_letter_cutoff",
        {"comfort": [f"Paragraph 6: our procedures covered the period up to {fmt_date(cutoff)} (the cut-off date)."],
         "underwriting": [f"Clause 7(b): the comfort letter cut-off date shall be no earlier than 3 business days before the pricing date. The pricing date is {fmt_date(pricing)}."]},
        {"comfort": [fmt_date(cutoff)], "underwriting": [fmt_date(pricing)]},
        [f"Identifies that the comfort letter cut-off of {fmt_date(cutoff)} is {(pricing - cutoff).days} days before the {fmt_date(pricing)} pricing date, outside the 3-business-day requirement in Clause 7(b), so a bring-down letter is needed."],
        ["H3"], {"H3": f"States the gap between cut-off and pricing as a duration ({(pricing - cutoff).days} calendar days) and identifies the latest compliant cut-off date."}, "date",
    )


def cm_related_party(rng, c):
    director = c["director"]
    amt = rng.choice([2_500_000, 4_000_000, 6_250_000])
    return Planted(
        "related_party_disclosure",
        {"board_minutes": [f"Item 7: the board approved a loan of {fmt_money(amt)} from the Company to {director}, a director, on interest-free terms."],
         "prospectus": ["Related Party Transactions: there are no related party transactions other than directors' service agreements."]},
        {"board_minutes": [director, fmt_money(amt)]},
        [f"Identifies the undisclosed {fmt_money(amt)} interest-free loan to director {director} that must be described in the Prospectus Related Party Transactions section."],
        ["H5"], {"H5": "Flags that the Prospectus related party disclosure is inconsistent with the board minutes."}, "qualitative",
    )


def cm_selling_restrictions(rng, c):
    return Planted(
        "selling_restrictions",
        {"underwriting": ["Clause 9: the Underwriters may offer the Shares to investors in the United States, Canada and the European Economic Area. No selling restrictions or exemption conditions are specified for any jurisdiction."]},
        {"underwriting": ["United States", "European Economic Area"]},
        ["Identifies that the Underwriting Agreement lacks selling restrictions (e.g. Rule 144A / Regulation S for the US, prospectus exemptions for Canada and the EEA) and recommends adding them."],
        ["H11"], {"H11": "Lists securities-law exemptions/registrations required for each offering jurisdiction and states they are not addressed."}, "qualitative",
    )


# ---------------------------------------------------------------- Commercial / employment issues
def com_auto_renewal(rng, c):
    n = rng.choice([60, 90])
    expiry = c["closing"]
    last = expiry - dt.timedelta(days=n)
    for off in range(30):
        cand = expiry + dt.timedelta(days=off)
        if (cand - dt.timedelta(days=n)).weekday() >= 5:
            expiry = cand
            last = cand - dt.timedelta(days=n)
            break
    c["closing"] = expiry
    prev_bd = last
    while prev_bd.weekday() >= 5:
        prev_bd -= dt.timedelta(days=1)
    left = (last - c["today"]).days
    return Planted(
        "auto_renewal_notice",
        {"msa": [f"Clause 3.2: this Agreement expires on {fmt_date(expiry)} and renews automatically for successive 2-year terms unless either party gives notice of non-renewal at least {n} days before expiry. Notices are effective only on Business Days (Monday to Friday)."]},
        {"msa": [fmt_date(expiry), f"{n} days"]},
        [f"Calculates the last date to serve non-renewal notice as {fmt_date(last)} ({n} days before the {fmt_date(expiry)} expiry), and warns that otherwise the agreement renews for 2 years."],
        ["H3", "H10"],
        {"H3": f"Gives the notice window as {n} days and as the date {fmt_date(last)}, with days remaining from {fmt_date(c['today'])} ({left} days).",
         "H10": f"Notes that {fmt_date(last)} is a {last.strftime('%A')} and that notice should be served by the preceding Business Day, {fmt_date(prev_bd)}."},
        "date",
    )


def com_liability_carveout(rng, c):
    capv = rng.choice([500_000, 1_000_000])
    return Planted(
        "data_breach_cap",
        {"msa": [f"Clause 11: each party's total liability is capped at {fmt_money(capv)}. The cap does not apply to death or personal injury caused by negligence or to fraud."],
         "dpa": ["Clause 6: the Supplier shall process Customer Personal Data in accordance with applicable data protection law."]},
        {"msa": [fmt_money(capv)]},
        [f"Identifies that data protection breaches are not carved out of the {fmt_money(capv)} liability cap in Clause 11, leaving the customer under-protected for data breach losses, and recommends a separate higher cap or carve-out."],
        ["H6"], {}, "qualitative",
    )


def com_service_credits(rng, c):
    fee = rng.choice([40_000, 65_000, 120_000])
    uptime = rng.choice([98.1, 97.4, 98.6])
    pct = 10 if uptime >= 98.0 else 25
    correct = fee * pct / 100
    wrong = fee * 5 / 100
    return Planted(
        "service_credit_calc",
        {"sla": [f"Paragraph 4: if monthly availability is below 99.5% but at least 98.0%, a service credit of 10% of the monthly fee applies; below 98.0%, 25%. The monthly fee is {fmt_money(fee)}."],
         "client_email": [f"Availability last month was {uptime}%. The supplier has offered a service credit of {fmt_money(wrong)}."]},
        {"sla": [fmt_money(fee), "98.0%"], "client_email": [f"{uptime}%", fmt_money(wrong)]},
        [f"Calculates the service credit as {fmt_money(correct)} ({pct}% of the {fmt_money(fee)} monthly fee for {uptime}% availability) and identifies that the supplier's offer of {fmt_money(wrong)} is too low."],
        ["H4"], {"H4": f"Shows the service credit arithmetic ({pct}% x {fmt_money(fee)} = {fmt_money(correct)}) and flags the discrepancy with {fmt_money(wrong)}."}, "numeric",
    )


def com_assignment(rng, c):
    return Planted(
        "assignment_change_of_control",
        {"msa": ["Clause 19: neither party may assign this Agreement without the other's consent. A change of control of a party is deemed an assignment."],
         "client_email": ["The client is planning a group reorganisation that will move it under a new holding company next quarter."]},
        {"msa": ["deemed an assignment"]},
        ["Identifies that the planned reorganisation may be a change of control deemed an assignment under Clause 19, requiring the counterparty's consent."],
        ["H11"], {"H11": "Lists counterparty consent under Clause 19 as a required consent for the reorganisation that has not been obtained."}, "qualitative",
    )


def emp_garden_leave(rng, c):
    gl = rng.choice([3, 6])
    nc = rng.choice([6, 12])
    return Planted(
        "garden_leave_offset",
        {"employment": [f"Clause 16: the Company may place the Executive on garden leave for up to {gl} months of the notice period. Clause 18: the Executive shall not compete for {nc} months after the Termination Date. There is no provision reducing the restriction by time spent on garden leave."]},
        {"employment": [f"{gl} months", f"{nc} months"]},
        [f"Identifies that the {nc}-month non-compete is not reduced by up to {gl} months of garden leave, so total restraint could be {gl + nc} months, increasing unenforceability risk; recommends an offset provision."],
        ["H9"], {"H9": "Explains the alternative readings of whether the restraint runs from the start or end of garden leave and their consequences."}, "qualitative",
    )


def emp_notice_pay(rng, c):
    salary = rng.choice([96_000, 132_000, 180_000])
    months = rng.choice([3, 6])
    correct = salary / 12 * months
    wrong = salary / 52 * months * 4
    return Planted(
        "pilon_calc",
        {"employment": [f"Clause 15: the Company may terminate by paying basic salary in lieu of {months} months' notice. Annual basic salary is {fmt_money(salary)}."],
         "settlement": [f"The Company proposes a payment in lieu of notice of {fmt_money(wrong)}."]},
        {"employment": [fmt_money(salary), f"{months} months"], "settlement": [fmt_money(wrong)]},
        [f"Calculates pay in lieu of notice as {fmt_money(correct)} ({months}/12 of {fmt_money(salary)}) and identifies that the proposed {fmt_money(wrong)} understates it."],
        ["H4"], {"H4": f"Shows the PILON arithmetic ({fmt_money(salary)} / 12 x {months} = {fmt_money(correct)}) and flags the discrepancy."}, "numeric",
    )


ISSUES: dict[str, list[Callable[..., Planted]]] = {
    "corporate_mna": [mna_indemnity_cap, mna_basket, mna_escrow_release, mna_survival, mna_coc_consent,
                      mna_undisclosed_claim, mna_earn_out, mna_mac, mna_non_compete, mna_notice_conflict,
                      mna_board_quorum, mna_wc_adjust, mna_governing_law, mna_ip_gap, mna_long_stop],
    "capital_markets": [cm_lockup, cm_undisclosed_litigation, cm_use_of_proceeds, cm_gross_spread, cm_greenshoe,
                        cm_share_count, cm_comfort_cutoff, cm_related_party, cm_selling_restrictions],
    "commercial_contract": [com_auto_renewal, com_liability_carveout, com_service_credits, com_assignment],
    "employment": [emp_garden_leave, emp_notice_pay],
}
DATE_ISSUES = {"escrow_release", "survival_period", "claim_notice_conflict", "long_stop_date", "lockup_expiry",
               "comfort_letter_cutoff", "auto_renewal_notice"}

DOC_TITLES = {
    "spa": "share_purchase_agreement.md", "disclosure": "disclosure_letter.md", "board_minutes": "board_minutes.md",
    "escrow": "escrow_agreement.md", "client_email": "client_email.md", "employment": "employment_agreement.md",
    "material_contract": "material_customer_contract.md", "articles": "articles_of_association_extract.md",
    "prospectus": "prospectus_extract.md", "underwriting": "underwriting_agreement.md", "lock_up": "lock_up_agreement.md",
    "comfort": "comfort_letter.md", "msa": "master_services_agreement.md", "dpa": "data_processing_agreement.md",
    "sla": "service_level_schedule.md", "settlement": "settlement_proposal.md", "research_note": "internal_research_note.md",
}
PRINCIPAL_DOC = {"corporate_mna": "spa", "capital_markets": "underwriting", "commercial_contract": "msa",
                 "employment": "employment"}
MATTER_FAMILY = {"corporate_mna": "acquisition", "capital_markets": "securities",
                 "commercial_contract": "commercial_contract", "employment": "employment"}

# ---------------------------------------------------------------- negative-control research topics
RESEARCH_TOPICS: list[dict[str, Any]] = [
    {"q": "What is the difference between a representation and a warranty under English law, and why does it matter to a buyer?",
     "points": ["Explains that a warranty is a contractual promise whose breach gives a claim for damages for breach of contract (contractual measure).",
                "Explains that a representation is a statement inducing the contract whose falsity can give a misrepresentation claim, including rescission and tortious/statutory damages.",
                "Notes that sellers typically state that warranties are not representations / exclude reliance to limit remedies.",
                "Explains why this matters to a buyer (wider remedies, rescission, measure of loss)."]},
    {"q": "How do English courts interpret a 'material adverse change' clause?",
     "points": ["States that the burden is on the party invoking the MAC to prove it.",
                "Explains that the change must be material and durationally significant, not short-term.",
                "Notes that changes known to the party at signing generally cannot be relied on.",
                "Notes that courts construe MAC clauses according to their wording and context rather than a fixed threshold."]},
    {"q": "What duties do directors owe when approving the sale of the company?",
     "points": ["Identifies the duty to promote the success of the company for the benefit of its members as a whole (s.172 Companies Act 2006).",
                "Identifies the duty to exercise independent judgment and reasonable care, skill and diligence.",
                "Identifies the duty to avoid conflicts of interest and declare interests in transactions.",
                "Notes that the board should take advice and minute its reasoning."]},
    {"q": "When is a liquidated damages clause unenforceable as a penalty?",
     "points": ["States the modern test from Cavendish v Makdessi: whether the clause protects a legitimate interest and is not out of all proportion to it.",
                "Explains that the rule applies only to secondary obligations triggered by breach.",
                "Notes that commercial context and equal bargaining power make enforcement more likely.",
                "Explains the consequence that a penalty is unenforceable and the claimant recovers general damages."]},
    {"q": "Is there an implied duty of good faith in English commercial contracts?",
     "points": ["States that English law has no general duty of good faith in commercial contracts.",
                "Explains that a duty may be implied in relational contracts (e.g. Yam Seng, Bates v Post Office).",
                "Notes that parties can expressly agree a good faith obligation and courts will give it effect.",
                "Notes the implied term that contractual discretions be exercised rationally (Braganza)."]},
    {"q": "Does a variation of a contract require fresh consideration?",
     "points": ["States the general rule that a variation requires consideration to be binding.",
                "Explains the practical benefit doctrine from Williams v Roffey.",
                "Notes that a deed avoids the need for consideration.",
                "Notes the effect of 'no oral modification' clauses after Rock Advertising v MWB."]},
]
