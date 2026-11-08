# Grant Portfolio Desk

A local web app for preparing funder-specific grant answers, reviewing restricted budgets, scheduling quarterly close work, and tracking reports. The app interface is in English. Its 15 built-in validation grants are synthetic examples and stay separate from uploaded grant totals.

## Run locally

1. Install Python 3.10 or later.
2. Open a terminal in this folder and run `python -m pip install -r requirements.txt`.
3. Run `python app.py`.
4. Open `http://127.0.0.1:8765`. Use **Watch animated tour** or visit `/tour` to see the guided feature walkthrough.
5. Upload a ZIP containing grant source files. Confirm staff reviewed the facts before generating answers.
6. Download the complete web app ZIP at `/download/tidepath-grant-webapp.zip` while the local app is running.

The app listens only on `127.0.0.1`. Uploaded files are read in memory and are not extracted to disk. The latest five generated results are held in memory until the app closes.

## Optional OpenAI answer polishing

Open **Optional: OpenAI answer polishing**, enable the checkbox, and enter an OpenAI API key. The default model is `gpt-4.1-mini`; you can change the model name. Each drafted answer is sent through three sequential Responses API calls. The instructions ask the model to preserve facts and figures and return only revised prose. The final answer is fitted to its funder word limit.

Only the draft answer text is sent to OpenAI; the uploaded ZIP and its other files are not. The key is held in memory for the request, is not logged or saved to generated files, and Responses API storage is disabled. OpenAI API calls use credits available to the linked API organization, if any, or incur usage charges under that organization's billing. Eligibility and available credits depend on the account and linked organization. Check the [OpenAI API credits guide](https://developers.openai.com/api/docs/guides/chatgpt-api-credits) and [text generation documentation](https://developers.openai.com/api/docs/guides/text). This polishing step is not fact-checking; staff must review the answer and sources before submission.

## Upload ZIP structure

The app matches files using `grant_id` and can process multiple grant folders in one ZIP.

- `organization_fact_sheet.md` (required; `fact_sheet.md` is also accepted)
- `award_budget.csv` or `budget.csv`: grant ID, funder, category, approved amount
- `actual_expenses.csv` or `monthly_budget_actuals.csv`: date/month, category, actual amount
- `funder_requirements.csv` and/or `funder_requirements.md`: funder and fiscal-year start month
- `narrative_limits.csv`: grant ID, question/field, and word limit
- `application_draft.md` or `proposal_reference.md`: optional source responses and narrative
- `outcomes_data.csv`: optional outcome targets and results for work-progress indicators
- `report_schedule.csv` or `report_queue.csv`: report due date and reporting period

Question rows can use `field_name` for the short answer title, `funder_question` or `question_text` for the prompt, and `maximum`, `word_limit`, or `maximum_words` for the limit. Transactions should include dates, categories, amounts, approval status, and receipt or journal references when available.

For the annual spending charts, budget rows should include `budget_year`, `calendar_year`, or `year` (four digit calendar year), or a period start and end such as `grant_start` and `grant_end`. Accepted date fields also include `grant_start_date`, `grant_end_date`, `budget_period_start`, `budget_period_end`, `period_start`, `period_end`, `start_date`, and `end_date`. Dated multi-year budgets are allocated by the days overlapping each calendar year. A row without year or period dates is assigned to the current calendar year; no next-year forecast is inferred without a budget allocation for that year.

## Workspace and downloads

- **Priority overview:** an Upcoming banner lists the nearest report and quarterly-close dates. The overview also shows category budget use and three separate annual spending-mix pie charts labeled Last year, This year, and Next year. Each pie has a readable category legend with dollar amounts and shares.
- **Annual spending mix:** each yearly pie uses the same five named categories: Children & mentoring, Family support, School safety, Mental health, and Staff, materials & evaluation. Each legend shows each category's amount and percentage. School safety and mental-health combined categories are split across those two categories. Last year uses uploaded expense actuals. This-year estimates sum budget amounts allocated to the current calendar year, and next-year forecasts use budget amounts assigned to or overlapping next calendar year. Undated budget rows are assigned to the current year. No spending run rate or renewal scenario is carried forward, so a year without an identified budget shows a zero forecast. These forecasts are not commitments.
- **Grant progress:** uploaded live grants and the separate validation groups. Validation examples include five applying, five approved, and five completed grants. The approved group includes 2.5% current-quarter utilization and a severe 267% overspend case. Completed records appear gray in a collapsible historical section. These examples are excluded from live totals and reconciliation.
- **Validation grant files:** Each applying grant has 2 documents (proposal and proposed budget); each approved grant has 10 (proposal, award budget, expenses, outcomes, progress report, planning and controls); each completed grant has 11, including a final settlement. Open a grant card document list to download its files. The standalone files are in `validation_documents/`; `build_validation_documents.py` regenerates them from the synthetic CSV.
- **Sample grants:** `sample_grants/` contains ten fictional proposals and their ten matching monthly spending CSVs, clearly marked as synthetic challenge data.
- **Budget & close:** category reconciliation by funder fiscal year and quarterly close checks.
- **Reports & reminders:** report queue with special circumstances and dated quarterly reminders.
- **Funder answers:** grant and question-grouped drafts with editable answer text and word counts.

The summary workbook includes Dashboard, Portfolio, Category Spend, Application Limits, Report Queue, Grant Reminders, Financial Close, Validation Grants, and Read Me sheets. The downloadable result ZIP also includes all validation grant documents, narrative and report drafts, CSV exports, the workbook, and reminder calendar.

## Review notes

- The fact-review checkbox is an operator attestation; it does not verify claims against source documents.
- Quarterly close compares uploaded ledger data with grant budgets. It does not connect to or post entries in a bank or accounting system. Bookkeeper review is still required.
- Fiscal-year start month defaults to October when it cannot be identified. Set `fiscal_year_start_month` to `1`, `7`, or `10` in `funder_requirements.csv` for January, July, or October.
- The default category alert threshold is 85%; categories above 110% are marked as significant overspends.
- Validation grant records are fictional demonstration rows, not real awards or expenses.
