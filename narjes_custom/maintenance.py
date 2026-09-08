"""Things the shop should be told without having to go and look.

Every report this system needs already existed before this module. What did not
exist was anything that ran on its own: `scheduler_events` was empty, no Email
Account was ever configured, and the scheduler process sat up for weeks with
nothing of this app's to do. So the Items Balance report knew which rolls were
nearly out and nobody was told; the intake queue collected items needing review
and nobody saw them; and — found the hard way on 8 September 2026 — the site
had no scheduled backup at all, with the newest dump four days old.

The rule this module follows: **a number nobody reads is not a control.**

Delivery is the desk's own Notification Log, deliberately, not email — this
site has no outgoing mail configured and getting one is a separate decision.
Every check therefore has to be worth a notification badge, which is why there
are five of them and not fifty.

Each check is independent and defensive: one that raises must never stop the
others, because the whole point is that nobody is watching.
"""

import frappe
from frappe.utils import add_days, flt, getdate, now_datetime, today

from narjes_custom import finance

# The server writes this after every successful backup (see
# /opt/narjes-backup/run.sh on the VPS). Its *age* is the signal — a backup
# system that has silently stopped looks exactly like one that is working.
BACKUP_STATUS_FILE = "/opt/narjes-backup/last-success"

# Cron runs 02:30 daily. Past 30h means at least one night was missed.
BACKUP_STALE_HOURS = 30

# Below this, the intake review queue has stopped being a queue and started
# being a backlog someone will eventually clear carelessly.
INTAKE_REVIEW_WARN = 10


def _notify(subject, message, recipients=None, doctype=None, docname=None):
    """Raise a desk notification for the people who can act on it.

    Falls back to Administrator rather than failing silently: a check that
    finds a problem and then cannot find anyone to tell is worse than no check.
    """
    if recipients is None:
        recipients = frappe.get_all(
            "Has Role",
            filters={"role": "System Manager", "parenttype": "User"},
            pluck="parent",
        )
        recipients = [
            u for u in set(recipients)
            if frappe.db.get_value("User", u, "enabled")
            and u not in ("Guest",)
        ] or ["Administrator"]

    for user in set(recipients):
        try:
            note = frappe.new_doc("Notification Log")
            note.subject = subject
            note.email_content = message
            note.for_user = user
            note.type = "Alert"
            if doctype:
                note.document_type = doctype
            if docname:
                note.document_name = docname
            note.insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(frappe.get_traceback(), f"Narjes: could not notify {user}")


def _safe(fn):
    """Run a check; never let one failure take the rest of the run with it."""
    try:
        return fn()
    except Exception:
        frappe.log_error(frappe.get_traceback(), f"Narjes maintenance: {fn.__name__} failed")
        return None


# ------------------------------------------------------------------ backups


def backup_health():
    """Shout if the nightly backup has stopped running.

    This is the most important check in the file. A backup that has silently
    stopped is indistinguishable from one that is working right up until the
    day you need it, which is the day it is too late to notice.
    """
    import os

    if not os.path.exists(BACKUP_STATUS_FILE):
        # Not an error on a machine that isn't the production VPS — local
        # benches and CI have no backup cron and shouldn't nag about it.
        return

    try:
        stamp = open(BACKUP_STATUS_FILE).read().strip()
        last = frappe.utils.get_datetime(stamp.replace("Z", ""))
    except Exception:
        _notify(
            "Backup status unreadable",
            f"{BACKUP_STATUS_FILE} exists but could not be parsed. "
            "Check /opt/narjes-backup/backup.log on the server.",
        )
        return

    age_hours = (now_datetime() - last).total_seconds() / 3600
    if age_hours > BACKUP_STALE_HOURS:
        _notify(
            f"Backup has not run in {int(age_hours)} hours",
            f"The last successful backup was {last}. The nightly job runs at 02:30. "
            "Check /opt/narjes-backup/backup.log on the server — and do not deploy "
            "or migrate anything until it is fixed.",
        )


# ------------------------------------------------------------------- stock


def low_stock_alert():
    """Tell someone which roll items are nearly out.

    The Items Balance report has answered this since Round 2 and is reachable
    only by opening it. Meanwhile NegativeStockError has been the single most
    common reason an order fails to submit — nine orders in three weeks, one of
    them retried eight times. The information existed; the delivery did not.
    """
    from narjes_custom.narjes_custom.report.items_balance.items_balance import get_data

    # get_data() already evaluates the threshold per row and caches the
    # settings read once for the whole report — recomputing it here would
    # re-read Narjes Settings once per item for no gain.
    low = [
        f"{row.get('item_name') or row.get('item_code')}: "
        f"{flt(row.get('balance')):g} {row.get('stock_uom') or ''}".strip()
        for row in (get_data() or [])
        if row.get("is_low_balance")
    ]

    if low:
        _notify(
            f"{len(low)} item(s) running low",
            "These are at or below their reorder threshold:<br><br>"
            + "<br>".join(f"• {line}" for line in low[:20])
            + ("<br><br>…and more — open Items Balance." if len(low) > 20 else ""),
        )


# ------------------------------------------------------------------ intake


