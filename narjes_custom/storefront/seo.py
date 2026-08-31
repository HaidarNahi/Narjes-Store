"""Storefront SEO: Schema.org structured data, emitted as JSON-LD (plan W10.3).

Every page ships **one** `<script type="application/ld+json">` holding a single
`@graph`, rather than a scatter of separate script tags. One graph lets the
nodes reference each other by `@id` — a Product's `seller`, a page's
`publisher`, the breadcrumb's owner all point at the same Organization node
instead of restating it — which is both smaller on the wire and what Google's
parser prefers when it reconciles entities.

Two rules hold throughout:

1. **Never assert what the shop has not entered.** A missing price means the
   `offers` key is absent, not `null` and not a guess. `_prune` drops empty
   values recursively so a half-filled Settings doc can never emit
   `"telephone": ""` — an empty string is a claim, absence is not, and Google
   flags the former as an error while ignoring the latter.
2. **Mirror the page.** Structured data that describes something the visitor
   cannot see is a manual-action risk. The breadcrumb graph matches the
   rendered breadcrumb, the ItemList matches the grid that is actually on
   screen, and no rating is emitted anywhere because the shop has no reviews.
"""

from urllib.parse import quote
from xml.sax.saxutils import escape

import frappe
from frappe.utils import cint, get_url

from narjes_custom.storefront import core

CURRENCY = "IQD"
COUNTRY = "IQ"

# Stable @id anchors. Fragment ids on the site root keep every node globally
# unique without inventing URLs that do not resolve.
ORG_ID = "#organization"
WEBSITE_ID = "#website"


# ------------------------------------------------------------------ helpers


def abs_url(path):
	"""Absolute URL for a stored file path, left alone if already absolute."""
	if not path:
		return None
	if path.startswith(("http://", "https://", "//")):
		return path
	return get_url() + ("" if path.startswith("/") else "/") + path


def _prune(value):
	"""Drop None, empty strings, empty lists/dicts — recursively.

	This is what keeps rule 1 above true without every builder below having to
	branch on each optional field. Note `0` and `False` are deliberately kept:
	a price of 0 or `"value": false` is a real assertion, unlike a blank field.
	"""
	if isinstance(value, dict):
		out = {}
		for key, val in value.items():
			cleaned = _prune(val)
			if cleaned is not None and cleaned != "" and cleaned != [] and cleaned != {}:
				out[key] = cleaned
		return out
	if isinstance(value, (list, tuple)):
		out = [_prune(v) for v in value]
		return [v for v in out if v is not None and v != "" and v != [] and v != {}]
	if isinstance(value, str):
		return value.strip()
	return value


def shop_name(lang):
	"""The business name — deliberately NOT `meta_title`.

	`meta_title` is a page-title field: long, keyword-shaped, and in practice
	filled with a slogan. Feeding it into `name` made the Organization, the
	WebSite and every product's `brand.name` read as a full marketing
	sentence, which is what Google would then treat as the brand.
	"""
	s = core.settings()
	return core.pick(s, "shop_name", lang) or ("النرجس" if lang == "ar" else "Narjes Store")


def _page_url(lang, path=""):
	return f"{get_url()}/{lang}{path or ''}"


# ------------------------------------------------------------------- nodes


def organization_ld(lang):
	"""The shop itself. Typed as both Store and Organization: Store carries the
	retail semantics (address, hours) while Organization is what `publisher`
	and `seller` references expect to resolve to.
	"""
	s = core.settings()
	address = core.pick(s, "address", lang)
	instagram = (s.get("instagram") or "").strip()
	phone = (s.get("phone") or "").strip()
	whatsapp = (s.get("whatsapp") or "").strip()

	return {
		"@type": ["Organization", "Store"],
		"@id": get_url() + ORG_ID,
		"name": shop_name(lang),
		"url": _page_url(lang),
		"description": core.pick(s, "meta_description", lang),
		"logo": abs_url("/assets/narjes_custom/images/narjes-logo.svg"),
		"image": abs_url(core.public_file(s.get("og_image")))
		or abs_url("/assets/narjes_custom/images/narjes-logo.svg"),
		"telephone": phone or (f"+{whatsapp.lstrip('+')}" if whatsapp else None),
		"email": (s.get("email") or "").strip(),
		# `sameAs` is how Google ties the site to the shop's existing Instagram
		# audience — the strongest entity signal this store actually has.
		"sameAs": [instagram] if instagram else [],
		"address": {
			"@type": "PostalAddress",
			"streetAddress": address,
			"addressCountry": COUNTRY,
		}
		if address
		else None,
		"openingHours": (s.get("working_hours") or "").strip(),
		"currenciesAccepted": CURRENCY,
		"paymentAccepted": "Cash on Delivery",
		"areaServed": {"@type": "Country", "name": "Iraq"},
	}


