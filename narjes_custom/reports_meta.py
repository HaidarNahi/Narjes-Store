"""What each number on a report means, in words a shop owner would use.

These sit beside the code that calculates them rather than in a list of UI
strings, because the failure mode to design against is the explanation quietly
becoming a lie: someone changes how net profit is worked out and the sentence
describing it, three files away, still says the old thing. Here, the sum and
the sentence are neighbours.

Two parts each, and they answer different questions:

    what  — what the number means, in a sentence
    how   — where it came from, so a reader can decide whether to trust it

Both are wrapped in _() at the point of use, not here, so they land in the
translation files as ordinary strings.
"""

# Real typographic signs, not their ASCII lookalikes. These strings are read by
# a person and never parsed, so a true minus sets better than a hyphen. Written
# as escapes and named, because an invisible-to-the-eye difference between two
# characters is a trap for whoever edits the copy next.
MINUS = "\u2212"
TIMES = "\u00d7"
DIVIDE = "\u00f7"

# The same idea must read identically wherever it appears. "Net profit" means
# one thing whether you meet it on the Revenue report or the salary screen, so
# it is defined once and reused.
COST_OF_GOODS = {
	"what": "What the things you sold actually cost you: materials, printing, painting, packaging and flowers.",
	"how": "materials of what was sold",
}
RUNNING_COSTS = {
	"what": "The cost of keeping the shop open: ads, rent, salaries, electricity, transport, subscriptions.",
	"how": "all other spending",
}
NET_PROFIT = {
	"what": "What the business actually kept. This is the number the salary screen divides between you.",
	"how": f"gross profit {MINUS} running costs",
}

EXPLAINERS = {
	# ---------------------------------------------------------- Money In
	"Total in": {
		"what": "Every dinar earned in this period, whether or not the customer has paid yet.",
		"how": "sum of all income entries",
	},
	"Cash received": {
		"what": (
			"The part that actually reached your hand or the bank. "
			"Selling cash on delivery, this is usually the same as Total in."
		),
		"how": "money paid into cash + bank",
	},
	"Still owed": {
		"what": (
			"Earned but not yet collected. It should stay near zero — if it climbs, "
			"someone has taken goods without paying."
		),
		"how": f"total in {MINUS} cash received",
	},
	"Average sale": {
		"what": "The size of a typical order this period.",
		"how": f"total in {DIVIDE} number of sales",
	},
	# --------------------------------------------------------- Money Out
	"Total out": {
		"what": "Every dinar that left the company: what your goods cost you, plus what the shop costs to run.",
		"how": "cost of goods + running costs",
	},
	"Cost of goods": COST_OF_GOODS,
	"Running the shop": RUNNING_COSTS,
	"Entries": {
		"what": "How many separate money movements make up this list.",
		"how": "count of rows",
	},
	"Stock corrections (not spending)": {
		"what": (
			"Stock entered into the system with no purchase behind it. No money moved, "
			"so it is shown but never counted as spending."
		),
		"how": "shown, not counted",
	},
	# ----------------------------------------------------------- Revenue
	"Money in": {
		"what": (
			"Every dinar that came into the company in this period — sales and services "
			"together, read straight from the ledger."
		),
		"how": "sales + service",
	},
	"Gross profit": {
		"what": "What is left after paying for the goods, but before paying for rent, ads and everything else.",
		"how": f"money in {MINUS} cost of goods",
	},
	"Running costs": RUNNING_COSTS,
	"Net profit": NET_PROFIT,
	"vs previous period": {
		"what": "Whether net profit went up or down against the period just before this one, of the same length.",
		"how": f"change {DIVIDE} previous net profit",
	},
	# ------------------------------------------- The Revenue & Salaries
	"Net profit to divide": {
		"what": (
			"This month's net profit from the Revenue report. Walaa's commission is "
			"already taken out before anything is divided."
		),
		"how": "net profit for the month",
	},
	"Paid to people": {
		"what": "The partners' shares plus the piece commission — money leaving the business to people.",
		"how": "partner shares + commission",
	},
	"Kept in the business": {
		"what": "The emergencies box plus growth — money that stays with the shop.",
		"how": "emergencies + growth",
	},
	"Emergencies box": {
		"what": "Set aside for hard days — a printer breaking, and days like it.",
		"how": "{0}% of net profit",
	},
	"Growth & development": {
		"what": "Kept back for improving the business.",
		"how": "{0}% of net profit",
	},
	"Partner share": {
		"what": "This partner's agreed share of the same net profit.",
		"how": "{0}% of net profit",
	},
	"Commission": {
		"what": (
			"Paid for every MDF, frame or stand sold. It is a wage, so it is recorded as "
			"an expense and comes out before the shares are worked out."
		),
		"how": "{0} " + TIMES + " pieces sold",
	},
	# ------------------------------------------------------------- Debts
	"Owed to us": {
		"what": "What customers and others still owe you. Only debts not yet settled are counted.",
		"how": "unpaid part of open debts",
	},
	"We owe": {
		"what": "What you still owe suppliers and others.",
		"how": "unpaid part of what you owe",
	},
	"Net position": {
		"what": "Positive means more money is coming to you than going out.",
		"how": f"owed to us {MINUS} we owe",
	},
	"Overdue": {
		"what": "Debts whose settle-by date has passed and that are still not fully paid.",
		"how": "past due date, still unpaid",
	},
}


def card(label, value, **kw):
	"""A report summary card, carrying its own explanation.

	Anything in EXPLAINERS is attached automatically, so adding a card that is
	already described elsewhere needs nothing extra, and a card with no entry
	simply renders without a button.
	"""
	from frappe import _

	entry = EXPLAINERS.get(label)
	out = {"label": _(label), "value": value}
	out.update(kw)
	if entry:
		out["explanation"] = _(entry["what"])
		out["formula"] = _(entry["how"])
	return out


def explain(label, *format_args):
	"""The explainer for a label, for surfaces that build their own cards.

	`format_args` fill the placeholders in `how` — the share percentages and
	the commission rate are configurable, so the formula shown has to be the
	one actually in force rather than the one that was true when this was
	written.
	"""
	from frappe import _

	entry = EXPLAINERS.get(label)
	if not entry:
		return None
	how = _(entry["how"])
	if format_args:
		how = how.format(*format_args)
	return {"title": _(label), "what": _(entry["what"]), "how": how}
