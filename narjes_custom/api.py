import colorsys

# pyrefly: ignore [missing-import]
import frappe
# pyrefly: ignore [missing-import]
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
# pyrefly: ignore [missing-import]
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

from narjes_custom.business_logic import compute_canvas_cost, compute_delivery_fee, compute_sheet_cost


def _get_account(account_name, company):
    """Resolve a company account by its plain name instead of a hardcoded
    '- NS' suffix (which silently breaks for any company whose abbreviation
    isn't NS), and fail loudly and immediately if it's missing instead of
    letting a stray fallback string surface as an opaque error partway
    through document creation (see NARJES_STORE_SYSTEM.md audit follow-up)."""
    account = frappe.db.get_value("Account", {"account_name": account_name, "company": company})
    if not account:
        frappe.throw(
            f"Account '{account_name}' does not exist for company '{company}'. "
            f"Create it before this automation can run."
        )
    return account


def _get_cost_center(company):
    cost_center = frappe.db.get_value("Company", company, "cost_center")
    if not cost_center:
        frappe.throw(f"Company '{company}' has no default Cost Center set.")
    return cost_center


def automate_po_flow(doc, method):
    try:
        pr = make_purchase_receipt(doc.name)
        if len(pr.get("items") or []) > 0:
            pr.insert(ignore_permissions=True)
            pr.submit()
            pi = make_purchase_invoice(pr.name)
        else:
            from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice as make_pi_from_po
            pi = make_pi_from_po(doc.name)

        pi.insert(ignore_permissions=True)
        pi.submit()

        pe = get_payment_entry("Purchase Invoice", pi.name)
        pe.reference_no = f"AUTO-{doc.name}"
        pe.reference_date = frappe.utils.today()
        if not pe.mode_of_payment:
            pe.mode_of_payment = frappe.db.get_value("Mode of Payment", {"type": "Cash"}, "name") or "Cash"
        if not pe.paid_from:
            pe.paid_from = _get_account("Cash", doc.company)
        pe.insert(ignore_permissions=True)
        pe.submit()

        frappe.msgprint(
            f"Auto-generated Purchase Receipt, Purchase Invoice, and Payment Entry for {doc.name}")

    except Exception:
        # Log the real traceback before re-raising — the previous
        # `frappe.throw(str(e))` discarded the stack trace and exception
        # type, making production failures here nearly undebuggable.
        frappe.log_error(title=f"Purchase auto-creation failed for {doc.name}", message=frappe.get_traceback())
        raise

# --- NEW SALES AUTOMATION ---


def _append_flower_items(target_doc, flower_items, doc, default_income_account, only_stock_items=False, warehouse=None):
    """Shared by the auto Sales Invoice and auto Delivery Note so flower
    rows aren't only added to the invoice — leaving them off the Delivery
    Note meant a stock-tracked flower's consumption never hit the Stock
    Ledger (see NARJES_STORE_SYSTEM.md audit follow-up)."""
    for flower in flower_items or []:
        item_doc = frappe.get_doc("Item", flower.flower_item)
        if only_stock_items and not item_doc.is_stock_item:
            continue
        row = {
            "item_code": flower.flower_item,
            "item_name": item_doc.item_name,
            "description": item_doc.description,
            "uom": item_doc.stock_uom or "Nos",
            "stock_uom": item_doc.stock_uom or "Nos",
            "conversion_factor": 1.0,
            "qty": flower.qty,
            "rate": flower.rate,
        }
        if only_stock_items:
            row["warehouse"] = warehouse
            row["against_sales_order"] = doc.name
        else:
            row["price_list_rate"] = flower.rate
            row["amount"] = (flower.qty or 0) * (flower.rate or 0)
            row["income_account"] = default_income_account
            row["cost_center"] = _get_cost_center(doc.company)
            row["sales_order"] = doc.name
        target_doc.append("items", row)


