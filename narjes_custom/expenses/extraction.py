"""
narjes_custom.expenses.extraction
==================================
Gemini extraction for expenses — AI is used ONLY here, and only to turn a
sentence into a dict. It never touches the database and never posts anything
to the ledger; that is `narjes_expense.py`'s job, behind a human pressing
Submit.

Same split as `narjes_custom.ai_intake.extraction`, and the same API key
resolution (AI Intake Settings first, then site_config's `gemini_api_key`) —
there is one Gemini key for this site and no reason to make the shop enter it
twice.

The one rule worth stating: the model is given the shop's *real* chart of
accounts and told to choose from it. It is never allowed to invent an account
name, because a hallucinated account either fails the Link validation or, far
worse, quietly matches something real and wrong.
"""

import json
import time

import frappe
from google import genai
from google.genai import types

from narjes_custom.ai_intake import settings as ai_settings
from narjes_custom.ai_intake.extraction import ExtractionError, _is_worth_retrying, resolve_api_key

# Kept deliberately small. Everything here is a hint for a human to check on
# the form, not a fact — the review step is what makes this safe.
EXPENSE_SCHEMA = {
	"type": "object",
	"properties": {
		"description": {
			"type": "string",
			"description": "What the money was spent on, as a short noun phrase.",
		},
		"payee": {
			"type": "string",
			"description": "Who was paid — a company, person or service. Empty string if not stated.",
		},
		"amount": {
			"type": "number",
			"description": "The amount as a plain number, no separators or currency symbol.",
		},
		"expense_account": {
			"type": "string",
			"description": "The exact account name from the provided chart of accounts. Empty string if none clearly fits.",
		},
		"expense_date": {
			"type": "string",
			"description": "ISO date YYYY-MM-DD. Empty string if the text does not say when.",
		},
		"notes": {
			"type": "string",
			"description": "Anything else stated that does not fit the fields above. Empty string if nothing.",
		},
	},
	"required": ["description", "amount"],
}


def get_expense_accounts(company=None) -> list[dict]:
	"""The shop's real expense heads — the only values the model may choose."""
	filters = {"root_type": "Expense", "is_group": 0, "disabled": 0}
	if company:
		filters["company"] = company
	return frappe.get_all(
		"Account",
		filters=filters,
		fields=["name", "account_name"],
		order_by="account_name asc",
	)


# Arabic weekday names, indexed by Python's Monday=0 convention.
_ARABIC_WEEKDAYS = [
	(0, ("الاثنين", "الإثنين")),
	(1, ("الثلاثاء",)),
	(2, ("الاربعاء", "الأربعاء")),
	(3, ("الخميس",)),
	(4, ("الجمعة",)),
	(5, ("السبت",)),
	(6, ("الاحد", "الأحد")),
]


def _build_calendar_block() -> str:
	"""Today's date plus the most recent occurrence of every weekday.

	The model has no clock. Without this it resolves "yesterday" against its
	own training cutoff — in testing that produced a date two years stale,
	which would file the expense into a closed accounting period.

	Note this looks BACKWARDS, unlike the order-intake calendar block which
	looks forwards. An order is delivered in the future; money was spent in
	the past, so "الاثنين" on an expense note means the Monday that has just
	been, never the one coming.
	"""
	from datetime import timedelta

	from frappe.utils import getdate, nowdate

	today = getdate(nowdate())
	lines = [
		f"CURRENT DATE: {today.isoformat()} ({today.strftime('%A')})",
		f"YESTERDAY (امس / البارحة): {(today - timedelta(days=1)).isoformat()}",
		f"DAY BEFORE YESTERDAY (اول امس): {(today - timedelta(days=2)).isoformat()}",
		"MOST RECENT OCCURRENCE OF EACH WEEKDAY — use these exact dates when a day is named:",
	]
	for weekday, names in _ARABIC_WEEKDAYS:
		# The most recent such day; a day named today means today itself,
		# because an expense can perfectly well have been paid this morning.
		delta = (today.weekday() - weekday) % 7
		lines.append(f"  {' / '.join(names[:2])} -> {(today - timedelta(days=delta)).isoformat()}")
	return "\n".join(lines)


