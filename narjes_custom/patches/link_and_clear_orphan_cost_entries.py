"""Repair the sale-time cost entries created before they had a real order link.

Two things happen here, in order:

1. Backfill `custom_sales_order` on every existing cost Journal Entry by
   parsing the order name out of `user_remark` — the only place the
   relationship was ever recorded. After this, the entries are reportable and
   the on_cancel hook can find them.

2. Cancel the entries whose order is cancelled or deleted. These were
   overstating expenses (understating profit) against orders that no longer
   exist, and nothing would ever have cleaned them up.

Cancelled, never deleted: these are submitted accounting documents, so the
reversal has to stay on the record.
"""

import re

import frappe

ORDER_IN_REMARK = re.compile(r"Sales Order\s+(\S+)")


def execute():
    # Patches run BEFORE after_migrate, so the link field does not exist yet on
    # the first pass. Create it here rather than bailing out — a patch only ever
    # runs once, so returning early would have silently skipped the repair
    # forever (which is exactly what happened on the first deploy of this).
    if not frappe.db.has_column("Journal Entry", "custom_sales_order"):
        from narjes_custom.setup.custom_fields import run as ensure_custom_fields

        ensure_custom_fields()
        frappe.db.commit()

    if not frappe.db.has_column("Journal Entry", "custom_sales_order"):
        return

    entries = frappe.db.sql(
        """
        SELECT name, user_remark
        FROM `tabJournal Entry`
        WHERE docstatus = 1
          AND user_remark LIKE '%%Sales Order%%'
          AND (custom_sales_order IS NULL OR custom_sales_order = '')
        """,
        as_dict=True,
    )

    linked = 0
    orphans = []
    for entry in entries:
        match = ORDER_IN_REMARK.search(entry.user_remark or "")
        if not match:
            continue
        order = match.group(1).strip().rstrip(".,)")
        status = frappe.db.get_value("Sales Order", order, "docstatus")

        if status is not None:
            # db_set on the raw column: the JE is submitted, so a normal save
            # is not allowed, and this field carries no accounting meaning
            frappe.db.set_value(
                "Journal Entry", entry.name, "custom_sales_order", order,
                update_modified=False,
            )
            linked += 1

        if status is None or status == 2:
            orphans.append((entry.name, order))

    cancelled, freed = 0, 0.0
    for name, order in orphans:
        try:
            doc = frappe.get_doc("Journal Entry", name)
            freed += float(doc.total_debit or 0)
            doc.cancel()
            cancelled += 1
        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Orphan cost entry {name} (order {order}) could not be cancelled",
            )

    frappe.db.commit()
    print(
        f"cost entries: linked {linked}, cancelled {cancelled} orphans "
        f"releasing {freed:,.0f} of overstated expense"
    )