def automate_so_flow(doc, method):
    try:
        # 1. Create and Submit Delivery Note (for physical items)
        dn = make_delivery_note(doc.name)

        stock_flowers = [f for f in (doc.get("custom_flower_items") or [])
                          if frappe.db.get_value("Item", f.flower_item, "is_stock_item")]
        if stock_flowers:
            warehouse = dn.items[0].warehouse if dn.get("items") else frappe.db.get_value(
                "Item Default", {"parent": stock_flowers[0].flower_item, "company": doc.company}, "default_warehouse"
            )
            if not warehouse:
                frappe.throw(
                    f"No warehouse available to deliver stock item '{stock_flowers[0].flower_item}' "
                    f"from Sales Order {doc.name}. Set a default warehouse for this item or company."
                )
            _append_flower_items(dn, stock_flowers, doc, None, only_stock_items=True, warehouse=warehouse)

        if len(dn.get("items") or []) > 0:
            dn.insert(ignore_permissions=True)
            dn.submit()

        # 2. Create Sales Invoice directly from SO (includes all standard items and services)
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as make_si_from_so
        si = make_si_from_so(doc.name)

        # Inject flower items into the Sales Invoice
        income_account = _get_account("Sales", doc.company)
        _append_flower_items(si, doc.get("custom_flower_items"), doc, income_account)

        si.insert(ignore_permissions=True)
        si.submit()

        # 3. Create and Receive Payment Entry
        pe = get_payment_entry("Sales Invoice", si.name)
        pe.reference_no = f"AUTO-{doc.name}"
        pe.reference_date = frappe.utils.today()
        if not pe.mode_of_payment:
            pe.mode_of_payment = frappe.db.get_value("Mode of Payment", {"type": "Cash"}, "name") or "Cash"
        if not pe.paid_to:
            pe.paid_to = _get_account("Cash", doc.company)
        pe.insert(ignore_permissions=True)
        pe.submit()

        # 4. Book Packaging Expenses Journal Entry
        packaging_costs = doc.get("packaging_costs") or 0
        if packaging_costs > 0:
            je = frappe.get_doc({
                "doctype": "Journal Entry",
                "voucher_type": "Journal Entry",
                "posting_date": frappe.utils.today(),
                "company": doc.company,
                "user_remark": f"Packaging Expenses for Sales Order {doc.name}",
                "accounts": [
                    {
                        "account": _get_account("Packaging Expenses", doc.company),
                        "debit_in_account_currency": packaging_costs
                    },
                    {
                        "account": _get_account("Cash", doc.company),
                        "credit_in_account_currency": packaging_costs
                    }
                ]
            })
            je.insert(ignore_permissions=True)
            je.submit()

        # 5. Book Painting Costs (Canvas + Sheet combined)
        total_painting_cost = doc.get("custom_total_painting_cost") or 0
        
        if total_painting_cost > 0:
            # Build canvas items for the Painting Cost document
            painting_items = []
            for row in doc.get("custom_painting_items") or []:
                painting_items.append({
                    "item_code": row.item_code,
                    "qty": row.qty,
                    "area_per_item": row.area_per_item,
                    "total_area": row.total_area
                })
            
            pc = frappe.get_doc({
                "doctype": "Painting Cost",
                "sales_order": doc.name,
                "rate_per_cm": frappe.get_cached_doc("Narjes Settings").painting_rate_per_cm or 0,
                "total_area": doc.get("custom_total_canvas_area") or 0,
                "total_painting_cost": total_painting_cost,
                "items": painting_items or [{"item_code": "N/A", "qty": 0, "area_per_item": 0, "total_area": 0}]
            })
            pc.insert(ignore_permissions=True)
            pc.submit()
            
            je_painting = frappe.get_doc({
                "doctype": "Journal Entry",
                "voucher_type": "Journal Entry",
                "posting_date": frappe.utils.today(),
                "company": doc.company,
                "user_remark": f"Painting Costs for Sales Order {doc.name} (Canvas: {doc.get('custom_canvas_painting_cost') or 0}, Sheet: {doc.get('custom_sheet_painting_cost') or 0})",
                "accounts": [
                    {
                        "account": _get_account("Painting Costs", doc.company),
                        "debit_in_account_currency": total_painting_cost
                    },
                    {
                        "account": _get_account("Cash", doc.company),
                        "credit_in_account_currency": total_painting_cost
                    }
                ]
            })
            je_painting.insert(ignore_permissions=True)
            je_painting.submit()

        # 6. Book Flower COGS Journal Entry
        flower_total = doc.get("custom_flower_total") or 0
        if flower_total > 0:
            je_flower = frappe.get_doc({
                "doctype": "Journal Entry",
                "voucher_type": "Journal Entry",
                "posting_date": frappe.utils.today(),
                "company": doc.company,
                "user_remark": f"Flower COGS for Sales Order {doc.name}",
                "accounts": [
                    {
                        "account": _get_account("Cost of Goods Sold", doc.company),
                        "debit_in_account_currency": flower_total
                    },
                    {
                        "account": _get_account("Cash", doc.company),
                        "credit_in_account_currency": flower_total
                    }
                ]
            })
            je_flower.insert(ignore_permissions=True)
            je_flower.submit()

        frappe.msgprint(
            f"Auto-generated Delivery Note, Sales Invoice, Payment Entry, and all expense JEs for {doc.name}")

    except Exception:
        frappe.log_error(title=f"Sales auto-creation failed for {doc.name}", message=frappe.get_traceback())
        raise


# def force_last_purchase_rate(doc, method):
#     # This runs right before the PO is saved
#     for item in doc.get("items"):
#         if item.item_code:
#             # Grab the last known rate from the Item master
#             last_rate = frappe.get_cached_value(
#                 "Item", item.item_code, "last_purchase_rate")

#             if last_rate:
#                 item.price_list_rate = last_rate
#                 item.rate = last_rate
#                 # ERPNext will automatically recalculate the total amounts