def website_ld(lang):
	"""WebSite node carrying the search action.

	The `SearchAction` is what makes a sitelinks search box possible on the
	brand query — it points at the shop's own `?q=` route, which already
	exists and renders real results.
	"""
	return {
		"@type": "WebSite",
		"@id": get_url() + WEBSITE_ID,
		"name": shop_name(lang),
		"url": _page_url(lang),
		"inLanguage": lang,
		"publisher": {"@id": get_url() + ORG_ID},
		"potentialAction": {
			"@type": "SearchAction",
			"target": {
				"@type": "EntryPoint",
				"urlTemplate": f"{get_url()}/{lang}/shop?q={{search_term_string}}",
			},
			"query-input": "required name=search_term_string",
		},
	}


def breadcrumb_ld(lang, crumbs):
	"""BreadcrumbList from [(name, path), ...] where path is language-relative.

	The final crumb is the current page and intentionally carries an `item`
	too; Google accepts it and it keeps the trail self-describing.
	"""
	if not crumbs:
		return None
	return {
		"@type": "BreadcrumbList",
		"@id": _page_url(lang, crumbs[-1][1]) + "#breadcrumb",
		"itemListElement": [
			{
				"@type": "ListItem",
				"position": i,
				"name": name,
				"item": _page_url(lang, path),
			}
			for i, (name, path) in enumerate(crumbs, start=1)
		],
	}


def product_ld(p, lang, *, gallery=None):
	"""Product + Offer for a single item.

	`offers` is omitted entirely when the item has no price. The alternative —
	an Offer with a null or zero price — is an untrue statement about the
	shop's terms and Google rejects the whole Product node for it, losing the
	rich result on every *other* product that shares the page.
	"""
	images = [abs_url(shot["image"]) for shot in (gallery or [])] or [abs_url(p.get("image"))]
	url = f"{get_url()}{p.get('route') or ''}"

	node = {
		"@type": "Product",
		"@id": url + "#product",
		"name": p.get("title"),
		"description": p.get("short") or p.get("long") or "",
		"image": [i for i in images if i],
		"sku": p.get("item_code"),
		"url": url,
		"category": p.get("category"),
		"brand": {"@type": "Brand", "name": shop_name(lang)},
		# No `inLanguage` here. It is a CreativeWork property, and Product is not
		# a CreativeWork — schema.org's validator warns on it. The language of a
		# product page is already carried by `<html lang>`, the hreflang set, and
		# the `inLanguage` on this page's WebPage/CollectionPage node, all of
		# which are the right places for it.
	}

	if p.get("has_price"):
		node["offers"] = {
			"@type": "Offer",
			"@id": url + "#offer",
			"url": url,
			"price": p.get("rate"),
			"priceCurrency": CURRENCY,
			"availability": (
				"https://schema.org/InStock" if p.get("in_stock") else "https://schema.org/OutOfStock"
			),
			"itemCondition": "https://schema.org/NewCondition",
			"seller": {"@id": get_url() + ORG_ID},
			"areaServed": {"@type": "Country", "name": "Iraq"},
		}

	# Made-to-order lead time is a genuine, visible product fact — it renders in
	# the facts strip — so it belongs in the graph as a plain property.
	if p.get("made_to_order") and cint(p.get("lead_time")):
		node["additionalProperty"] = {
			"@type": "PropertyValue",
			"name": "Lead time (days)" if lang == "en" else "مدة التنفيذ (أيام)",
			"value": cint(p.get("lead_time")),
		}

	return node


def item_list_ld(products, lang, *, path="", name=None):
	"""ItemList for a grid of products.

	Uses the URL-only ListItem form, which is what Google documents for a
	"summary" listing page — the detail lives on each product page, and
	restating it here would just be two sources of truth for the same offer.
	"""
	if not products:
		return None
	return {
		"@type": "ItemList",
		"@id": _page_url(lang, path) + "#itemlist",
		"name": name,
		"numberOfItems": len(products),
		"itemListElement": [
			{
				"@type": "ListItem",
				"position": i,
				"url": f"{get_url()}{p.get('route') or ''}",
				"name": p.get("title"),
			}
			for i, p in enumerate(products, start=1)
		],
	}


