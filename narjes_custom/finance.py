"""One definition of the shop's money, shared by every report that reports it.

Money Out, Money In, Revenue and the salary dashboard all answer versions of
the same question, and the fastest way to lose trust in all four is to let
them disagree by a few thousand dinars. So the arithmetic lives here, once,
and each report is a presentation of it.

Everything reads `GL Entry` — the ledger — rather than Sales Orders or Narjes
Expenses. That is the difference between "most of the money" and *every*
dinar: the sale automation books painting, packaging and flower cost straight
to Journal Entries that no document-level report would ever see.

Two rules the ledger alone will not give you, learned from this company's
actual books:

1.  **Classify by account, never by root type alone.** `Packaging Expenses`
    spent months filed under Income while being debited as a cost. Summing
    root types would have reported the shop's profit as 139,300 when it was
    29,300. setup/accounts.py now keeps the classification honest, but the
    reports still name what they include rather than trusting the tree.

2.  **Opening balances are not trading.** An opening Stock Adjustment credit
    of 110,000 reads as negative spending and inflates profit by exactly that
    much. Opening entries are excluded everywhere.
"""

import frappe
from frappe.utils import flt, get_first_day, get_last_day, getdate

# Accounts that hold a cost of *making the thing sold* rather than a cost of
# running the shop. Splitting them is what makes a gross margin meaningful.
DIRECT_COST_ACCOUNT_TYPES = ("Cost of Goods Sold",)
DIRECT_COST_NAMES = ("Painting Costs", "Packaging Expenses")

# Stock Adjustment is not trading, and it is not symmetrical.
#
# A *debit* is a genuine loss — stock written off, damaged, or found short —
# and belongs in the cost of running the shop.
#
# A *credit* is stock appearing without a purchase behind it. On these books
# that is a Material Receipt of 110,000: ten stands the shop already owned,
# entered into the system for the first time. No money moved. Read as an
# expense it comes out negative, and 110,000 of pure phantom profit lands in
# the pot that pays everybody's salary.
#
# So credits here are carried as a correction — shown in Money Out, clearly
# labelled, never counted as trading.
STOCK_CORRECTION_ACCOUNT_TYPE = "Stock Adjustment"

# Where money physically sits. Used to answer "what did we actually collect",
# as opposed to "what did we invoice".
LIQUID_ACCOUNT_TYPES = ("Cash", "Bank")


def month_bounds(month):
	"""('2026-08-01', '2026-08-31') for any date inside August 2026."""
	d = getdate(month)
	return get_first_day(d), get_last_day(d)


# --------------------------------------------------------------- ledger rows


def _gl(from_date, to_date, company, root_types, extra="", params=None):
	"""Ledger entries in a period, already joined to their account.

	`is_opening = 'No'` is not decoration: an opening entry is the balance the
	company started with, not money that moved during the period, and counting
	one as trading is how a 110,000 opening credit becomes 110,000 of phantom
	profit.
	"""
	values = {
		"from_date": from_date,
		"to_date": to_date,
		"company": company,
		"root_types": list(root_types),
	}
	values.update(params or {})
	return frappe.db.sql(
		f"""
		SELECT
			gl.posting_date, gl.account, gl.debit, gl.credit,
			gl.voucher_type, gl.voucher_no, gl.against_voucher,
			gl.remarks, gl.party, gl.party_type,
			acc.account_name, acc.root_type, acc.account_type
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON acc.name = gl.account
		WHERE gl.is_cancelled = 0
		  AND gl.is_opening = 'No'
		  AND gl.company = %(company)s
		  AND gl.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  AND acc.root_type IN %(root_types)s
		  {extra}
		ORDER BY gl.posting_date DESC, gl.creation DESC
		""",
		values,
		as_dict=True,
	)


def money_out_rows(from_date, to_date, company):
	"""Every dinar that left, one row per posting, newest first.

	Each row carries a `bucket`, and the bucket is what the profit chain adds
	up — never the raw account tree. See STOCK_CORRECTION_ACCOUNT_TYPE for the
	one case where an expense-account posting is deliberately not a cost.
	"""
	rows = _gl(from_date, to_date, company, ("Expense",))
	out = []
	for r in rows:
		amount = flt(r.debit) - flt(r.credit)
		if not amount:
			continue
		r["amount"] = amount
		r["bucket"] = _bucket(r, amount)
		out.append(r)
	return out


def _bucket(row, amount):
	if row.account_type == STOCK_CORRECTION_ACCOUNT_TYPE:
		# A debit is a real write-off; a credit is stock catching up with
		# reality and must not read as money coming back.
		return "Operating" if amount > 0 else "Correction"
	return "Direct" if _is_direct_cost(row) else "Operating"


def money_in_rows(from_date, to_date, company):
	"""Every dinar that arrived, one row per posting, newest first."""
	rows = _gl(from_date, to_date, company, ("Income",))
	out = []
	for r in rows:
		amount = flt(r.credit) - flt(r.debit)
		if not amount:
			continue
		r["amount"] = amount
		out.append(r)
	return out


def _is_direct_cost(row):
	return (
		row.account_type in DIRECT_COST_ACCOUNT_TYPES
		or row.account_name in DIRECT_COST_NAMES
	)


# ------------------------------------------------------------------ totals


def cash_collected(from_date, to_date, company):
	"""What actually landed in cash or the bank — not what was invoiced.

	Debits only, deliberately. Netting the credits off would answer a
	different question ("did the till grow this month"), and on these books it
	answers it as -297,050 — because the shop paid suppliers more than it took
	in — which is not a sentence anyone wants under a heading called
	"collected".
	"""
	return (
		frappe.db.sql(
			"""
		SELECT COALESCE(SUM(gl.debit), 0)
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON acc.name = gl.account
		WHERE gl.is_cancelled = 0 AND gl.is_opening = 'No'
		  AND gl.company = %(company)s
		  AND gl.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  AND acc.account_type IN %(types)s
		""",
			{
				"company": company,
				"from_date": from_date,
				"to_date": to_date,
				"types": list(LIQUID_ACCOUNT_TYPES),
			},
		)[0][0]
		or 0
	)