def sales_order_before_validate(doc, method):
    # has_flower drives the flower icon on the Sales Order kanban card.
    # It is read from the dedicated `custom_flower_items` child table — the
    # actual place flowers are entered — rather than by sniffing for the
    # substring "flower" in the main `items` table, which both missed flowers
    # named in Arabic and false-positived on any non-flower item that happened
    # to contain the word.
    has_flower = 0
    if doc.meta.has_field("custom_flower_items"):
        has_flower = 1 if any(
            row.get("flower_item") for row in doc.get("custom_flower_items", [])
        ) else 0

    # has_stand still scans the main items table: stands are ordinary items
    # there, with no child table of their own.
    has_stand = 0
    for item in doc.get("items", []):
        name = (item.get("item_name") or "").lower()
        code = (item.get("item_code") or "").lower()
        if "stand" in name or "stand" in code:
            has_stand = 1
            break

    if doc.meta.has_field("has_flower"):
        doc.has_flower = has_flower
    if doc.meta.has_field("has_stand"):
        doc.has_stand = has_stand

    fee = 0
    gov = doc.get('governorate_of_delivery')

    if not gov and doc.doctype in ["Sales Invoice", "Delivery Note"]:
        for item in doc.get("items"):
            so_name = item.get("sales_order")
            if so_name:
                gov = frappe.db.get_value("Sales Order", so_name, "governorate_of_delivery")
                break

    # Delivery fee is read live from Narjes Settings, not hardcoded, so an
    # admin can change it from the Settings form and have it take effect
    # immediately (see NARJES_STORE_SYSTEM.md §14.3/§14.5 — an earlier draft
    # of this function hardcoded 4000/6000 here, which silently disconnected
    # the Settings form from anything).
    settings = frappe.get_cached_doc("Narjes Settings")
    fee = compute_delivery_fee(gov, settings.baghdad_delivery_fee, settings.other_governorate_delivery_fee)

    if doc.meta.has_field("delivery_fees"):
        doc.delivery_fees = fee
    if doc.meta.has_field("total_with_delivery_fees"):
        doc.total_with_delivery_fees = (doc.get("total") or 0) + fee

    # Packaging cost defaults from Narjes Settings when left blank, for the
    # same reason (§14.5) — no static field default, so a rate change in
    # Settings is reflected on every new order rather than only on new
    # records created after a redeploy.
    if doc.doctype == "Sales Order" and doc.meta.has_field("packaging_costs") and not doc.get("packaging_costs"):
        doc.packaging_costs = settings.default_packaging_cost or 0

    # The ONLY ERPNext-compliant way to add a fee to grand_total without breaking GL entries
    # is to add it to the Taxes and Charges table.
    if fee > 0 and getattr(doc, "taxes", None) is not None:
        delivery_account = _get_account("Service", doc.company)
        cost_center = _get_cost_center(doc.company)

        # Check if we already have a delivery fee tax row
        found = False
        for tax in doc.taxes:
            if tax.account_head == delivery_account and tax.description == "Delivery Fees":
                tax.tax_amount = fee
                found = True
                break
                
        if not found:
            doc.append("taxes", {
                "charge_type": "Actual",
                "account_head": delivery_account,
                "cost_center": cost_center,
                "description": "Delivery Fees",
                "tax_amount": fee
            })
    
    # --- Flower Items: calculate amounts ---
    if doc.doctype == "Sales Order":
        flower_total = 0
        for flower in doc.get("custom_flower_items") or []:
            if not flower.delivery_date:
                flower.delivery_date = doc.delivery_date
            flower.amount = (flower.qty or 0) * (flower.rate or 0)
            flower_total += flower.amount

        doc.custom_flower_total = flower_total
        _sync_flower_charge(doc, flower_total)

    # Set the discount apply setting so standard Frappe calculates discount from the full total correctly
    doc.apply_discount_on = "Grand Total"


FLOWER_CHARGE_DESCRIPTION = "Flower Items"


def _sync_flower_charge(doc, flower_total):
    """Carry the flower-items total into the order total as an "Actual" row in
    Sales Taxes and Charges, mirroring how the delivery fee is handled above.

    Flowers live in their own child table (`custom_flower_items`) rather than
    in `items`, so ERPNext's own totals never see them. Writing them straight
    into total/net_total/grand_total does not work — ERPNext recalculates
    those after this hook — which is why flower amounts were silently dropped
    from what the customer was charged. A charges row is the supported way to
    add an amount to grand_total, and it keeps the GL entries balanced.

    The row is kept in sync (updated, or removed when the flowers are), so
    editing or clearing the flower table never leaves a stale charge behind.
    """
    if getattr(doc, "taxes", None) is None:
        return

    existing = [
        tax for tax in doc.taxes
        if (tax.description or "") == FLOWER_CHARGE_DESCRIPTION
    ]

    if not flower_total:
        for tax in existing:
            doc.taxes.remove(tax)
        return

    if existing:
        existing[0].tax_amount = flower_total
        for extra in existing[1:]:
            doc.taxes.remove(extra)
        return

    doc.append("taxes", {
        "charge_type": "Actual",
        "account_head": _get_account("Service", doc.company),
        "cost_center": _get_cost_center(doc.company),
        "description": FLOWER_CHARGE_DESCRIPTION,
        "tax_amount": flower_total,
    })

