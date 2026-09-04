"""How the month's profit becomes four people's pay.

The rule the shop agreed:

    Walaa earns 1,000 IQD for every MDF, frame or stand sold. That is a wage,
    so it is an expense and comes out first. What is left over is the net
    profit, and it divides:

        15%  emergencies      — the printer breaking, and days like it
        25%  growth           — putting the business somewhere better
        60%  the partners     — Ibrahim 30%, Haneen 30%

Two decisions inside that are worth stating plainly, because both are places
where a reasonable-looking implementation pays someone the wrong amount.

**Walaa is paid before the split, not out of it.** Her commission is a cost of
selling, exactly like packaging. It appears in Money Out, it reduces net
profit, and only the remainder is divided. Paying her out of the 60% instead
would make the partners' share depend on how many frames she sold, which is
not the deal.

**Nobody is hardcoded.** The three accounts named in the original brief do not
exist on this bench, and an implementation that assumed they did would fail on
a fresh site and cannot be changed without a developer. Shares and people live
in Narjes Settings; this module reads them.
"""

import frappe
from frappe import _
from frappe.utils import add_months, flt, get_first_day, get_last_day, getdate

from narjes_custom import finance

# The word rule that seeds Item.custom_pays_commission.
#
# Matched as whole words against both item_code and item_name, case
# insensitively. Whole words matter: a plain LIKE '%stand%' also matches
# "Standard", "Standee" and "Freestanding", and this is a rule that pays real
# money every month.
COMMISSION_KEYWORDS = ("mdf", "frame", "stand")

# UOMs that mean "a piece". Commission is per piece, so an item sold by length
# must never be multiplied by 1,000 — a 250 cm cut of a row item would
# otherwise pay 250,000 IQD for a single line.
PIECE_UOMS = ("Nos", "Unit", "Piece", "Pcs", "Each", "Box", "Set")


# --------------------------------------------------------------- item rule


def _keyword_regex():
	# MariaDB REGEXP: [[:<:]]word[[:>:]] are its word boundaries.
	return "|".join(f"[[:<:]]{k}[[:>:]]" for k in COMMISSION_KEYWORDS)


def matching_items():
	"""Items the name rule considers commission-earning."""
	return frappe.db.sql(
		"""
		SELECT name, item_name, stock_uom
		FROM `tabItem`
		WHERE LOWER(name) REGEXP %(rx)s OR LOWER(IFNULL(item_name, '')) REGEXP %(rx)s
		""",
		{"rx": _keyword_regex()},
		as_dict=True,
	)


def sync_commission_flags():
	"""Tick `custom_pays_commission` on items the name rule finds.

	Only ever ticks, never unticks: once someone has judged an item by hand,
	a migrate must not overrule them. Returns the items it changed.
	"""
	if not frappe.db.has_column("Item", "custom_pays_commission"):
		return []

	changed = []
	for item in matching_items():
		if not frappe.db.get_value("Item", item.name, "custom_pays_commission"):
			frappe.db.set_value("Item", item.name, "custom_pays_commission", 1, update_modified=False)
			changed.append(item.name)
	return changed


def commission_items():
	"""The items that actually pay commission — the checkbox, not the rule."""
	if not frappe.db.has_column("Item", "custom_pays_commission"):
		return []
	return frappe.get_all(
		"Item",
		filters={"custom_pays_commission": 1},
		fields=["name", "item_name", "stock_uom"],
	)


def _keyword_for(item_code, item_name):
	"""Which of MDF / frame / stand this item is, for the breakdown table.

	Deliberately free of frappe imports so it can be unit-tested without a
	site, the same way business_logic.py is — this is the rule that decides
	what a person is paid, and it should be the easiest thing here to check.
	Translation is the display layer's job; this returns a stable key.
	"""
	haystack = f"{item_code or ''} {item_name or ''}".lower()
	words = set(_words(haystack))
	for word in COMMISSION_KEYWORDS:
		if word in words:
			return word.upper() if word == "mdf" else word.capitalize()
	return "Other"


def _words(text):
	buf, out = [], []
	for ch in text:
		if ch.isalnum():
			buf.append(ch)
		elif buf:
			out.append("".join(buf))
			buf = []
	if buf:
		out.append("".join(buf))
	return out


# ------------------------------------------------------------- commission


