import frappe
from narjes_custom.storefront import core


def get_context(context):
	"""Order confirmation. The reference is shown back to the customer only —
	no order data is looked up here, so a guessed reference reveals nothing."""
	lang = core.resolve_lang()
	core.guard(context)
	core.base_context(context, lang)
	context.reference = frappe.form_dict.get("ref") or ""
	context.no_cache = 1
	return context
