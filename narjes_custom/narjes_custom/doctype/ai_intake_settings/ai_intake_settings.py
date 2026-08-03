# Copyright (c) 2026, Narjes Custom and contributors
# For license information, please see license.txt

import json
import time

import frappe
from frappe.model.document import Document
from frappe.utils import cint, flt


class AIIntakeSettings(Document):
	def validate(self):
		self.normalize_numbers()
		self.validate_api_params()
		self.validate_matching()
		self.validate_guardrails()
		self.validate_catalog_filters()
		self.validate_few_shot_examples()

	def normalize_numbers(self):
		"""Coerce the numeric settings before anything compares them.

		Values reach a doctype as strings from more than one direction — the
		docfield `default` is a string, and so is anything posted through the
		REST API — so the range checks below can't assume they got numbers.
		"""
		for fieldname in (
			"max_tokens",
			"request_timeout",
			"max_retries",
			"max_catalog_items",
			"fuzzy_match_threshold",
			"max_discount_percentage",
		):
			self.set(fieldname, cint(self.get(fieldname)))
		for fieldname in (
			"enabled",
			"append_governorates",
			"append_catalog",
			"catalog_include_item_name",
			"append_examples",
			"enable_fuzzy_name_match",
			"allow_retry_failed_intake",
		):
			self.set(fieldname, cint(self.get(fieldname)))

	# -- Gemini API ---------------------------------------------------------

	def validate_api_params(self):
		# Temperature is a Select of strings, not a Float, because this site's
		# number format is "#,###" — no decimal separator, so Frappe renders
		# and stores every Float without decimals and a temperature of 0.1
		# silently becomes 0. The Select can only offer valid values, so this
		# check exists for anything written through the API instead. Above ~1
		# the model paraphrases rather than extracts, which is the one thing
		# this prompt must never do.
		if not (0 <= flt(self.temperature) <= 2):
			frappe.throw("Temperature must be between 0 and 2. Extraction wants it near 0.")

		if not (256 <= self.max_tokens <= 65536):
			frappe.throw("Max Output Tokens must be between 256 and 65536.")

		if not (5 <= self.request_timeout <= 600):
			frappe.throw("Request Timeout must be between 5 and 600 seconds.")

		if not (0 <= self.max_retries <= 5):
			frappe.throw("Max Retries must be between 0 and 5.")

	# -- Customer matching --------------------------------------------------

	def validate_matching(self):
		if not (0 <= self.fuzzy_match_threshold <= 100):
			frappe.throw("Fuzzy Match Threshold must be between 0 and 100.")

		# A low floor makes every unfamiliar name look like an existing
		# customer, which is worse than no suggestion at all
		if self.enable_fuzzy_name_match and self.fuzzy_match_threshold < 60:
			frappe.msgprint(
				f"A Fuzzy Match Threshold of {self.fuzzy_match_threshold} is very low — "
				"unrelated customers will be suggested as matches. 85 is the tested default.",
				indicator="orange",
				title="Low match threshold",
			)

	# -- Guardrails ---------------------------------------------------------

	def validate_guardrails(self):
		if not (0 <= self.max_discount_percentage <= 100):
			frappe.throw("Max Discount % must be between 0 and 100.")

		if self.max_catalog_items < 0:
			frappe.throw("Max Catalog Items cannot be negative. Use 0 for no limit.")

	# -- Catalog ------------------------------------------------------------

	def validate_catalog_filters(self):
		groups = [line.strip() for line in (self.catalog_item_groups or "").splitlines() if line.strip()]
		unknown = [g for g in groups if not frappe.db.exists("Item Group", g)]
		if unknown:
			frappe.throw(
				"These Item Groups don't exist: {0}. "
				"Enter one existing Item Group per line, or leave the field blank "
				"to send the whole catalog.".format(", ".join(unknown))
			)

	# -- Few-shot examples --------------------------------------------------

	def validate_few_shot_examples(self):
		"""Reject a malformed override at save time.

		extraction.py silently falls back to the built-in examples if this
		won't parse, so without this check a typo would degrade every
		extraction quietly instead of failing loudly here.
		"""
		raw = (self.few_shot_examples or "").strip()
		if not raw:
			return

		try:
			parsed = json.loads(raw)
		except Exception as e:
			frappe.throw(f"Custom Few-Shot Examples is not valid JSON: {e}")

		if not isinstance(parsed, list) or not parsed:
			frappe.throw("Custom Few-Shot Examples must be a non-empty JSON array.")

		for i, example in enumerate(parsed, 1):
			if not isinstance(example, dict):
				frappe.throw(f"Example {i} must be an object with 'input' and 'output' keys.")
			if not example.get("input"):
				frappe.throw(f"Example {i} is missing a non-empty 'input'.")
			if not isinstance(example.get("output"), dict):
				frappe.throw(f"Example {i} must have an 'output' object holding the expected JSON.")

		# Re-serialize so the stored value is consistently formatted
		self.few_shot_examples = json.dumps(parsed, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Form actions
# ---------------------------------------------------------------------------

SAMPLE_INTAKE_TEXT = (
	"طلب جديد:\n"
	"احمد محمد - 07701234567\n"
	"لوحة كانفاس 30*40 عدد 2 بسعر 20000"
)


def _check_permission():
	frappe.has_permission("AI Intake Settings", ptype="write", throw=True)


@frappe.whitelist()
def preview_system_prompt() -> dict:
	"""
	The exact system instruction the next extraction would send, assembled
	from the saved settings — prompt, governorate list, catalog, examples and
	extra instructions.
	"""
	_check_permission()

	from narjes_custom.ai_intake import settings as ai_settings
	from narjes_custom.ai_intake.extraction import (
		build_system_prompt,
		get_prompt_catalog,
		resolve_few_shot_examples,
	)

	settings = ai_settings.get_settings()
	prompt = build_system_prompt(settings)

	return {
		"prompt": prompt,
		"characters": len(prompt),
		# Rough only: Gemini bills real tokens, and Arabic runs well above
		# 4 chars/token. Enough to tell "fine" from "this prompt is huge".
		"approx_tokens": len(prompt) // 4,
		"catalog_items": len(get_prompt_catalog(settings)) if ai_settings.get_bool("append_catalog", settings) else 0,
		"examples": len(resolve_few_shot_examples(settings)) if ai_settings.get_bool("append_examples", settings) else 0,
	}


@frappe.whitelist()
def test_connection() -> dict:
	"""
	Run one real extraction against a short sample order to prove the API key,
	model name and prompt actually work together. Costs one API call.
	"""
	_check_permission()

	from narjes_custom.ai_intake import settings as ai_settings
	from narjes_custom.ai_intake.extraction import ExtractionError, extract_order, resolve_api_key

	settings = ai_settings.get_settings()

	if settings is not None and settings.get("api_key"):
		key_source = "AI Intake Settings"
	elif frappe.conf.get("gemini_api_key"):
		key_source = "site config (gemini_api_key)"
	else:
		return {
			"ok": False,
			"error": (
				"No Gemini API key found. Set one here, or run: "
				"bench --site {0} set-config gemini_api_key YOUR_KEY".format(frappe.local.site)
			),
		}

	if not resolve_api_key(settings):
		return {"ok": False, "error": "The configured Gemini API key is empty."}

	started = time.monotonic()
	try:
		extracted = extract_order(SAMPLE_INTAKE_TEXT)
	except ExtractionError as e:
		return {
			"ok": False,
			"key_source": key_source,
			"model": ai_settings.get_str("model_name", settings),
			"elapsed": round(time.monotonic() - started, 2),
			"error": str(e),
		}

	return {
		"ok": True,
		"key_source": key_source,
		"model": ai_settings.get_str("model_name", settings),
		"elapsed": round(time.monotonic() - started, 2),
		"sample_text": SAMPLE_INTAKE_TEXT,
		"extracted": json.dumps(extracted, ensure_ascii=False, indent=2),
	}