def outstanding_receivable(company, as_of=None):
	"""What customers still owe, per the ledger's own receivable accounts."""
	return (
		frappe.db.sql(
			"""
		SELECT COALESCE(SUM(gl.debit) - SUM(gl.credit), 0)
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON acc.name = gl.account
		WHERE gl.is_cancelled = 0
		  AND gl.company = %(company)s
		  AND acc.account_type = 'Receivable'
		  AND (%(as_of)s IS NULL OR gl.posting_date <= %(as_of)s)
		""",
			{"company": company, "as_of": as_of},
		)[0][0]
		or 0
	)


def profit_summary(from_date, to_date, company):
	"""The chain from what customers paid down to what the shop keeps.

	This is the number the salary dashboard divides, so every step is named
	explicitly and the steps are guaranteed to reconcile: gross is income less
	direct cost, net is gross less operating cost, and `money_out` is the sum
	of both cost buckets.
	"""
	income = money_in_rows(from_date, to_date, company)
	expense = money_out_rows(from_date, to_date, company)

	money_in = sum(r["amount"] for r in income)
	direct = sum(r["amount"] for r in expense if r["bucket"] == "Direct")
	operating = sum(r["amount"] for r in expense if r["bucket"] == "Operating")
	correction = sum(r["amount"] for r in expense if r["bucket"] == "Correction")

	gross = money_in - direct
	net = gross - operating

	return {
		"from_date": from_date,
		"to_date": to_date,
		"company": company,
		"money_in": money_in,
		"direct_cost": direct,
		"operating_cost": operating,
		"money_out": direct + operating,
		# Shown, never counted. Reported separately so a reader can see it
		# rather than wonder why the report and the P&L differ.
		"stock_correction": correction,
		"gross_profit": gross,
		"net_profit": net,
		"gross_margin": (gross / money_in * 100) if money_in else 0.0,
		"net_margin": (net / money_in * 100) if money_in else 0.0,
		"by_income_account": _group(income),
		"by_expense_account": _group(r for r in expense if r["bucket"] != "Correction"),
	}


def _group(rows):
	"""Account name -> total, largest first."""
	totals = {}
	for r in rows:
		totals[r["account_name"]] = totals.get(r["account_name"], 0) + r["amount"]
	return dict(sorted(totals.items(), key=lambda kv: -abs(kv[1])))


def default_company():
	return (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_default("company")
		or frappe.db.get_value("Company", {}, "name")
	)


def profit_totals(from_date, to_date, company):
	"""profit_summary()'s numbers without its rows.

	The salary history draws six months at once. profit_summary() pulls every
	ledger row for each of them purely to add them up and throw them away —
	fine for one month on this bench, not fine for six months of a busy year.
	This asks the database to do the adding.

	The bucketing must match _bucket() exactly or the history will disagree
	with the month it is a history of, so both read the same constants.
	"""
	direct_names = list(DIRECT_COST_NAMES)
	direct_types = list(DIRECT_COST_ACCOUNT_TYPES)

	row = frappe.db.sql(
		"""
		SELECT
			COALESCE(SUM(CASE WHEN acc.root_type = 'Income'
				THEN gl.credit - gl.debit END), 0) AS money_in,

			COALESCE(SUM(CASE WHEN acc.root_type = 'Expense'
				AND acc.account_type != %(correction_type)s
				AND (acc.account_type IN %(direct_types)s OR acc.account_name IN %(direct_names)s)
				THEN gl.debit - gl.credit END), 0) AS direct_cost,

			COALESCE(SUM(CASE WHEN acc.root_type = 'Expense'
				AND NOT (acc.account_type IN %(direct_types)s OR acc.account_name IN %(direct_names)s)
				AND NOT (acc.account_type = %(correction_type)s AND gl.debit - gl.credit <= 0)
				THEN gl.debit - gl.credit END), 0) AS operating_cost,

			COALESCE(SUM(CASE WHEN acc.account_type = %(correction_type)s
				AND gl.debit - gl.credit <= 0
				THEN gl.debit - gl.credit END), 0) AS stock_correction
		FROM `tabGL Entry` gl
		INNER JOIN `tabAccount` acc ON acc.name = gl.account
		WHERE gl.is_cancelled = 0
		  AND gl.is_opening = 'No'
		  AND gl.company = %(company)s
		  AND gl.posting_date BETWEEN %(from_date)s AND %(to_date)s
		  AND acc.root_type IN ('Income', 'Expense')
		""",
		{
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"direct_types": direct_types,
			"direct_names": direct_names,
			"correction_type": STOCK_CORRECTION_ACCOUNT_TYPE,
		},
		as_dict=True,
	)[0]

	money_in = flt(row.money_in)
	direct = flt(row.direct_cost)
	operating = flt(row.operating_cost)
	gross = money_in - direct

	return {
		"from_date": from_date,
		"to_date": to_date,
		"company": company,
		"money_in": money_in,
		"direct_cost": direct,
		"operating_cost": operating,
		"money_out": direct + operating,
		"stock_correction": flt(row.stock_correction),
		"gross_profit": gross,
		"net_profit": gross - operating,
		"gross_margin": (gross / money_in * 100) if money_in else 0.0,
		"net_margin": ((gross - operating) / money_in * 100) if money_in else 0.0,
	}