def sales_order_validate(doc, method):
    if doc.doctype != "Sales Order":
        return
        
    # --- Add flower qty to the standard qty total ---
    flower_qty = sum([fl.qty or 0 for fl in (doc.get("custom_flower_items") or [])])
    if flower_qty > 0:
        doc.total_qty = (doc.total_qty or 0) + flower_qty

    # Flower amounts are carried into the order total as a Sales Taxes and
    # Charges row (see _sync_flower_charge), NOT by assigning to total /
    # net_total / grand_total here.
    #
    # That is what this code used to do, and those assignments did not
    # survive: ERPNext recalculates net_total and grand_total after this hook,
    # so orders ended up storing total=40,000 (items + flowers) next to
    # net_total=30,000 (items only) and a grand_total computed from the
    # flower-less figure — i.e. the flowers were never actually charged to the
    # customer. Routing the amount through the charges table is the same
    # ERPNext-compliant mechanism already used for the delivery fee below, and
    # it survives recalculation because ERPNext derives grand_total from it.

    # --- Canvas + Sheet Items ---
    # Item flags are batched into one query instead of one `get_value` call
    # per item row — this runs on every single Sales Order/Sales Invoice/
    # Delivery Note save, not just in a report, so the per-row N+1 here was
    # the hottest instance of the pattern in the app.
    settings = frappe.get_cached_doc("Narjes Settings")
    item_codes = list({item.item_code for item in doc.items if item.item_code})
    item_flags = {}
    if item_codes:
        rows = frappe.db.get_all(
            "Item",
            filters={"name": ["in", item_codes]},
            fields=["name", "custom_is_canvas", "custom_area", "custom_is_sheet"],
        )
        item_flags = {r.name: r for r in rows}

    doc.set("custom_painting_items", [])
    total_area = 0
    rate_per_cm = settings.painting_rate_per_cm or 0

    for item in doc.items:
        flags = item_flags.get(item.item_code)
        is_canvas, area = (flags.custom_is_canvas, flags.custom_area) if flags else (0, 0)
        if is_canvas and area:
            row_area = area * item.qty
            total_area += row_area
            doc.append("custom_painting_items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "area_per_item": area,
                "total_area": row_area
            })

    doc.custom_total_canvas_area = total_area
    canvas_cost = compute_canvas_cost(total_area, rate_per_cm)
    doc.custom_canvas_painting_cost = canvas_cost

    # --- Sheet Items ---
    doc.set("custom_sheet_items", [])
    sheet_rate = settings.sheet_rate_per_item or 0
    sheet_cost = 0

    for item in doc.items:
        flags = item_flags.get(item.item_code)
        is_sheet = flags.custom_is_sheet if flags else 0
        if is_sheet:
            row_cost = compute_sheet_cost(item.qty, sheet_rate)
            sheet_cost += row_cost
            doc.append("custom_sheet_items", {
                "item_code": item.item_code,
                "qty": item.qty,
                "rate_per_sheet": sheet_rate,
                "total_cost": row_cost
            })

    doc.custom_sheet_painting_cost = sheet_cost
    
    # --- Combined Total ---
    doc.custom_total_painting_cost = canvas_cost + sheet_cost

    warn_insufficient_stock(doc)