def _build_system_prompt(accounts: list[dict], currency: str) -> str:
	listing = "\n".join(f"- {a['name']}" for a in accounts)
	return f"""You read a short note about money the shop spent and turn it into structured data.

{_build_calendar_block()}

The shop is Narjes Store, a design and gifts business in Baghdad, Iraq.
Notes may be written in Arabic, English, or a mix of both. Arabic-Iraqi
phrasing is common.

AMOUNTS
- The shop's currency is {currency}. Amounts are written in {currency} unless
  a different currency is explicitly named.
- Return the amount as a plain number: "131,000" and "131 الف" are both 131000.
- Arabic shorthand: "الف"/"ألف" means thousand, "مليون" means million.
- If a foreign currency IS explicitly named (e.g. "$100"), still return the
  number as written and say so in `notes`. Do NOT convert it yourself — you
  do not know the rate, and a wrong guess becomes a wrong ledger entry.

ACCOUNT
- `expense_account` MUST be copied exactly from this list, character for
  character, or left as an empty string:
{listing}
- Never invent an account name and never adapt one. If nothing clearly fits,
  return an empty string and let the human choose.

DATE
- Only fill `expense_date` if the note actually says when, and take the value
  from the CURRENT DATE block above — never from your own sense of today.
- Expenses are always in the past. Never return a date after CURRENT DATE.
- If the note says nothing about timing, return an empty string rather than
  guessing.

Return only the structured fields. Anything you are unsure about belongs in
`notes` rather than in a field you had to guess at."""


def extract_expense(raw_text: str, company: str | None = None) -> dict:
	"""Parse a free-text expense note into a dict of form fields.

	Raises ExtractionError on API failure or an unusable response. Never
	writes anything.
	"""
	if not (raw_text or "").strip():
		raise ExtractionError("Nothing to read — write what you spent first.")

	settings = ai_settings.get_settings()
	api_key = resolve_api_key(settings)
	if not api_key:
		raise ExtractionError(
			"Gemini API key not configured. Set it in 'AI Intake Settings' or run: "
			"bench --site narjes.store set-config gemini_api_key YOUR_KEY"
		)

	company = (
		company or frappe.defaults.get_user_default("Company") or frappe.db.get_value("Company", {}, "name")
	)
	currency = frappe.db.get_value("Company", company, "default_currency") or "IQD"
	accounts = get_expense_accounts(company)
	if not accounts:
		raise ExtractionError(f"No expense accounts found for {company}.")

	timeout_seconds = ai_settings.get_int("request_timeout", settings)
	max_retries = max(0, ai_settings.get_int("max_retries", settings))

	client = genai.Client(
		api_key=api_key,
		http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
	)
	config = types.GenerateContentConfig(
		system_instruction=_build_system_prompt(accounts, currency),
		response_mime_type="application/json",
		response_schema=EXPENSE_SCHEMA,
		# Lower than the order-intake temperature: this is a short, literal
		# transcription task with one right answer, not a task with any room
		# for interpretation.
		temperature=0.0,
		max_output_tokens=ai_settings.get_int("max_tokens", settings),
	)

	response = None
	last_error = None
	attempts_made = 0
	for attempt in range(max_retries + 1):
		attempts_made = attempt + 1
		try:
			response = client.models.generate_content(
				model=ai_settings.get_str("model_name", settings),
				contents=[raw_text],
				config=config,
			)
			break
		except Exception as e:
			last_error = e
			if attempt == max_retries or not _is_worth_retrying(e):
				break
			time.sleep(2**attempt)

	if response is None:
		attempts = "1 attempt" if attempts_made == 1 else f"{attempts_made} attempts"
		raise ExtractionError(f"Gemini API call failed after {attempts}: {last_error}")

	try:
		extracted = json.loads(response.text)
	except Exception as e:
		raise ExtractionError(f"Could not read the model's response as JSON: {e}")

	return sanitize(extracted, accounts)


def sanitize(extracted: dict, accounts: list[dict]) -> dict:
	"""Discard anything the model got wrong before it reaches the form.

	Pure and DB-free so it can be unit-tested without a site. The account
	check is the important one: a name that is not in the shop's chart of
	accounts is dropped rather than passed through, so the field arrives
	empty and the human picks — which is the correct outcome for "the model
	was not sure".
	"""
	valid = {a["name"] for a in accounts}
	account = (extracted.get("expense_account") or "").strip()

	amount = extracted.get("amount")
	try:
		amount = float(amount)
	except TypeError, ValueError:
		amount = 0.0

	return {
		"description": (extracted.get("description") or "").strip(),
		"payee": (extracted.get("payee") or "").strip(),
		"amount": amount if amount > 0 else 0.0,
		"expense_account": account if account in valid else "",
		"expense_date": (extracted.get("expense_date") or "").strip(),
		"notes": (extracted.get("notes") or "").strip(),
	}