def commission_for_period(from_date, to_date, company=None):
	"""What Walaa earned on pieces sold in a period.

	Counts submitted Sales Orders by transaction date: that is when the shop
	agreed the sale, which is the moment the work was done. Cancelled orders
	are excluded by docstatus, so a cancelled order takes its commission with
	it.
	"""
	settings = get_settings()
	rate = flt(settings["commission_per_piece"])
	items = {i.name: i for i in commission_items()}
	if not items or not rate:
		return {
			"rate": rate,
			"person": settings["commission_person"],
			"total": 0.0,
			"pieces": 0,
			"lines": [],
			"by_kind": [],
			"skipped": [],
			"stranded": [],
		}

	rows = frappe.db.sql(
		"""
		SELECT soi.item_code, SUM(soi.qty) AS qty, COUNT(*) AS line_count
		FROM `tabSales Order Item` soi
		INNER JOIN `tabSales Order` so ON so.name = soi.parent
		WHERE so.docstatus = 1
		  AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		  AND (%(company)s IS NULL OR so.company = %(company)s)
		  AND soi.item_code IN %(items)s
		GROUP BY soi.item_code
		""",
		{
			"from_date": from_date,
			"to_date": to_date,
			"company": company,
			"items": list(items),
		},
		as_dict=True,
	)

	lines, skipped, pieces = [], [], 0
	for row in rows:
		item = items[row.item_code]
		if item.stock_uom not in PIECE_UOMS:
			# Shown, not silently dropped: an item that should be earning
			# commission and isn't is a pay dispute waiting to happen.
			skipped.append(
				{
					"item_code": row.item_code,
					"qty": flt(row.qty),
					"uom": item.stock_uom,
					"reason": _("sold by {0}, not by the piece").format(item.stock_uom),
				}
			)
			continue
		qty = int(flt(row.qty))
		pieces += qty
		lines.append(
			{
				"item_code": row.item_code,
				"item_name": item.item_name,
				"kind": _keyword_for(row.item_code, item.item_name),
				"qty": qty,
				"amount": qty * rate,
			}
		)

	lines.sort(key=lambda r: -r["amount"])
	return {
		"rate": rate,
		"person": settings["commission_person"],
		"stranded": _stranded_orders(from_date, to_date, company, list(items)),
		"total": pieces * rate,
		"pieces": pieces,
		"lines": lines,
		"by_kind": _by_kind(lines),
		"skipped": skipped,
	}


def _stranded_orders(from_date, to_date, company, item_codes):
	"""Commission-earning orders whose income landed in a different month.

	Commission is counted by the Sales Order's own date, because that is when
	the shop agreed the sale and when the work was done — which is how the
	rule was described. Revenue is counted by when the invoice reached the
	ledger. `automate_so_flow()` invoices with ERPNext's default posting date,
	which is *today*, not the order's date.

	For an order raised and submitted the same day those are identical and
	none of this matters. For a backdated order — the AI intake can produce
	one from a WhatsApp message about last week — they diverge, and the month
	pays commission out of income it never received while another month
	receives income it pays no commission on.

	Nothing here is corrected automatically: silently moving somebody's pay
	between months is worse than the mismatch. It is reported instead.
	"""
	if not item_codes:
		return []

	rows = frappe.db.sql(
		"""
		SELECT DISTINCT so.name, so.transaction_date, si.posting_date
		FROM `tabSales Order` so
		INNER JOIN `tabSales Order Item` soi ON soi.parent = so.name
		INNER JOIN `tabSales Invoice Item` sii ON sii.sales_order = so.name
		INNER JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1
		WHERE so.docstatus = 1
		  AND so.transaction_date BETWEEN %(from_date)s AND %(to_date)s
		  AND (%(company)s IS NULL OR so.company = %(company)s)
		  AND soi.item_code IN %(items)s
		  AND si.posting_date NOT BETWEEN %(from_date)s AND %(to_date)s
		""",
		{
			"from_date": from_date,
			"to_date": to_date,
			"company": company,
			"items": item_codes,
		},
		as_dict=True,
	)
	return [
		{
			"sales_order": r.name,
			"ordered": str(r.transaction_date),
			"invoiced": str(r.posting_date),
		}
		for r in rows
	]


def _by_kind(lines):
	totals = {}
	for line in lines:
		bucket = totals.setdefault(line["kind"], {"kind": line["kind"], "qty": 0, "amount": 0})
		bucket["qty"] += line["qty"]
		bucket["amount"] += line["amount"]
	return sorted(totals.values(), key=lambda r: -r["amount"])


# ------------------------------------------------------------ the split