def warn_insufficient_stock(doc):
    """Warn about short stock while the order is still a Draft.

    ERPNext only surfaces "Insufficient Stock" when the stock ledger is
    actually written — on submit — which is far too late for the shop: by then
    the order has been agreed with the customer. This runs on every save, so
    the shortage shows up as soon as the item is added.

    Deliberately a warning, not a throw: a draft must still be saveable with
    short stock (that is the normal case for made-to-order work). The hard
    block at submit is ERPNext's and is left untouched.
    """
    if doc.docstatus != 0:
        return

    default_warehouse = doc.get("set_warehouse")

    # Both tables matter, and `packed_items` is the important one:
    #
    #   * `items` holds what was sold. For a Product Bundle (e.g. "MDF 40*60")
    #     that row is is_stock_item=0 and consumes nothing itself.
    #   * `packed_items` holds the bundle's exploded components ("mdf 40*60
    #     row", "Roll Paper 60cm") — these are the real stock movements, and
    #     they are what ERPNext throws "Insufficient Stock" over on submit.
    #
    # Checking only `items` meant every bundle order silently passed here and
    # then failed at submit, which is exactly the case this warning exists for.
    rows = []
    for item in doc.get("items", []):
        if item.item_code and (item.warehouse or default_warehouse):
            rows.append((item.item_code, item.warehouse or default_warehouse, item.qty or 0))
    for packed in doc.get("packed_items", []):
        if packed.item_code and (packed.warehouse or default_warehouse):
            rows.append((packed.item_code, packed.warehouse or default_warehouse, packed.qty or 0))
    if not rows:
        return

    # Batched lookups — this runs on every save, so no per-row queries
    # (same reasoning as the item-flags batching above).
    item_codes = list({code for code, _, _ in rows})
    stock_items = {
        r.name
        for r in frappe.db.get_all(
            "Item",
            filters={"name": ["in", item_codes], "is_stock_item": 1},
            fields=["name"],
        )
    }
    if not stock_items:
        return

    pairs = {(code, wh) for code, wh, _ in rows if code in stock_items}
    balances = {
        (b.item_code, b.warehouse): b.actual_qty
        for b in frappe.db.get_all(
            "Bin",
            filters={
                "item_code": ["in", list({p[0] for p in pairs})],
                "warehouse": ["in", list({p[1] for p in pairs})],
            },
            fields=["item_code", "warehouse", "actual_qty"],
        )
    }

    # Several rows can draw on the same item+warehouse — check the demand in
    # aggregate, otherwise two rows of 3 against a stock of 5 both look fine.
    required = {}
    for code, warehouse, qty in rows:
        if code not in stock_items:
            continue
        required[(code, warehouse)] = required.get((code, warehouse), 0) + qty

    messages = []
    for (item_code, warehouse), needed in sorted(required.items()):
        available = balances.get((item_code, warehouse)) or 0
        if needed > available:
            messages.append(
                frappe._("{0} more unit(s) of {1} needed in {2} — {3} required, {4} in stock.").format(
                    frappe.utils.flt(needed - available),
                    frappe.get_desk_link("Item", item_code),
                    frappe.get_desk_link("Warehouse", warehouse),
                    frappe.utils.flt(needed),
                    frappe.utils.flt(available),
                )
            )

    if messages:
        frappe.msgprint(
            "<br>".join(messages),
            title=frappe._("Insufficient Stock"),
            indicator="orange",
        )


@frappe.whitelist()
def get_customer_info(customer):
	"""Every field of a Customer, grouped as the Customer form groups them, for
	the read-only "Customer" tab on Sales Order.

	Read from the live record on demand rather than mirrored into fetch_from
	columns on Sales Order: no duplicated master data, never stale, and new
	Customer fields appear here without a schema change.

	Permission-checked: `has_permission` is enforced explicitly because a
	whitelisted method is directly callable, and a user who may open a Sales
	Order does not automatically have read access to Customer.
	"""
	if not customer:
		return {"groups": []}

	if not frappe.has_permission("Customer", "read", doc=customer):
		frappe.throw(
			frappe._("You do not have permission to view this customer."),
			frappe.PermissionError,
		)

	doc = frappe.get_doc("Customer", customer)
	meta = frappe.get_meta("Customer")

	# Layout-only and container fieldtypes carry no value worth showing.
	skip_types = {
		"Section Break", "Column Break", "Tab Break", "HTML", "Table",
		"Table MultiSelect", "Button", "Fold", "Heading", "Image",
	}

	# Fields worth a row even when empty, because their absence is itself
	# information staff act on. An unset channel means nobody recorded where
	# this customer came from — hiding the row makes that look like the
	# question was never asked rather than never answered.
	always_show = {"channal"}

	groups = []
	current = {"label": frappe._("Details"), "fields": []}

	for field in meta.fields:
		if field.fieldtype in ("Section Break", "Tab Break"):
			if current["fields"]:
				groups.append(current)
			current = {"label": field.label or "", "fields": []}
			continue

		if field.fieldtype in skip_types or field.hidden:
			continue

		value = doc.get(field.fieldname)
		if (
			value in (None, "", 0)
			and field.fieldname not in always_show
			and field.fieldtype not in ("Check", "Currency", "Float", "Int")
		):
			continue

		current["fields"].append({
			"label": field.label or field.fieldname,
			"value": frappe.format_value(value, field, doc) if value not in (None, "") else "",
			"fieldtype": field.fieldtype,
		})

	if current["fields"]:
		groups.append(current)

	return {
		"customer": doc.name,
		"customer_name": doc.customer_name,
		"groups": [g for g in groups if g["fields"]],
	}


def item_validate(doc, method):
    """Prevent an item from being both Canvas and Sheet at the same time."""
    if doc.get("custom_is_canvas") and doc.get("custom_is_sheet"):
        frappe.throw("An item cannot be both a Canvas and a Sheet. Please select only one.")

@frappe.whitelist()
def discard_draft(docname):
    """`frappe.db.set_value` bypasses permission checks entirely (unlike
    `doc.save()`/`doc.cancel()`), so without an explicit check here any
    logged-in user — regardless of their actual Sales Order permissions —
    could discard someone else's draft (see NARJES_STORE_SYSTEM.md audit
    follow-up)."""
    frappe.has_permission("Sales Order", doc=docname, ptype="write", throw=True)
    doc = frappe.get_doc("Sales Order", docname)
    if doc.docstatus == 0:
        frappe.db.set_value("Sales Order", docname, "docstatus", 2)
        frappe.db.set_value("Sales Order", docname, "status", "Cancelled")
        frappe.db.set_value("Sales Order", docname, "order_phase", "Cancelled")
        return True
    return False