def intake_review_queue():
    """Surface AI intakes waiting on a human.

    27 of 207 were sitting in Needs Review when this was written, with nothing
    anywhere showing that. A review queue nobody is shown is where a wrong
    price eventually gets confirmed by someone clearing a backlog at speed.
    """
    pending = frappe.get_all(
        "AI Order Intake",
        filters={"status": "Needs Review"},
        fields=["name", "creation"],
        order_by="creation asc",
    )
    if len(pending) < INTAKE_REVIEW_WARN:
        return

    oldest = getdate(pending[0].creation)
    days = (getdate(today()) - oldest).days
    _notify(
        f"{len(pending)} orders waiting for review",
        f"The AI intake queue has {len(pending)} items in Needs Review; the oldest "
        f"has been waiting {days} day(s). Clear them from the AI Order Intake list.",
    )


# ------------------------------------------------------------------- money


def accrued_expenses_watch():
    """Report the unpaid material-cost liability while it is still small.

    Sale-time costs credit Accrued Expenses rather than Cash, which is correct
    — the canvas was bought on some other day, in bulk, and that purchase was
    never entered. The account only clears when those real purchases are
    booked. Nothing was watching it, and it was at 251,050 IQD across 107
    entries when this was written. That is the same silent drift as the 479,080
    of phantom cash chased down in August, just wearing an honest label.
    """
    company = finance.default_company()
    if not company:
        return

    account = frappe.db.get_value(
        "Account", {"account_name": "Accrued Expenses", "company": company}, "name"
    )
    if not account:
        return

    balance = frappe.db.sql(
        """
        SELECT COALESCE(SUM(credit - debit), 0)
        FROM `tabGL Entry`
        WHERE account = %s AND is_cancelled = 0
        """,
        account,
    )[0][0]

    _notify(
        "Weekly money check",
        f"Accrued Expenses (material costs incurred but never matched to a real "
        f"purchase) stands at <b>{flt(balance):,.0f} IQD</b>.<br><br>"
        "This clears when the bulk purchases behind it are entered as Purchase "
        "Orders. If it only ever grows, the cost of goods is real but the "
        "purchases behind it are missing from the books.",
    )


# ------------------------------------------------------------------- digest


def daily_digest():
    """Yesterday, in the numbers this shop actually runs on.

    Orders *taken* and orders *submitted* are counted separately, and that
    distinction is the whole point. This shop does not submit an order the day
    it arrives: an order sits in draft through New → In Design → Execution →
    In Delivery and is submitted when the work is finished, often several days
    later. The first version of this digest reported only submissions and
    announced "0 orders yesterday" on a day the shop had taken six — a number
    that is true, useless, and actively misleading.

    So: `taken` is the day's trade, `submitted` is the day's money, and the
    two are not expected to match.
    """
    company = finance.default_company()
    if not company:
        return

    day = add_days(today(), -1)

    taken = frappe.db.count("Sales Order", {"transaction_date": day})
    submitted = frappe.db.count("Sales Order", {"docstatus": 1, "modified": (">=", day)})
    drafts = frappe.db.count("Sales Order", {"docstatus": 0})
    collected = finance.cash_collected(day, day, company)
    receivable = finance.outstanding_receivable(company)

    # A draft that has stopped moving is the thing worth noticing. Anything
    # still open after a week has either been forgotten or is stuck behind
    # something — most often stock the system says is not there (see
    # api.automate_so_flow).
    stale_cutoff = add_days(today(), -7)
    stale = frappe.db.count(
        "Sales Order", {"docstatus": 0, "transaction_date": ("<", stale_cutoff)}
    )

    lines = [
        f"• Orders taken: <b>{taken}</b>",
        f"• Orders completed: {submitted}",
        f"• Cash collected: <b>{flt(collected):,.0f} IQD</b>",
        f"• Open orders in progress: {drafts}",
    ]

    # A receivable can legitimately go negative, and "Still owed: -115,000"
    # reads as a broken number rather than as what it means: more has been
    # received against customers than was ever invoiced to them. On these books
    # that was two customers carrying credit balances, which is a bookkeeping
    # problem — a payment entered without its invoice, a duplicate, or an
    # invoice cancelled while its payment stayed. Say so in words.
    receivable = flt(receivable)
    if receivable < 0:
        lines.append(
            f"• <b>Customers are {abs(receivable):,.0f} IQD in credit</b> — more has "
            f"been received than invoiced. Usually a payment recorded without its "
            f"invoice, or an invoice cancelled while its payment stayed."
        )
    else:
        lines.append(f"• Still owed to the shop: {receivable:,.0f} IQD")
    if stale:
        lines.append(
            f"• <b>{stale} open longer than a week</b> — worth a look; an order "
            f"that has stopped moving is usually stuck, not forgotten"
        )

    _notify(
        f"{day}: {taken} order(s) taken, {flt(collected):,.0f} IQD collected",
        f"<b>{day}</b><br><br>" + "<br>".join(lines),
    )


# --------------------------------------------------------------- entrypoints
# Wired in hooks.py. Each wrapper keeps its checks independent, so one raising
# never silences the others — the entire point of this module is that nobody is
# watching it run.


def daily():
    _safe(backup_health)
    _safe(low_stock_alert)
    _safe(daily_digest)
    _safe(intake_review_queue)


def weekly():
    _safe(accrued_expenses_watch)
