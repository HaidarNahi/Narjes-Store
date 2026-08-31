"""Storefront robots.txt, overriding Frappe's at /robots.txt.

Frappe's version serves whatever string is typed into Website Settings, which
means the crawl rules live in the database, drift silently, and are lost on a
fresh site. Generating them here keeps them in git alongside the routes they
describe, and — the reason that matters — keeps them *in sync with the shop's
own noindex switch*, which a hand-typed field cannot be.
"""

from frappe.utils import get_url
from narjes_custom.storefront import core, seo

no_cache = 1

# Desk, API and private files. `/api` in particular is disallowed not for
# secrecy (it is already permission-checked) but because crawling it wastes
# the crawl budget that should be going to the catalogue.
#
# Deliberately NOT blocked: `/files` and `/assets`. Product photos are served
# from /files, and a catalogue this visual wants them in Google Images;
# /assets carries the CSS and JS Googlebot needs to render the page at all.
# Blocking either is the classic own-goal in a storefront robots.txt.
PRIVATE = ("/app", "/api", "/private", "/login")

# Per-visitor or duplicate storefront surfaces. These already send
# `noindex` in their head, but noindex only works if the page is crawled
# first — disallowing them here saves the crawl entirely.
TRANSIENT = ("/cart", "/checkout", "/favorites", "/order")


def get_context(context):
	if not seo.indexable():
		# One rule, no ambiguity: the shop is closed to crawlers.
		return {"robots_txt": "User-agent: *\nDisallow: /\n"}

	lines = ["User-agent: *"]
	lines += [f"Disallow: {path}" for path in PRIVATE]
	for lang in core.LANGS:
		lines += [f"Disallow: /{lang}{path}" for path in TRANSIENT]
	# Search-results URLs: infinite in number, thin in content, and every one
	# of them a near-duplicate of /shop.
	lines += [f"Disallow: /{lang}/shop?q=" for lang in core.LANGS]
	lines.append("")
	lines.append(f"Sitemap: {get_url()}/sitemap.xml")

	return {"robots_txt": "\n".join(lines) + "\n"}