@frappe.whitelist()
def cancel_sales_order_and_links(docname):
    frappe.has_permission("Sales Order", doc=docname, ptype="cancel", throw=True)

    # 1. Cancel Linked Payment Entries (identified by reference_no = AUTO-{docname})
    pe_names = frappe.get_all("Payment Entry", filters={"reference_no": f"AUTO-{docname}", "docstatus": 1}, pluck="name")
    for pe in pe_names:
        doc = frappe.get_doc("Payment Entry", pe)
        doc.cancel()
        
    # 2. Cancel Linked Sales Invoices (where items reference the Sales Order)
    si_names = frappe.get_all("Sales Invoice Item", filters={"sales_order": docname, "docstatus": 1}, pluck="parent")
    si_names = list(set(si_names))
    for si in si_names:
        doc = frappe.get_doc("Sales Invoice", si)
        doc.cancel()
        
    # 3. Cancel Linked Delivery Notes
    dn_names = frappe.get_all("Delivery Note Item", filters={"against_sales_order": docname, "docstatus": 1}, pluck="parent")
    dn_names = list(set(dn_names))
    for dn in dn_names:
        doc = frappe.get_doc("Delivery Note", dn)
        doc.cancel()
        
    # 4. Cancel the Sales Order
    so = frappe.get_doc("Sales Order", docname)
    if so.docstatus == 1:
        so.cancel()
        
    return True


# --- PURCHASE ORDER: Transportation Charges ---

def purchase_order_before_validate(doc, method):
    """Sync the transportation_charges custom field with the Taxes and Charges table.
    This ensures data integrity even if the PO is created via API without JS running.
    """
    amount = doc.get("transportation_charges") or 0
    description = "Transportation Charges"

    # Match by description alone so a PO with no transportation charge never
    # requires the account to exist — the account is only resolved (and
    # required) when there's actually a nonzero charge to book.
    existing_row = None
    for tax in doc.get("taxes", []):
        if tax.description == description:
            existing_row = tax
            break

    if amount > 0:
        account_head = _get_account("Transportation Charges", doc.company)
        if existing_row:
            existing_row.tax_amount = amount
            existing_row.account_head = account_head
        else:
            doc.append("taxes", {
                "charge_type": "Actual",
                "account_head": account_head,
                "description": description,
                "category": "Valuation and Total",
                "add_deduct_tax": "Add",
                "tax_amount": amount,
            })
    else:
        # Remove the transportation row if amount is 0 or empty
        if existing_row:
            doc.taxes = [t for t in doc.taxes if t.description != description]

def setup_packaging():
    """Create the Packaging Expenses account used by automate_so_flow's
    Journal Entry. The `packaging_costs` Sales Order field itself is created
    by narjes_custom.setup.custom_fields.run() — this function no longer
    duplicates that (see NARJES_STORE_SYSTEM.md §14.1/§14.2: having the same
    field defined in more than one setup script is exactly the kind of
    drift that made the schema unreliable)."""
    company = frappe.get_all("Company", limit=1)[0].name
    parent_account = frappe.get_all("Account", filters={"account_name": "Direct Income - NS", "company": company}, limit=1)

    if parent_account:
        parent_account_name = parent_account[0].name
        account_name = "Packaging Expenses - NS"

        if not frappe.db.exists("Account", {"account_name": account_name, "company": company}):
            doc = frappe.get_doc({
                "doctype": "Account",
                "account_name": account_name,
                "parent_account": parent_account_name,
                "company": company,
                "root_type": "Income",
                "is_group": 0,
                "account_type": "Income Account"
            })
            doc.insert(ignore_permissions=True)
            print(f"Created Account: {doc.name}")
        else:
            print("Account already exists.")
    else:
        print("Parent account 'Direct Income - NS' not found!")

    frappe.db.commit()


