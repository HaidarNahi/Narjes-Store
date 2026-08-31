"""Storefront sitemap, overriding Frappe's at /sitemap.xml.

Frappe's own sitemap enumerates `www/` pages and doctypes with web views. The
storefront is neither — its URLs come from `website_route_rules` in hooks.py —
so the catalogue would be entirely missing from it. The public face of this
site *is* the storefront, so replacing the route rather than adding a second
one keeps a single sitemap for Search Console to watch.

Resolution order is why this works: `TemplatePage.set_template_path` walks
`reversed(frappe.get_installed_apps())`, and narjes_custom is installed after
frappe, so this file is found first.
"""

import frappe
from narjes_custom.storefront import seo

no_cache = 1


def get_context(context):
	# A shop that is switched off, or has asked search engines to stay away,
	# should not publish a map of itself. 404 rather than an empty sitemap:
	# an empty one is a positive assertion that the site has no pages.
	if not seo.indexable():
		raise frappe.DoesNotExistError

	context.links = seo.sitemap_entries()
	return context