def get_settings():
	"""Shares and people, from Narjes Settings, with the agreed defaults.

	Defaults are used when the setting is blank so a fresh site behaves
	correctly, but everything here is meant to be edited in the UI rather than
	in this file.
	"""
	doc = frappe.get_cached_doc("Narjes Settings")
	shares = [
		{
			"key": "emergency",
			"label": _("Emergencies box"),
			"percent": _pct(doc, "emergency_share_percent", 15),
			"kind": "fund",
		},
		{
			"key": "growth",
			"label": _("Growth & development"),
			"percent": _pct(doc, "growth_share_percent", 25),
			"kind": "fund",
		},
	]
	for row in doc.get("profit_shares") or []:
		shares.append(
			{
				"key": row.user or row.person_name,
				"label": row.person_name or row.user,
				"user": row.user,
				"percent": flt(row.share_percent),
				"kind": "person",
			}
		)

	return {
		"commission_per_piece": _num(doc, "commission_per_piece", 1000),
		"commission_person": doc.get("commission_person_name") or _("Walaa"),
		"commission_user": doc.get("commission_user"),
		"shares": shares,
	}


def _pct(doc, field, default):
	value = doc.get(field)
	return flt(value) if value not in (None, "", 0) else float(default)


def _num(doc, field, default):
	value = doc.get(field)
	return flt(value) if value not in (None, "", 0) else float(default)


def distribution(from_date, to_date, company=None, detailed=True):
	"""The whole month: profit, commission, and who gets what.

	`detailed=False` skips the per-account breakdown and asks the database to
	total the ledger instead of pulling every row back to add up here. The
	history draws six months at once, and only needs the totals — see
	finance.profit_totals(), which is verified to agree with the full path.
	"""
	company = company or finance.default_company()
	summary = (
		finance.profit_summary(from_date, to_date, company)
		if detailed
		else finance.profit_totals(from_date, to_date, company)
	)
	commission = commission_for_period(from_date, to_date, company)
	settings = get_settings()

	net = summary["net_profit"]

	# Whether the commission has actually reached the books yet. If it has
	# not, `net` still contains money that is already owed to somebody, and
	# every share below is overstated — so this travels with the numbers
	# rather than being left for the reader to know.
	posted = commission_expense_for(from_date, company)
	commission["posted"] = bool(posted)
	commission["expense"] = posted.name if posted else None
	commission["net_if_posted"] = net - commission["total"] if not posted else net

	allocations = []
	for share in settings["shares"]:
		allocations.append(
			{
				**share,
				"amount": net * flt(share["percent"]) / 100.0,
			}
		)

	allocated_percent = sum(flt(s["percent"]) for s in settings["shares"])

	return {
		"from_date": from_date,
		"to_date": to_date,
		"company": company,
		"net_profit": net,
		"money_in": summary["money_in"],
		"money_out": summary["money_out"],
		"commission": commission,
		"allocations": allocations,
		"allocated_percent": allocated_percent,
		# Surfaced rather than hidden: shares that do not add to 100 mean
		# money is either unassigned or promised twice, and the dashboard
		# says so out loud.
		"unallocated": net * (100.0 - allocated_percent) / 100.0,
		"commission_pending": not commission["posted"] and bool(commission["total"]),
		"paid_to_people": sum(a["amount"] for a in allocations if a["kind"] == "person")
		+ commission["total"],
		"kept_in_business": sum(a["amount"] for a in allocations if a["kind"] == "fund"),
	}


def history(months=6, company=None, end=None):
	"""The last N complete months, newest first, each with its change.

	The comparison is against the month before it, so a reader can see whether
	their pay went up or down without doing arithmetic.
	"""
	company = company or finance.default_company()
	anchor = get_first_day(getdate(end)) if end else get_first_day(getdate())

	periods = []
	# One extra month at the end, purely to compute the oldest row's change.
	for offset in range(months + 1):
		start = add_months(anchor, -offset)
		periods.append(distribution(start, get_last_day(start), company, detailed=False))

	rows = []
	for index, period in enumerate(periods[:months]):
		previous = periods[index + 1] if index + 1 < len(periods) else None
		rows.append(
			{
				**period,
				"label": getdate(period["from_date"]).strftime("%B %Y"),
				"previous_net": previous["net_profit"] if previous else None,
				"change": (period["net_profit"] - previous["net_profit"]) if previous else None,
				"change_percent": _change_pct(period, previous),
			}
		)
	return rows


def _change_pct(period, previous):
	if not previous or not previous["net_profit"]:
		return None
	return (period["net_profit"] - previous["net_profit"]) / abs(previous["net_profit"]) * 100.0


# --------------------------------------------------- paying the commission


