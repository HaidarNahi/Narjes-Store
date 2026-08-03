"""
narjes_custom.ai_intake.settings
================================
Single accessor for the `AI Intake Settings` Single doctype.

Every knob the intake flow reads lives here, with a hardcoded fallback for
each one. The fallbacks are not decoration: intake runs inside a user
request, and a Single row that is missing (fresh site, mid-migrate) or
holding a garbage value must degrade to the old hardcoded behaviour rather
than take the whole intake down. That is why `get_setting` swallows
everything — callers get a usable value or the default, never an exception.

The doctype JSON's `default` for each field is kept in sync with DEFAULTS
below; both exist because the JSON default only applies when a field is
first created, while these apply on every read.
"""

import frappe

# Fallback for every setting, used when the Single row can't be read or
# holds a value that won't coerce. Keep in sync with the doctype JSON.
DEFAULTS = {
	"enabled": 1,
	# Gemini API
	"model_name": "gemini-2.5-flash",
	"temperature": 0.1,
	"max_tokens": 4096,
	"request_timeout": 60,
	"max_retries": 2,
	# Prompt
	"append_governorates": 1,
	# Catalog
	"append_catalog": 1,
	"catalog_include_item_name": 1,
	"max_catalog_items": 0,
	"catalog_item_groups": "",
	# Examples
	"append_examples": 1,
	"few_shot_examples": "",
	# Matching
	"enable_fuzzy_name_match": 1,
	"fuzzy_match_threshold": 85,
	# Order defaults and guardrails
	"default_currency": "IQD",
	"default_uom": "Nos",
	"default_warehouse": None,
	"max_discount_percentage": 50.0,
	"allow_retry_failed_intake": 0,
}

SETTINGS_DOCTYPE = "AI Intake Settings"


def get_settings():
	"""The settings doc, or None if it can't be read.

	Cached by Frappe and invalidated on save, so this is cheap to call
	repeatedly within one request.
	"""
	try:
		return frappe.get_cached_doc(SETTINGS_DOCTYPE)
	except Exception:
		return None


def get_setting(fieldname: str, settings=None):
	"""Raw value of one setting, falling back to DEFAULTS.

	Pass `settings` when reading several in a row to avoid re-fetching.
	"""
	default = DEFAULTS.get(fieldname)
	if settings is None:
		settings = get_settings()
	if settings is None:
		return default
	try:
		value = settings.get(fieldname)
	except Exception:
		return default
	if value is None or value == "":
		return default
	return value


def get_bool(fieldname: str, settings=None) -> bool:
	value = get_setting(fieldname, settings)
	try:
		return bool(int(value))
	except (TypeError, ValueError):
		return bool(DEFAULTS.get(fieldname))


def get_int(fieldname: str, settings=None) -> int:
	value = get_setting(fieldname, settings)
	try:
		return int(float(value))
	except (TypeError, ValueError):
		return int(DEFAULTS.get(fieldname) or 0)


def get_float(fieldname: str, settings=None) -> float:
	value = get_setting(fieldname, settings)
	try:
		return float(value)
	except (TypeError, ValueError):
		return float(DEFAULTS.get(fieldname) or 0)


def get_str(fieldname: str, settings=None) -> str:
	value = get_setting(fieldname, settings)
	if value is None:
		return ""
	return str(value)


def get_lines(fieldname: str, settings=None) -> list[str]:
	"""A newline-separated Small Text field as a list of non-empty lines."""
	return [line.strip() for line in get_str(fieldname, settings).splitlines() if line.strip()]


def is_enabled() -> bool:
	return get_bool("enabled")
