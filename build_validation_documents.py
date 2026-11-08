"""Build the synthetic validation grant file sets bundled with Tidepath."""
import csv
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "validation_documents"
DATA = ROOT / "validation_grants.csv"
CATEGORIES = [
    ("Program personnel and benefits", 0.40, "Payroll - Program"),
    ("Mentoring, screening, training and supervision", 0.18, "Program Services - Mentoring"),
    ("Family counseling and caregiver support", 0.15, "Program Services - Family Support"),
    ("School safety and mental health workshops", 0.17, "Program Services - School Workshops"),
    ("Evaluation, data management and reporting", 0.10, "Program Evaluation"),
]
QUESTION_LIMITS = [
    ("Statement of Goals", 250),
    ("Implementation", 1000),
    ("Outreach & Engagement", 500),
    ("Assessment", 500),
    ("Qualifications & Sustainability", 500),
    ("Advancing Equity", 500),
    ("Financial Narrative", 500),
]
PHASES = [
    "Partner readiness and staff orientation", "Outreach and family enrollment", "Program launch",
    "Mentoring and workshops", "Mentoring and family support", "Midyear review",
    "Program delivery", "Program delivery", "School and family engagement",
    "Closeout preparation", "Outcome review", "Final reporting",
]


def read_grants():
    with DATA.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def dollars(value):
    amount = float(value)
    return f"-${abs(amount):,.2f}" if amount < 0 else f"${amount:,.2f}"


def split_cents(total, weights=None):
    weights = weights or [item[1] for item in CATEGORIES]
    cents = int(round(float(total) * 100))
    pieces = [int(round(cents * weight)) for weight in weights]
    pieces[-1] += cents - sum(pieces)
    return [piece / 100 for piece in pieces]