def commission_expense_for(month, company=None):
	"""The posted commission expense for a month, if there is one."""
	company = company or finance.default_company()
	name = frappe.db.get_value(
		"Narjes Expense",
		{
			"custom_commission_month": get_first_day(getdate(month)),
			"company": company,
			"docstatus": ["<", 2],
		},
		"name",
	)
	return frappe.get_doc("Narjes Expense", name) if name else None


@frappe.whitelist()
def post_commission_expense(month, company=None):
	"""Record the month's piece commission as a real expense, once.

	Until this is posted the commission is only a calculation: it has not
	reduced profit, so the partners' 30% each is being worked out on money
	that is already owed to somebody else. The dashboard says so, and this is
	the button that fixes it.

	Idempotent by lookup, not by hope — `custom_commission_month` makes a
	second posting for the same month impossible even if two people press the
	button at the same moment.
	"""
	frappe.has_permission("Narjes Expense", ptype="create", throw=True)

	company = company or finance.default_company()
	start = get_first_day(getdate(month))
	end = get_last_day(start)

	existing = commission_expense_for(start, company)
	if existing:
		return {
			"created": False,
			"expense": existing.name,
			"amount": existing.amount,
			"message": _("{0} was already recorded for {1}.").format(
				existing.name, start.strftime("%B %Y")
			),
		}

	settings = get_settings()
	commission = commission_for_period(start, end, company)
	if not commission["total"]:
		return {
			"created": False,
			"expense": None,
			"amount": 0,
			"message": _("No commission-earning pieces were sold in {0}.").format(
				start.strftime("%B %Y")
			),
		}

	from narjes_custom.setup import accounts

	salary_account = accounts.resolve("Salary", company)
	if not salary_account:
		frappe.throw(
			_("No 'Salary' expense account exists for {0}. Run a migrate to create it.").format(company)
		)

	cash = frappe.db.get_value(
		"Account", {"company": company, "account_type": "Cash", "is_group": 0}, "name"
	)
	if not cash:
		frappe.throw(_("No Cash account exists for {0}.").format(company))

	doc = frappe.get_doc(
		{
			"doctype": "Narjes Expense",
			"company": company,
			# Dated the last day of the month it covers, so it lands inside
			# the period whose profit it is reducing rather than in the next
			# one — which would flatter this month and punish the next.
			"expense_date": end,
			"payee": settings["commission_person"],
			"description": _("Piece commission — {0} pieces in {1}").format(
				commission["pieces"], start.strftime("%B %Y")
			),
			"amount": commission["total"],
			"expense_account": salary_account,
			"paid_from": cash,
			"custom_commission_month": start,
			"notes": "\n".join(
				f"{line['qty']} \u00d7 {line['item_code']} = {line['amount']:,.0f}"
				for line in commission["lines"]
			),
		}
	)
	doc.insert(ignore_permissions=True)
	doc.submit()

	return {
		"created": True,
		"expense": doc.name,
		"amount": doc.amount,
		"message": _("Recorded {0} for {1} — {2} pieces.").format(
			frappe.format_value(doc.amount, {"fieldtype": "Currency"}),
			start.strftime("%B %Y"),
			commission["pieces"],
		),
	}


# ------------------------------------------------------------- dashboard API


@frappe.whitelist()
def get_dashboard(month=None, history_months=6):
	"""Everything the Revenue & Salaries page draws, in one round trip.

	The page is opened to answer "what am I paid this month" — splitting that
	across several requests would put a spinner in front of the only number
	anybody came for.
	"""
	# Pay is sensitive. Reading it means being allowed to read the ledger it
	# is derived from.
	frappe.has_permission("GL Entry", ptype="read", throw=True)

	start = get_first_day(getdate(month)) if month else get_first_day(getdate())
	end = get_last_day(start)

	current = distribution(start, end)
	rows = history(months=int(history_months), end=start)

	return {
		"month": str(start),
		"month_label": start.strftime("%B %Y"),
		"current": current,
		"history": [
			{
				"label": r["label"],
				"month": str(r["from_date"]),
				"net_profit": r["net_profit"],
				"money_in": r["money_in"],
				"change": r["change"],
				"change_percent": r["change_percent"],
				"commission": r["commission"]["total"],
				"commission_pieces": r["commission"]["pieces"],
				"commission_posted": r["commission"].get("posted", False),
				"allocations": [
					{"label": a["label"], "amount": a["amount"], "kind": a["kind"]}
					for a in r["allocations"]
				],
			}
			for r in rows
		],
		"can_post_commission": frappe.has_permission("Narjes Expense", ptype="create"),
	}
