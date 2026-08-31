# Storefront SEO

Implements plan **W10.3**: canonical + hreflang, per-language `sitemap.xml`,
`robots.txt`, and Schema.org structured data as JSON-LD for Google rich
results.

## Where things live

| Concern | File |
|---|---|
| Structured data (all node builders) | `narjes_custom/storefront/seo.py` |
| Emission — one `<script>` per page | `templates/storefront/base.html` |
| Per-page graph assembly | `www/store/*.py` |
| `/sitemap.xml` | `www/sitemap.py` + `www/sitemap.xml` |
| `/robots.txt` | `www/robots.py` + `www/robots.txt` |
| Slug sanitisation | `storefront/core.py` → `sanitize_slug` |
| Tests | `narjes_custom/tests/test_seo.py` |

## The one thing that actually gates Google

Everything below is inert while **Storefront Settings → "Discourage Search
Engines" (`noindex`)** is ticked, which is its shipped default — the plan's
W11.4 launch step. While it is on, every page sends `noindex, nofollow`,
`/robots.txt` serves `Disallow: /`, and `/sitemap.xml` returns 404.

To go live, untick it on the production site:

```bash
ssh root@72.61.87.227 "docker exec -u frappe narjes-backend-1 bench --site narjes.store set-value 'Narjes Storefront Settings' noindex 0"
```

Nothing is indexable until that is done.

## Structured data

One `<script type="application/ld+json">` per page holding a single `@graph`,
rather than several script tags. A single graph lets nodes reference each
other by `@id` — every Offer's `seller`, every page's `about`, the WebSite's
`publisher` all resolve to one Organization node instead of restating it.

| Route | Nodes emitted |
|---|---|
| `/{lang}` | Organization+Store, WebSite (SearchAction), ItemList (featured) |
| `/{lang}/p/<slug>` | …+ Product (+Offer), BreadcrumbList |
| `/{lang}/shop`, `/{lang}/c/<slug>` | …+ CollectionPage, ItemList, BreadcrumbList |
| `/{lang}/about` | …+ AboutPage, BreadcrumbList |
| `/{lang}/contact` | …+ ContactPage, BreadcrumbList |
| `/{lang}/custom-design` | …+ WebPage, BreadcrumbList |
| cart, checkout, favourites, order | none — these are `noindex` |

Two rules hold throughout `seo.py`:

1. **Never assert what the shop has not entered.** `_prune` drops empty values
   recursively, so a half-filled Settings doc cannot emit `"telephone": ""`.
   An empty string is a claim Google errors on; absence it ignores. `0` and
   `False` are kept — those are real values.
2. **Mirror the page.** The breadcrumb graph matches the rendered breadcrumb,
   the ItemList matches the grid on screen, and **no rating is emitted
   anywhere**, because the shop has no reviews. Marking up invisible or
   invented content is what earns a manual action.

The unpriced-item case is the one worth remembering: an item with no Item
Price omits `offers` **entirely**. The previous inline markup emitted
`"offers": null`, which invalidates the whole Product node.

## Two traps found on the live site

Both were invisible in local dev and only showed up when the deployed pages
were fetched as a guest:

* **`shop_name_ar` / `shop_name_en` exist because `meta_title` is not a
  brand.** The entity name originally came from `meta_title`, which the shop
  had (reasonably) filled with a slogan — so the Organization, the WebSite and
  every product's `brand.name` read as a full marketing sentence. These are
  now dedicated fields under Brand & Hero, and `meta_title` is used only for
  the `<title>` tag it was meant for.
* **`core.public_file` rejects `/private/` uploads.** A file attached as
  private 403s for everyone not signed in. The shop's share image was uploaded
  that way, so `og:image` and the Organization `image` both pointed at a
  broken URL — and looked perfect to the logged-in person who set it.

## Not emitted, and why

* **`aggregateRating` / `review`** — no review data exists. These are the
  single biggest rich-result upgrade available and the reason to build a
  review capture flow; fabricating them is a manual-action risk.
* **`hasMerchantReturnPolicy` / `shippingDetails`** — Merchant listing
  experiences want these, but the shop has no written returns policy to
  encode. Add the policy as real content first, then mark it up.
* **`priceValidUntil`** — Settings has no price expiry to reference. Omitted
  rather than invented; its absence is a warning, not an error.
* **`FAQPage`** — requires visible Q&A on the page. Worth adding to
  `/about` as real content, then marking up.

## robots.txt

Generated, not stored in Website Settings, so the rules live in git next to
the routes they describe and stay in sync with the `noindex` switch.

Deliberately **not** blocked: `/files` (product photos — this catalogue wants
Google Images) and `/assets` (the CSS/JS Googlebot needs to render the page).
Blocking either is the classic storefront own-goal.

Blocked: `/app`, `/api`, `/private`, `/login`, the four transient storefront
surfaces in both languages, and `/{lang}/shop?q=` — search results are
infinite, thin, and near-duplicates of `/shop`.

## sitemap.xml

Replaces Frappe's, which is built from `get_pages()` and doctypes with web
views — the storefront is neither, since its routes come from
`website_route_rules`, so the catalogue would never appear in it. Resolution
works because `TemplatePage.set_template_path` walks
`reversed(frappe.get_installed_apps())` and `narjes_custom` installs after
`frappe`.

Every path appears once per language with `xhtml:link` alternates for the
others — the sitemap-side half of the hreflang pairing declared in the page
head. Declaring it in both places is what makes Google trust it. URLs are
percent-encoded and XML-escaped in Python because **Frappe's Jinja
environment is built without `autoescape`**.

## Slugs

`core.sanitize_slug` collapses URL-unsafe runs into single dashes, so an item
code like `MDF 50*80` yields `/p/mdf-50-80` instead of `/p/mdf-50*80`.
Non-ASCII is preserved — an Arabic slug is a legitimate URL.

**This changes existing generated URLs** for item codes containing unsafe
characters. Safe to do pre-launch (nothing is indexed yet); after launch it
would need redirects. Items with an explicit `custom_web_route` are
unaffected unless that route itself contains unsafe characters.

## Verifying

```bash
python -m pytest apps/narjes_custom/narjes_custom/tests/test_seo.py -v
```

For the rendered output, fetch a product page and paste its JSON-LD into the
[Rich Results Test](https://search.google.com/test/rich-results). After
launch, submit `https://narjes.store/sitemap.xml` in Google Search Console.
