"""Seed the salary configuration, and keep the commission flags in sync.

Runs on every migrate. Both halves are deliberately additive: they fill in
what is missing and never overwrite a decision someone has already made in
the UI, because this is configuration that decides what people get paid.
"""

import frappe

from narjes_custom import salaries

# The arrangement as agreed. Seeded only into an empty table — once the shop
# has edited the shares, a migrate must never quietly reset them.
DEFAULT_PARTNERS = [
	{"person_name": "Ibrahim", "user": "alwutwut8@gmail.com", "share_percent": 30},
	{"person_name": "Haneen", "user": "ha.alwutwut@gmail.com", "share_percent": 30},
]
DEFAULT_COMMISSION_USER = "walaa.hadi12@gmail.com"


def run():
	seed_shares()
	salaries.sync_commission_flags()
	frappe.db.commit()


def seed_shares():
	doc = frappe.get_single("Narjes Settings")
	dirty = False

	for field, value in (
		("emergency_share_percent", 15),
		("growth_share_percent", 25),
		("commission_per_piece", 1000),
		("commission_person_name", "Walaa"),
	):
		if not doc.get(field):
			doc.set(field, value)
			dirty = True

	if not doc.get("profit_shares"):
		for partner in DEFAULT_PARTNERS:
			doc.append(
				"profit_shares",
				{
					"person_name": partner["person_name"],
					# Only link the login if it actually exists. These three
					# accounts are not on every bench, and a Link to a missing
					# User makes the settings document unsaveable — which
					# would take the whole Settings page down, not just this
					# section.
					"user": _user_or_none(partner["user"]),
					"share_percent": partner["share_percent"],
				},
			)
		dirty = True

	if not doc.get("commission_user"):
		user = _user_or_none(DEFAULT_COMMISSION_USER)
		if user:
			doc.commission_user = user
			dirty = True

	if dirty:
		doc.flags.ignore_permissions = True
		doc.save()


def _user_or_none(email):
	return email if frappe.db.exists("User", email) else None
