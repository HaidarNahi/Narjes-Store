"""
narjes_custom.setup.flower_placeholder
======================================
Provisions the one Item that makes a flowers-only Sales Order possible.

Why this exists
---------------
Flowers are deliberately kept out of the standard `items` table: they live in
their own `custom_flower_items` child table and reach the order total through
a "Flower Items" Sales Taxes and Charges row (narjes_custom.api.
_sync_flower_charge). That is the data model, and it holds for every order
that mixes flowers with ordinary items.

It cannot hold for an order that is *nothing but* flowers, because ERPNext
marks Sales Order.items as mandatory — an empty `items` does not even fail
cleanly, it crashes inside the totals calculation with
"TypeError: bad operand type for abs(): 'NoneType'".

The obvious workarounds are both wrong:

  * Copying the flower into `items` as well bills it twice — once through
    net_total and once through the Flower Items charge. Measured on a 10,000
    flower with a 4,000 delivery fee, that produces a 24,000 order instead of
    a 14,000 one.
  * Putting the flower into `items` at rate 0 does not stay at 0. ERPNext
    re-prices a zero-rate row from the item's Item Price during validate, so
    the "harmless placeholder" silently comes back at full price and
    double-bills in exactly the same way.

So the placeholder is a separate, non-stock item that carries no Item Price
at all. With nothing to re-price from, its rate stays 0, `items` is satisfied,
net_total is 0, and the flowers are billed exactly once through their own
charge row — while `custom_flower_items` stays the only place a flower is
ever recorded.

Run via: bench --site <site> execute narjes_custom.setup.flower_placeholder.run
(also wired into after_migrate, so it self-heals).
"""

import frappe

ITEM_CODE = "FLOWER-ORDER"
ITEM_NAME = "Flower Order"
DESCRIPTION = (
    "Placeholder line for orders made up entirely of flowers. The flowers "
    "themselves are itemised in the Flower Items table and billed through the "
    "Flower Items charge — this line is always zero."
)


def _item_group():
    for preferred in ("Services", "Products", "All Item Groups"):
        if frappe.db.exists("Item Group", preferred):
            return preferred
    return frappe.db.get_value("Item Group", {"is_group": 0}, "name")


def ensure():
    """Return the placeholder item code, creating it if it is missing.

    Safe to call on every intake: it is a single cached exists() once the item
    is in place.
    """
    if frappe.db.exists("Item", ITEM_CODE):
        return ITEM_CODE

    doc = frappe.get_doc({
        "doctype": "Item",
        "item_code": ITEM_CODE,
        "item_name": ITEM_NAME,
        "item_group": _item_group(),
        "stock_uom": "Nos",
        "is_stock_item": 0,
        "is_sales_item": 1,
        "is_purchase_item": 0,
        "include_item_in_manufacturing": 0,
        # Must never be flagged as a flower: has_flower is derived partly from
        # the items table, and this line is not itself a flower.
        "custom_is_flower": 0,
        "description": DESCRIPTION,
    })

    # Production carries mandatory Custom Fields on Item that this repo does
    # not define — `rate` (Currency, reqd=1, default "") is one, which is why
    # this insert passed locally and failed on the live site with
    # "[Item, FLOWER-ORDER]: rate". Rather than hardcoding one field name and
    # waiting to be surprised by the next, fill every mandatory field we have
    # not already set with a harmless empty value for its type. A zero rate is
    # the correct value here anyway: this line is never charged.
    for df in doc.meta.get("fields", {"reqd": 1}):
        if doc.get(df.fieldname) not in (None, ""):
            continue
        if df.fieldtype in ("Currency", "Float", "Int", "Percent", "Check"):
            doc.set(df.fieldname, 0)
        elif df.fieldtype in ("Data", "Small Text", "Text", "Long Text", "Text Editor"):
            doc.set(df.fieldname, ITEM_NAME)

    doc.insert(ignore_permissions=True)

    return ITEM_CODE


def run():
    existed = frappe.db.exists("Item", ITEM_CODE)
    ensure()
    # Never let a price attach to this item — an Item Price would make ERPNext
    # re-price the line away from 0 and quietly double-bill the flowers.
    prices = frappe.get_all("Item Price", filters={"item_code": ITEM_CODE}, pluck="name")
    for name in prices:
        frappe.delete_doc("Item Price", name, ignore_permissions=True, force=True)

    if prices:
        print(f"Removed {len(prices)} stray Item Price row(s) from '{ITEM_CODE}'.")
    print(
        f"Flower placeholder item '{ITEM_CODE}' "
        + ("already present." if existed else "created.")
    )