@frappe.whitelist()
def get_home_dashboard_data():
    """
    Fetch KPI metrics and time-series data for the Home Dashboard charts.
    """
    frappe.has_permission("Sales Order", ptype="read", throw=True)

    today_str = frappe.utils.today()
    first_day_of_month = frappe.utils.get_first_day(today_str)

    # 1. KPI Metrics
    # Only docstatus = 1 (submitted) counts as revenue/orders — a draft
    # Sales Order isn't a confirmed order yet, so `docstatus != 2` (which
    # counted drafts alongside submitted ones) overstated "today's revenue"
    # with unconfirmed orders (see NARJES_STORE_SYSTEM.md audit follow-up).
    today_rev = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Order`
        WHERE transaction_date = %s AND docstatus = 1
    """, (today_str,))[0][0] or 0.0

    today_orders_count = frappe.db.count("Sales Order", filters={"transaction_date": today_str, "docstatus": 1})

    pending_deliveries_count = frappe.db.count("Sales Order", filters={"status": ["in", ["To Deliver", "To Deliver and Bill"]], "docstatus": 1})

    total_customers_count = frappe.db.count("Customer")

    # 2. Financial Time Series (Last 14 days)
    start_date = frappe.utils.add_days(today_str, -13)

    so_daily = frappe.db.sql("""
        SELECT transaction_date, COALESCE(SUM(grand_total), 0) as total
        FROM `tabSales Order`
        WHERE transaction_date >= %s AND docstatus = 1
        GROUP BY transaction_date
        ORDER BY transaction_date ASC
    """, (start_date,), as_dict=True)

    po_daily = frappe.db.sql("""
        SELECT transaction_date, COALESCE(SUM(grand_total), 0) as total
        FROM `tabPurchase Order`
        WHERE transaction_date >= %s AND docstatus = 1
        GROUP BY transaction_date
        ORDER BY transaction_date ASC
    """, (start_date,), as_dict=True)

    so_map = {str(r.transaction_date): float(r.total) for r in so_daily}
    po_map = {str(r.transaction_date): float(r.total) for r in po_daily}

    labels = []
    income_data = []
    outcome_data = []
    net_revenue_data = []

    curr = frappe.utils.getdate(start_date)
    end = frappe.utils.getdate(today_str)

    while curr <= end:
        ds = str(curr)
        labels.append(frappe.utils.formatdate(ds, "dd MMM"))
        inc = so_map.get(ds, 0.0)
        out = po_map.get(ds, 0.0)
        income_data.append(inc)
        outcome_data.append(out)
        net_revenue_data.append(inc - out)
        curr = frappe.utils.add_days(curr, 1)

    return {
        "kpis": {
            "today_revenue": today_rev,
            "today_orders": today_orders_count,
            "pending_deliveries": pending_deliveries_count,
            "total_customers": total_customers_count
        },
        "charts": {
            "labels": labels,
            "income": income_data,
            "outcome": outcome_data,
            "net_revenue": net_revenue_data
        }
    }

# Narjes Ledger theme accent presets — light+dark {fern, strong, tint}
# triples, matching exactly what was shown in the approved theme-preview
# artifact. "Fern" is the shipped default already baked into tokens.css;
# the other three (and "Custom") are patched in live by narjes_theme.js
# from bootinfo.narjes_theme, so switching accents needs no bench build.
THEME_PRESETS = {
    "Fern": {
        "light": {"fern": "#2E5C46", "strong": "#234433", "tint": "#E4F0EA"},
        "dark": {"fern": "#7FD4AE", "strong": "#9EE0C3", "tint": "#1E2E26"},
    },
    "Plum": {
        "light": {"fern": "#6B3757", "strong": "#54293F", "tint": "#F3E6EC"},
        "dark": {"fern": "#DE9FC7", "strong": "#EBBEDA", "tint": "#2E1E28"},
    },
    "Teal": {
        "light": {"fern": "#1F5C63", "strong": "#17454A", "tint": "#E1EEEE"},
        "dark": {"fern": "#6FCBD1", "strong": "#95DBDF", "tint": "#182B2C"},
    },
    "Ochre": {
        "light": {"fern": "#8A5A17", "strong": "#6B4611", "tint": "#F3E9D6"},
        "dark": {"fern": "#E0A44C", "strong": "#EABE78", "tint": "#332813"},
    },
}


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) / 255 for i in (0, 2, 4))


def _rgb_to_hex(rgb):
    return "#" + "".join(f"{round(max(0.0, min(1.0, c)) * 255):02X}" for c in rgb)


def _relative_luminance(rgb):
    def channel(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast_ratio(rgb1, rgb2):
    l1, l2 = _relative_luminance(rgb1), _relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _derive_custom_accent(hex_color):
    """Derive a full light+dark accent pair (hover shade, soft tint, and a
    dark-mode variant) from the single color an admin picks in Narjes
    Settings > Appearance, instead of asking a shop owner to hand-pick 6
    mutually-consistent, contrast-safe colors. Nudges lightness until the
    light-mode accent holds at least 4.5:1 contrast against white button
    text, and until the dark-mode accent holds the same against the app's
    near-black dark paper — so a poorly chosen custom color can't silently
    ship an unreadable button in either mode."""
    h, l, s = colorsys.rgb_to_hls(*_hex_to_rgb(hex_color))
    white = (1.0, 1.0, 1.0)
    near_black = _hex_to_rgb("#12160F")

    light_l = l
    while light_l > 0.05 and _contrast_ratio(colorsys.hls_to_rgb(h, light_l, s), white) < 4.5:
        light_l -= 0.04
    light_fern = colorsys.hls_to_rgb(h, light_l, s)
    light_strong = colorsys.hls_to_rgb(h, max(0.05, light_l - 0.08), s)
    light_tint = colorsys.hls_to_rgb(h, 0.93, min(s, 0.35))

    dark_l = 0.72
    while dark_l < 0.95 and _contrast_ratio(colorsys.hls_to_rgb(h, dark_l, s), near_black) < 4.5:
        dark_l += 0.04
    dark_fern = colorsys.hls_to_rgb(h, dark_l, min(s, 0.75))
    dark_strong = colorsys.hls_to_rgb(h, min(0.95, dark_l + 0.1), min(s, 0.75))
    dark_tint = colorsys.hls_to_rgb(h, 0.14, min(s, 0.45))

    return {
        "light": {
            "fern": _rgb_to_hex(light_fern),
            "strong": _rgb_to_hex(light_strong),
            "tint": _rgb_to_hex(light_tint),
        },
        "dark": {
            "fern": _rgb_to_hex(dark_fern),
            "strong": _rgb_to_hex(dark_strong),
            "tint": _rgb_to_hex(dark_tint),
        },
    }


def _resolve_theme(settings):
    accent = settings.theme_accent or "Fern"
    if accent == "Custom" and settings.custom_accent_color:
        return _derive_custom_accent(settings.custom_accent_color)
    return THEME_PRESETS.get(accent, THEME_PRESETS["Fern"])


@frappe.whitelist()
def extend_bootinfo(bootinfo):
    """Force default home page to be our custom dashboard, and expose
    Narjes Settings' Home Dashboard defaults + Quick Shortcuts for
    narjes_home.js to use (see NARJES_STORE_SYSTEM.md §14.3 — this used to
    get silently dropped by an earlier draft of the SO/PO automation work,
    which emptied the Home Dashboard's shortcuts grid for every user)."""
    bootinfo.home_page = "narjes-home"

    # Narjes Ledger kill switch (theme plan P0.7): site_config
    # narjes_theme_enabled, default on. narjes.bundle.js reads this and adds/
    # removes body.narjes-ledger — every structural theme rule is scoped to
    # that class, so flipping the flag reverts to near-stock with no rebuild.
    bootinfo.narjes_theme_enabled = bool(
        frappe.conf.get("narjes_theme_enabled", 1)
    )

    settings = frappe.get_cached_doc("Narjes Settings")
    bootinfo.narjes_theme = _resolve_theme(settings)
    bootinfo.narjes_settings = {
        "default_show_ai_intake": bool(settings.default_show_ai_intake),
        "default_show_shortcuts": bool(settings.default_show_shortcuts),
        "default_show_analytics": bool(settings.default_show_analytics),
        "shortcuts": [
            {"label": row.label, "icon": row.icon, "route": row.route, "role": row.role}
            for row in settings.quick_shortcuts
        ],
        # Business constants, so client-side previews (e.g. sales_order.js)
        # can read the live configured values instead of hardcoding their
        # own copies that silently drift from Narjes Settings (§14.5).
        "baghdad_delivery_fee": settings.baghdad_delivery_fee or 0,
        "other_governorate_delivery_fee": settings.other_governorate_delivery_fee or 0,
        "painting_rate_per_cm": settings.painting_rate_per_cm or 0,
        "sheet_rate_per_item": settings.sheet_rate_per_item or 0,
        "default_packaging_cost": settings.default_packaging_cost or 0,
    }

WORKSPACE_NAME = "Narjes Dashboard"


@frappe.whitelist()
def ensure_narjes_dashboard_workspace():
    """The single canonical way to (re)create the 'Narjes Dashboard'
    Workspace that Narjes Settings' sidebar sync (see
    narjes_settings.sync_sidebar_links) targets by name.

    This used to be duplicated across three near-identical implementations
    (this function under an earlier name, create_narjes_dashboard(), and a
    standalone fix_workspace.py) that disagreed on details and didn't
    always agree on the workspace name — see NARJES_STORE_SYSTEM.md §14.4.
    There is now exactly one.

    Idempotent: reloads the narjes-home page doc from disk, and only
    touches the Workspace if it's missing or was left in the broken state
    of being linked to a module (a JSON-backed workspace Frappe expects a
    matching module JSON file for, which this app doesn't ship) instead of
    being a plain DB-driven public workspace.
    """
    if "System Manager" not in frappe.get_roles():
        frappe.throw("Not permitted", frappe.PermissionError)

    frappe.reload_doc("narjes_custom", "page", "narjes_home")

    existing = frappe.db.get_value("Workspace", WORKSPACE_NAME, ["name", "module"], as_dict=True)
    if existing and not existing.module:
        return f"Workspace '{WORKSPACE_NAME}' already exists and is healthy."

    if existing:
        frappe.delete_doc("Workspace", WORKSPACE_NAME, force=1, ignore_permissions=True)

    frappe.get_doc({
        "doctype": "Workspace",
        "name": WORKSPACE_NAME,
        "title": WORKSPACE_NAME,
        "label": WORKSPACE_NAME,
        "public": 1,
        "icon": "home",
        "sequence_id": 1,
        "content": '[{"type": "header", "data": {"text": "Narjes Dashboard", "level": 2}}]',
        "links": [{"type": "Link", "label": "Home Dashboard", "link_to": "narjes-home", "link_type": "Page"}],
    }).insert(ignore_permissions=True)

    frappe.db.commit()
    return f"Rebuilt Workspace '{WORKSPACE_NAME}'."