def page_ld(lang, page_type, *, path="", name=None, description=None):
	"""A typed page node (AboutPage, ContactPage, …).

	Typing the About and Contact pages is what lets Google attach the shop's
	phone, address and hours to the knowledge panel for the brand query
	instead of treating them as loose text on an anonymous page.
	"""
	return {
		"@type": page_type,
		"@id": _page_url(lang, path) + "#page",
		"name": name,
		"description": description,
		"url": _page_url(lang, path),
		"inLanguage": lang,
		"isPartOf": {"@id": get_url() + WEBSITE_ID},
		"about": {"@id": get_url() + ORG_ID},
	}


def collection_page_ld(lang, *, path="", name=None, description=None):
	"""CollectionPage wrapper for shop/category listings."""
	return {
		"@type": "CollectionPage",
		"@id": _page_url(lang, path) + "#page",
		"name": name,
		"description": description,
		"url": _page_url(lang, path),
		"inLanguage": lang,
		"isPartOf": {"@id": get_url() + WEBSITE_ID},
		"about": {"@id": get_url() + ORG_ID},
	}


# ------------------------------------------------------------------- graph


def graph(context, *nodes):
	"""Attach the page's JSON-LD graph to the render context.

	Organization and WebSite are prepended on every page: they are what the
	`@id` references in the page-specific nodes resolve against, and repeating
	them per page is how a site without a crawlable "about" hub still gets a
	consistent entity read.
	"""
	lang = context.get("lang") or core.DEFAULT_LANG

	# A page the shop has asked search engines to ignore should not also be
	# handing them a machine-readable description of itself.
	if context.get("noindex"):
		context.jsonld = None
		return context

	all_nodes = [organization_ld(lang), website_ld(lang)] + [n for n in nodes if n]
	context.jsonld = _prune(
		{
			"@context": "https://schema.org",
			"@graph": all_nodes,
		}
	)
	return context


def crumb_labels(lang):
	t = core.translations(lang)
	return t.get("home"), t.get("shop")


# ------------------------------------------------------------------ sitemap

# Indexable static routes, language-relative. The cart, checkout, favourites
# and order pages are absent on purpose — they are noindex, and a sitemap that
# advertises noindex URLs is the most common cause of "Submitted URL marked
# noindex" errors in Search Console.
STATIC_ROUTES = ("", "/shop", "/about", "/contact", "/custom-design")


def indexable():
	"""Whether the shop is currently offering itself to crawlers at all."""
	s = core.settings()
	if not core.storefront_enabled():
		return False
	return not (bool(cint(s.get("noindex", 1))) if s else True)


def _sitemap_url(lang, path):
	"""Percent-encoded, XML-safe URL for a sitemap entry.

	The sitemap protocol requires both, and Frappe's Jinja environment does
	*not* autoescape (it is built without `autoescape=True`), so a slug
	carrying an `&` would otherwise produce a sitemap that fails to parse and
	takes every URL after it down with the document.
	"""
	return escape(quote(_page_url(lang, path), safe=":/"))


def _alternates(path):
	return [{"hreflang": l, "href": _sitemap_url(l, path)} for l in core.LANGS]


def sitemap_entries():
	"""Every indexable storefront URL, in both languages.

	Frappe's own /sitemap.xml is built from `get_pages()` and doctypes with web
	views; the storefront is neither — its routes come from
	`website_route_rules` — so none of the catalogue would ever appear in it.
	This replaces it for this site.

	Each path is emitted once per language with `xhtml:link` alternates
	pointing at every other language, which is the sitemap-side half of the
	hreflang pairing already declared in the page head. Declaring it in both
	places is what makes Google trust it.
	"""
	paths = [(path, None) for path in STATIC_ROUTES]

	for row in frappe.get_all(
		"Narjes Storefront Category",
		filters={"published": 1},
		fields=["name", "slug", "modified"],
	):
		slug = row.get("slug") or frappe.scrub(row["name"]).replace("_", "-")
		paths.append((f"/c/{slug}", row.get("modified")))

	for row in frappe.get_all(
		"Item",
		filters={"disabled": 0, "custom_publish_on_website": 1},
		fields=["item_code", "custom_web_route", "modified"],
	):
		paths.append((f"/p/{core.slug_for(row)}", row.get("modified")))

	entries = []
	for path, modified in paths:
		for lang in core.LANGS:
			entries.append(
				{
					"loc": _sitemap_url(lang, path),
					"lastmod": modified.strftime("%Y-%m-%d") if modified else None,
					"alternates": _alternates(path),
				}
			)
	return entries