def csv_text(path, fields, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def period_for(row):
    if row["status"] == "APPLYING":
        return date(2027, 1, 1), date(2027, 12, 31)
    if row["status"] == "APPROVED":
        return date(2026, 1, 1), date(2026, 12, 31)
    end = datetime.strptime(row["completed_on"], "%Y-%m-%d").date()
    start = date(end.year - 1, end.month, end.day) + timedelta(days=1)
    return start, end


def month_starts(start, count=12):
    year, month = start.year, start.month
    dates = []
    for _ in range(count):
        dates.append(date(year, month, 1))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return dates


def responses_for(row):
    name = row["grant_name"]
    amount = float(row["annual_amount"])
    status = row["status"].title()
    lifecycle = {
        "APPLYING": "This is a pending application scenario; no award or spending authorization has been issued.",
        "APPROVED": "This is an approved-award validation scenario. All activity and performance figures below are synthetic test data, not verified services.",
        "COMPLETED": "This is a completed historical validation scenario. All activity, outcomes, and financial figures are synthetic test data, not verified services.",
    }[row["status"]]
    answers = {
        "Statement of Goals": f"{name} is a proposed Tidepath Family Alliance initiative to support children and caregivers through consistent mentoring, family counseling, and school-based safety and mental health workshops. The project would offer a dependable adult connection, practical caregiver support, and age-appropriate ways for students to recognize stress and seek help. The sample annual request is {dollars(amount)} and the planning assumption is to serve up to 60 children and their families. These are proposed validation targets, not historical outcomes. {lifecycle}",
        "Implementation": "During a 12-month project period, staff would coordinate referrals with participating schools and community partners, obtain caregiver consent and child assent, and develop a family-centered support plan. Trained mentors would meet with participating children on a regular schedule, with staff supervision and documented safeguarding procedures. Qualified counseling professionals would provide family counseling or connect families to appropriate services when needs fall outside the program's scope. Schools would host practical safety and mental health workshops during the academic year, including how to identify trusted adults, ask for help, and use school support pathways. The project coordinator would track attendance, family contacts, workshop participation, referrals, and budget activity. Staff would use periodic check-ins to adjust scheduling and remove participation barriers. Mentoring and workshops are supportive services and do not replace clinical care, emergency response, or school counseling. All targets and events in this fixture are illustrative only.",
        "Outreach & Engagement": "Tidepath would invite school and community partners to refer children and families who want additional mentoring, caregiver support, or practical safety and mental health education. Participation would be voluntary, with information shared in accessible formats and families offered a chance to discuss schedules, language, transportation, and accessibility needs. Caregivers and children would help shape participation goals, meeting times, and feedback methods. Staff would explain privacy limits, safeguarding steps, referral options, and how to raise a concern before enrollment. Outreach would use partner communication channels and family meetings; translation or transportation supports would be offered only when arranged and funded. No diagnosis would be required to participate.",
        "Assessment": "The project would track children enrolled, mentoring contacts completed, caregiver counseling or support contacts, workshop attendance, referrals offered, and participant retention. A brief baseline, midyear check-in, and closeout survey would measure reported connection to a trusted adult, confidence seeking help, and perceived access to family support. Staff would review activity and spending monthly and discuss barriers with school partners quarterly. Proposed targets include serving up to 60 children, documenting family engagement, and completing all scheduled workshops. The validation records contain synthetic progress values solely to exercise Tidepath's progress indicators. They must not be represented as observed or independently verified outcomes. Any real report would use approved source records and explain limitations.",
        "Qualifications & Sustainability": "Before implementation, Tidepath would confirm the project lead's experience, mentor screening and training, school-partner responsibilities, and the credentials and scope of any counseling professional. The demonstration files do not verify staff qualifications or partner agreements; actual resumes, licenses, policies, and memoranda must be attached before submission. Sustainability planning would include maintaining school and community referral relationships, documenting a repeatable mentor orientation, seeking additional public and private support, and reviewing actual delivery costs after each term. Continued services would depend on renewed funding and confirmed staff capacity.",
        "Advancing Equity": "The project is designed to reduce barriers to supportive relationships and family services for children and caregivers who may face cost, transportation, language, disability-access, or scheduling barriers. Outreach would be coordinated with families and schools, and staff would invite caregivers to identify the formats and times that work for them. Participation would not depend on a clinical diagnosis. The team would review enrollment, attendance, workshop access, and feedback for gaps across partner sites and use those findings to adjust outreach. Accommodations, translation, and transportation would be provided only when capacity and funding are confirmed; staff would not promise supports that are unavailable.",
        "Financial Narrative": f"The {dollars(amount)} sample budget is organized around project personnel, mentor screening and supervision, family counseling and caregiver support, school safety and mental health workshops, and evaluation and reporting. Funds would be tracked against the funder's approved categories, with receipts, allocation notes, and approval records retained for each transaction. Applying examples show a proposed request only. Approved examples include synthetic expenditures and quarterly utilization for workflow validation. Completed examples include a synthetic closeout and final settlement. None of these dollar amounts or activity records represents a real grant, expense, or payment.",
    }
    return answers


def proposal_doc(row):
    answers = responses_for(row)
    status_line = {
        "APPLYING": "Pending application — requested amount only; no award has been made.",
        "APPROVED": f"Approved mock award: {dollars(row['annual_amount'])}.",
        "COMPLETED": f"Completed historical mock award: {dollars(row['annual_amount'])}; see final settlement file.",
    }[row["status"]]
    out = [f"# Application Draft — {row['grant_name']}", "", f"**Grant ID:** {row['validation_id']}  ", f"**Funder:** {row['funder']}  ", f"**Status:** {status_line}", "", "> Synthetic validation document. Replace demonstration details with staff-approved organizational facts before any real submission.", ""]
    for title, limit in QUESTION_LIMITS:
        answer = answers[title]
        out += [f"## {title} (maximum {limit} words)", "", f"**Response ({len(answer.split())}/{limit} words):**", "", answer, ""]
    return "\n".join(out)


def budget_rows(row, start, end):
    amounts = split_cents(row["annual_amount"])
    return [
        {
            "grant_id": row["validation_id"], "mock_funder": row["funder"],
            "funder_budget_category": category, "approved_amount_usd": f"{amount:.2f}",
            "currency": "USD", "grant_start": start.isoformat(), "grant_end": end.isoformat(),
            "funder_fiscal_year": f"{start.isoformat()}–{end.isoformat()}",
            "report_due": end.isoformat(),
            "restriction_summary": "Synthetic allocation for mentoring, family support, school workshops, and evaluation; no actual award restrictions are represented.",
            "data_status": "Synthetic validation budget; not a real award",
        }
        for (category, _, _), amount in zip(CATEGORIES, amounts)
    ]


def expenditure_rows(row, start, end, annual_spend_by_category, prior=None, quarter=None):
    prior = prior or [0] * len(CATEGORIES)
    quarter = quarter or [0] * len(CATEGORIES)
    rows = []
    for idx, (category, _, ledger_category) in enumerate(CATEGORIES):
        parts = []
        if prior[idx] > 0:
            parts.append((date(start.year, min(start.month + 2, 12), 15), prior[idx], "Prior-period synthetic expense"))
        if quarter[idx] > 0:
            parts.append((date(2026, 10, 15), quarter[idx] * 0.65, "Current-quarter synthetic expense — October"))
            parts.append((date(2026, 11, 5), quarter[idx] - round(quarter[idx] * 0.65, 2), "Current-quarter synthetic expense — November"))
        if row["status"] == "COMPLETED" and annual_spend_by_category[idx] > 0:
            parts = [(end, annual_spend_by_category[idx], "Synthetic final-period expense allocation")]
        elif row["status"] == "APPLYING":
            parts = []
        for seq, (when, amount, description) in enumerate(parts, 1):
            amount = round(amount, 2)
            if amount <= 0:
                continue
            rows.append({
                "transaction_id": f"SYN-{row['validation_id']}-{idx+1:02d}-{seq:02d}",
                "grant_id": row["validation_id"], "expense_date": when.isoformat(),
                "vendor": "Synthetic validation vendor", "description": description,
                "quickbooks_category": ledger_category, "funder_budget_category": category,
                "amount_usd": f"{amount:.2f}", "grant_allocation_percent": "100%",
                "receipt_or_journal_id": f"SYN-REF-{row['validation_id']}-{idx+1:02d}-{seq:02d}",
                "supporting_document": "Synthetic placeholder; no real receipt exists",
                "approval_status": "Synthetic approved test line",
                "data_status": "Synthetic validation data only",
            })
    return rows


def outcomes_rows(row):
    progress = float(row["work_progress"])
    targets = [("Children enrolled", 60, "people"), ("Children completing 30 mentoring contacts", 48, "people"), ("Caregivers reached through family support", 60, "people"), ("School safety and mental health workshops delivered", 12, "workshops")]
    date_value = row.get("completed_on") or "2026-11-08"
    rows = []
    for measure, target, unit in targets:
        actual = int(round(target * progress))
        rows.append({"grant_id": row["validation_id"], "measure": measure, "target": target, "synthetic_actual": actual, "unit": unit, "synthetic_source": "Validation fixture only", "measurement_date": date_value, "data_status": "Synthetic sample only; not measured or verified"})
    return rows


def tracker_rows(row, start, approved_by_category, spend_by_category, prior_by_category, quarter_by_category):
    rows = []
    months = month_starts(start)
    for category_idx, (category, _, _) in enumerate(CATEGORIES):
        planned_months = split_cents(approved_by_category[category_idx], [1/12] * 12)
        if row["status"] == "COMPLETED":
            actual_months = split_cents(spend_by_category[category_idx], [1/12] * 12)
        elif row["status"] == "APPROVED":
            actual_months = [0.0] * 12
            prior_months = split_cents(prior_by_category[category_idx], [1/9] * 9)
            actual_months[:9] = prior_months
            q_months = split_cents(quarter_by_category[category_idx], [0.65, 0.35])
            actual_months[9:11] = q_months
        else:
            actual_months = [""] * 12
        for idx, month in enumerate(months):
            planned = planned_months[idx]
            actual = actual_months[idx]
            variance = round(planned - float(actual), 2) if actual != "" else ""
            rows.append({
                "Month": month.strftime("%Y-%m"), "Project phase": PHASES[idx],
                "Budget category": category, "Planned budget (USD)": f"{planned:.2f}",
                "Actual expense (USD)": f"{float(actual):.2f}" if actual != "" else "",
                "Variance: planned minus actual (USD)": f"{variance:.2f}" if variance != "" else "",
                "Notes": "Synthetic validation plan/actual; replace with source ledger" if row["status"] != "APPLYING" else "Proposed only; no actual expense is authorized or recorded",
            })
    return rows


def make_report_template(row):
    out = [f"# Mock Grant Report — {row['grant_name']}", "", f"**Grant ID:** {row['validation_id']}  ", f"**Status:** {row['status'].title()} validation record  ", "**Data status:** Synthetic only; do not submit as a real report.", "", "Complete using reviewed source documents. Do not treat fixture values as verified outcomes.", "", "## Narrative responses", ""]
    for title, limit in QUESTION_LIMITS:
        out += [f"### {title} (maximum {limit} words)", "", "[Enter a staff-reviewed response supported by records. Do not invent outcomes.]", ""]
    return "\n".join(out)


def progress_report(row, budget, spend, quarter_budget, quarter_spend):
    use = quarter_spend / quarter_budget if quarter_budget else 0
    if use > 1.5:
        status = "URGENT — severe quarterly overspend; reconcile every category and escalate to the bookkeeper."
    elif use > 1:
        status = "REVIEW — quarterly spend exceeds the approved quarter plan; document the variance."
    elif use >= 0.85:
        status = "WATCH — close to the quarterly budget limit; verify remaining commitments."
    elif use < 0.1:
        status = "LOW UTILIZATION — confirm program launch dates, invoices, and planned delivery."
    else:
        status = "ON PLAN — continue routine monitoring."
    result = outcomes_rows(row)
    table = "\n".join(f"| {x['measure']} | {x['target']} | {x['synthetic_actual']} | {x['unit']} |" for x in result)
    return f"""# Quarterly Progress Report — {row['grant_name']}

**Grant ID:** {row['validation_id']}  
**Funder:** {row['funder']}  
**As-of date:** 2026-11-08  
**Status:** {status}

> Synthetic validation report. Every amount, target, and result below is a test fixture, not a verified service or financial record.

## Budget snapshot

- Annual award: {dollars(row['annual_amount'])}
- Mock year-to-date spend: {dollars(spend)}
- Current-quarter budget: {dollars(quarter_budget)}
- Current-quarter spend: {dollars(quarter_spend)} ({use:.1%})
- Remaining current-quarter budget: {dollars(quarter_budget-quarter_spend)}

## Work progress indicators

| Measure | Target | Synthetic actual | Unit |
|---|---:|---:|---|
{table}

The work-progress value displayed in Tidepath is {float(row['work_progress']):.0%}. It is a UI validation input, not a verified completion rate. The project narrative describes mentoring, family counseling/support, and school safety and mental health workshops. Use attendance logs, counseling/referral records, workshop sign-ins, and source-ledger documents to prepare any real progress report.

## Next steps

Reconcile uploaded receipts by funder category; confirm unpaid commitments; review participant and family participation records; document variance explanations; and obtain bookkeeper review before certifying a report.
"""


def build_grant(row):
    gid = row["validation_id"]
    status = row["status"]
    folder_name = {"APPLYING": "applying", "APPROVED": "approved", "COMPLETED": "completed"}[status]
    folder = OUT / folder_name / gid
    start, end = period_for(row)
    amount = float(row["annual_amount"])
    proposed = budget_rows(row, start, end)
    category_budgets = [float(x["approved_amount_usd"]) for x in proposed]
    total_spend = float(row["total_to_date"])
    spend_by_category = split_cents(total_spend)
    quarter_budget_total = float(row["current_quarter_budget"])
    quarter_spend_total = float(row["current_quarter_spend"])
    quarter_budgets = split_cents(quarter_budget_total)
    quarter_spends = split_cents(quarter_spend_total)
    prior_spends = [round(spend_by_category[i] - quarter_spends[i], 2) for i in range(len(CATEGORIES))]
    if status == "COMPLETED":
        quarter_budgets = [0.0] * len(CATEGORIES)
        quarter_spends = [0.0] * len(CATEGORIES)
        prior_spends = spend_by_category
    if status == "APPLYING":
        spend_by_category = [0.0] * len(CATEGORIES)
        prior_spends = [0.0] * len(CATEGORIES)
        quarter_spends = [0.0] * len(CATEGORIES)
        quarter_budgets = [0.0] * len(CATEGORIES)

    write_text(folder / "application_draft.md", proposal_doc(row))
    if status == "APPLYING":
        csv_text(folder / "proposed_budget.csv", ["grant_id", "mock_funder", "funder_budget_category", "request_amount_usd", "currency", "proposed_start", "proposed_end", "planning_assumption", "data_status"], [
            {"grant_id": gid, "mock_funder": row["funder"], "funder_budget_category": category, "request_amount_usd": f"{value:.2f}", "currency": "USD", "proposed_start": start.isoformat(), "proposed_end": end.isoformat(), "planning_assumption": "Proposed allocation only; subject to funder review and approval", "data_status": "Synthetic application budget; not an award"}
            for (category, _, _), value in zip(CATEGORIES, category_budgets)
        ])
        return

    csv_text(folder / "award_budget.csv", list(proposed[0]), proposed)
    actual_rows = expenditure_rows(row, start, end, spend_by_category, prior_spends, quarter_spends)
    csv_text(folder / "actual_expenses.csv", list(actual_rows[0]) if actual_rows else ["transaction_id", "grant_id", "expense_date", "amount_usd"], actual_rows)
    csv_text(folder / "outcomes_data.csv", ["grant_id", "measure", "target", "synthetic_actual", "unit", "synthetic_source", "measurement_date", "data_status"], outcomes_rows(row))
    fiscal_note = "January 1–December 31" if status == "APPROVED" else f"Historical 12-month period ending {end.isoformat()}"
    write_text(folder / "funder_requirements.md", f"""# Funder Requirements — {row['grant_name']}

**Grant ID:** {gid}  
**Funder:** {row['funder']}  
**Funder fiscal year:** {fiscal_note}  
**Quarterly validation as-of date:** 2026-11-08

> Synthetic validation requirements only. Confirm the real agreement and approved budget before use.

## Reporting and financial controls

Keep expenses in the approved funder categories, retain transaction and receipt references, document the grant allocation for shared costs, and reconcile quarterly. The sample project supports children and families through mentoring, family counseling/support, and safety and mental health workshops in schools. Counseling is provided only by qualified personnel within their scope; the project does not replace clinical treatment or emergency response.

## Synthetic scenario notes

{row['special_note']}

All amounts and program status values are fictional test data.
""")
    report_due = end.isoformat() if status == "COMPLETED" else "2027-01-31"
    narrative_rows = [{"grant_id": gid, "field_name": title, "funder_question": title, "word_limit": limit} for title, limit in QUESTION_LIMITS]
    csv_text(folder / "narrative_limits.csv", ["grant_id", "field_name", "funder_question", "word_limit"], narrative_rows)
    csv_text(folder / "monthly_budget_plan_and_actual_tracker.csv", ["Month", "Project phase", "Budget category", "Planned budget (USD)", "Actual expense (USD)", "Variance: planned minus actual (USD)", "Notes"], tracker_rows(row, start, category_budgets, spend_by_category, prior_spends, quarter_spends))
    csv_text(folder / "category_mapping.csv", ["grant_id", "quickbooks_category", "funder_budget_category", "mapping_rule", "data_status"], [
        {"grant_id": gid, "quickbooks_category": ledger, "funder_budget_category": category, "mapping_rule": "Direct one-to-one synthetic test mapping", "data_status": "Synthetic mapping; verify against ledger and award"}
        for category, _, ledger in CATEGORIES
    ])
    write_text(folder / "report_template.md", make_report_template(row))
    check_rows = []
    for i, (category, _, _) in enumerate(CATEGORIES):
        b, s, qb, qs = category_budgets[i], spend_by_category[i], quarter_budgets[i], quarter_spends[i]
        ratio = qs / qb if qb else 0
        check_rows.append({
            "grant_id": gid, "funder": row["funder"], "funder_fiscal_year": "2026 calendar fiscal year" if status == "APPROVED" else fiscal_note,
            "budget_category": category, "annual_category_budget_usd": f"{b:.2f}", "current_quarter_budget_usd": f"{qb:.2f}",
            "current_quarter_spend_usd": f"{qs:.2f}", "quarter_use_pct": f"{ratio:.4%}", "year_to_date_spend_usd": f"{s:.2f}",
            "remaining_annual_budget_usd": f"{b-s:.2f}",
            "reconciliation_status": "Closed historical fixture" if status == "COMPLETED" else ("Severe overrun — urgent review" if ratio > 1.5 else "Over budget — variance review" if ratio > 1 else "Near limit — monitor" if ratio >= .85 else "Within plan"),
            "review_note": row["special_note"], "data_status": "Synthetic only; not a ledger reconciliation",
        })
    csv_text(folder / "spending_check_by_funder_year.csv", list(check_rows[0]), check_rows)
    if status == "APPROVED":
        # The application draft carries its seven question headings and limits.
        # Keep the approved file set at ten by using the separate progress report.
        (folder / "narrative_limits.csv").unlink(missing_ok=True)
        write_text(folder / "progress_report.md", progress_report(row, amount, total_spend, quarter_budget_total, quarter_spend_total))
    else:
        # Use the ninth standard file as a closeout-ready report and add final settlement as file eleven.
        (folder / "progress_report.md").unlink(missing_ok=True)
        # Approved has ten files, including progress_report.md; this branch is for completed history only.
        settlement_date = datetime.strptime(row["completed_on"], "%Y-%m-%d").date()
        unspent = round(amount - total_spend, 2)
        # Replace narrative limits with the progress report to keep the completed package at ten files before settlement.
        # The proposal itself carries the seven question headings and limits.
        (folder / "narrative_limits.csv").unlink(missing_ok=True)
        write_text(folder / "progress_report.md", f"""# Completion and Outcomes Report — {row['grant_name']}

**Grant ID:** {gid}  
**Completed:** {row['completed_on']}  
**Status:** Completed historical validation record

> Synthetic historical report. Values are fixtures and are not verified program outcomes.

The project scenario is marked complete at 100% work progress. The sample initiative supports children and caregivers through mentoring, family counseling/support, and school-based safety and mental health workshops. Outcome rows and financial amounts in this package are demonstrations only. A real closeout would attach source attendance, consented feedback, counseling/referral documentation, workshop records, and ledger support.

The synthetic final recorded spend is {dollars(total_spend)} against a {dollars(amount)} award. The remaining amount of {dollars(unspent)} is reconciled in `final_settlement.md`.
""")
        write_text(folder / "final_settlement.md", f"""# Final Grant Settlement — {row['grant_name']}

**Grant ID:** {gid}  
**Funder:** {row['funder']}  
**Project end date:** {row['completed_on']}  
**Settlement date:** {settlement_date.isoformat()}  
**Settlement status:** Completed (synthetic validation fixture)

> Fictional closeout record for application validation. The amounts, references, and disposition below are not real transactions or evidence.

## Final financial summary

| Item | Amount |
|---|---:|
| Approved award | {dollars(amount)} |
| Final synthetic eligible expenses | {dollars(total_spend)} |
| Unspent balance | {dollars(unspent)} |
| Synthetic return to funder | {dollars(unspent)} |
| Remaining payable balance | $0.00 |

## Category reconciliation

| Funder budget category | Approved | Final synthetic spend | Balance |
|---|---:|---:|---:|
""" + "\n".join(f"| {category} | {dollars(category_budgets[i])} | {dollars(spend_by_category[i])} | {dollars(category_budgets[i]-spend_by_category[i])} |" for i, (category, _, _) in enumerate(CATEGORIES)) + f"""

## Settlement evidence and approval

- Synthetic remittance reference: `SYN-SETTLEMENT-{gid}`
- Synthetic receipt/reference date: {settlement_date.isoformat()}
- Final program report: included as `progress_report.md`; source verification is not represented.
- Prepared by: Tidepath Validation Finance Desk (fictional)
- Reviewed by: Synthetic bookkeeper review placeholder
- Real closeout action: replace this fixture with the funder's final statement, bank/ledger evidence, approval, and proof of any returned balance.
""")


def main():
    rows = read_grants()
    for row in rows:
        build_grant(row)
    totals = {key: sum(1 for row in rows if row["status"] == status) for key, status in [("applying", "APPLYING"), ("approved", "APPROVED"), ("completed", "COMPLETED")]}
    readme = ["# Validation Grant Documents", "", "These files are synthetic validation examples, not real funder records or Tidepath client data.", "", "Each validation grant has a status-specific document set:", "", "- Applying: 2 files per grant — application draft and proposed budget.", "- Approved: 10 files per grant — proposal, award budget, spending, outcomes, progress, planning, funder and category controls, report template, and funder-year spend check.", "- Completed: 11 files per grant — the completed record set plus a final settlement document.", "", "Each status group contains five grants. Generated monthly plans, expenses, outcomes, and settlement references are mock values created only to exercise the app."]
    write_text(OUT / "README.md", "\n".join(readme))
    print(f"Created {totals['applying']} applying, {totals['approved']} approved, and {totals['completed']} completed validation grants in {OUT}")


if __name__ == "__main__":
    main()
