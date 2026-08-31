import frappe
from narjes_custom.storefront import core


def get_context(context):
	"""Order confirmation. The reference is shown back to the customer only —
	no order data is looked up here, so a guessed reference reveals nothing."""
	lang = core.resolve_lang()
	core.guard(context)
	# One URL per order: never indexed, and no canonical that would invite a
	# crawler to try neighbouring references.
	core.base_context(context, lang, noindex=True)
	context.reference = frappe.form_dict.get("ref") or ""
	context.no_cache = 1
	return context
