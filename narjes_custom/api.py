# pyrefly: ignore [missing-import]
import frappe
# pyrefly: ignore [missing-import]
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
# pyrefly: ignore [missing-import]
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice

from narjes_custom.business_logic import compute_canvas_cost, compute_delivery_fee, compute_sheet_cost


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
            pe.paid_from = frappe.db.get_value("Account", {"account_name": "Cash", "company": doc.company}) or "Cash - NS"
        pe.insert(ignore_permissions=True)
        pe.submit()

        frappe.msgprint(
            f"Auto-generated Purchase Receipt, Purchase Invoice, and Payment Entry for {doc.name}")

    except Exception as e:
        frappe.throw(f"Auto-creation failed: {str(e)}")

# --- NEW SALES AUTOMATION ---


def automate_so_flow(doc, method):
    try:
        # 1. Create and Submit Delivery Note (for physical items)
        dn = make_delivery_note(doc.name)
        if len(dn.get("items") or []) > 0:
            dn.insert(ignore_permissions=True)
            dn.submit()
            
        # 2. Create Sales Invoice directly from SO (includes all standard items and services)
        from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice as make_si_from_so
        si = make_si_from_so(doc.name)
        
        # Inject flower items into the Sales Invoice
        for flower in doc.get("custom_flower_items") or []:
            item_doc = frappe.get_doc("Item", flower.flower_item)
            si.append("items", {
                "item_code": flower.flower_item,
                "item_name": item_doc.item_name,
                "description": item_doc.description,
                "uom": item_doc.stock_uom or "Nos",
                "stock_uom": item_doc.stock_uom or "Nos",
                "conversion_factor": 1.0,
                "qty": flower.qty,
                "rate": flower.rate,
                "price_list_rate": flower.rate,
                "amount": (flower.qty or 0) * (flower.rate or 0),
                "income_account": "Sales - NS",
                "cost_center": frappe.db.get_value("Company", doc.company, "cost_center") or "Main - NS",
                "sales_order": doc.name
            })
        
        si.insert(ignore_permissions=True)
        si.submit()

        # 3. Create and Receive Payment Entry
        pe = get_payment_entry("Sales Invoice", si.name)
        pe.reference_no = f"AUTO-{doc.name}"
        pe.reference_date = frappe.utils.today()
        if not pe.mode_of_payment:
            pe.mode_of_payment = frappe.db.get_value("Mode of Payment", {"type": "Cash"}, "name") or "Cash"
        if not pe.paid_to:
            pe.paid_to = frappe.db.get_value("Account", {"account_name": "Cash", "company": doc.company}) or "Cash - NS"
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
                        "account": "Packaging Expenses - NS",
                        "debit_in_account_currency": packaging_costs
                    },
                    {
                        "account": "Cash - NS",
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
                        "account": "Painting Costs - NS",
                        "debit_in_account_currency": total_painting_cost
                    },
                    {
                        "account": "Cash - NS",
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
                        "account": "Cost of Goods Sold - NS",
                        "debit_in_account_currency": flower_total
                    },
                    {
                        "account": "Cash - NS",
                        "credit_in_account_currency": flower_total
                    }
                ]
            })
            je_flower.insert(ignore_permissions=True)
            je_flower.submit()

        frappe.msgprint(
            f"Auto-generated Delivery Note, Sales Invoice, Payment Entry, and all expense JEs for {doc.name}")

    except Exception as e:
        frappe.throw(f"Sales auto-creation failed: {str(e)}")


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
    has_flower = 0
    has_stand = 0
    for item in doc.get("items", []):
        name = (item.get("item_name") or "").lower()
        code = (item.get("item_code") or "").lower()
        if "flower" in name or "flower" in code:
            has_flower = 1
        if "stand" in name or "stand" in code:
            has_stand = 1
            
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
        delivery_account = "Service - NS" # Dynamically found income account
        cost_center = "Main - NS"
        
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
            
    # Set the discount apply setting so standard Frappe calculates discount from the full total correctly
    doc.apply_discount_on = "Grand Total"

def sales_order_validate(doc, method):
    if doc.doctype != "Sales Order":
        return
        
    # --- Add flower qty and amounts to standard totals ---
    flower_qty = sum([fl.qty or 0 for fl in (doc.get("custom_flower_items") or [])])
    if flower_qty > 0:
        doc.total_qty = (doc.total_qty or 0) + flower_qty
        
    flower_total = getattr(doc, "custom_flower_total", 0)
    if flower_total > 0:
        doc.total = (doc.total or 0) + flower_total
        doc.net_total = (doc.net_total or 0) + flower_total
        doc.base_total = (doc.base_total or 0) + flower_total
        doc.base_net_total = (doc.base_net_total or 0) + flower_total
        
        # Calculate new grand_total after adding to net_total
        taxes_total = sum([t.tax_amount for t in (doc.get("taxes") or [])])
        doc.grand_total = doc.net_total + taxes_total - (doc.discount_amount or 0)
        doc.base_grand_total = doc.grand_total # Assuming 1:1 conversion for IQD/USD standard
        
    # --- Canvas Items ---
    settings = frappe.get_cached_doc("Narjes Settings")
    doc.set("custom_painting_items", [])
    total_area = 0
    rate_per_cm = settings.painting_rate_per_cm or 0

    for item in doc.items:
        is_canvas, area = frappe.db.get_value("Item", item.item_code, ["custom_is_canvas", "custom_area"]) or (0, 0)
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
        is_sheet = frappe.db.get_value("Item", item.item_code, "custom_is_sheet") or 0
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


def item_validate(doc, method):
    """Prevent an item from being both Canvas and Sheet at the same time."""
    if doc.get("custom_is_canvas") and doc.get("custom_is_sheet"):
        frappe.throw("An item cannot be both a Canvas and a Sheet. Please select only one.")

@frappe.whitelist()
def discard_draft(docname):
    doc = frappe.get_doc("Sales Order", docname)
    if doc.docstatus == 0:
        frappe.db.set_value("Sales Order", docname, "docstatus", 2)
        frappe.db.set_value("Sales Order", docname, "status", "Cancelled")
        frappe.db.set_value("Sales Order", docname, "order_phase", "Cancelled")
        return True
    return False

@frappe.whitelist()
def cancel_sales_order_and_links(docname):
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
    account_head = "Transportation Charges - NS"
    description = "Transportation Charges"

    # Find existing transportation row
    existing_row = None
    for tax in doc.get("taxes", []):
        if tax.account_head == account_head and tax.description == description:
            existing_row = tax
            break

    if amount > 0:
        if existing_row:
            existing_row.tax_amount = amount
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
            doc.taxes = [t for t in doc.taxes if not (t.account_head == account_head and t.description == description)]

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
    today_str = frappe.utils.today()
    first_day_of_month = frappe.utils.get_first_day(today_str)
    
    # 1. KPI Metrics
    today_rev = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Order`
        WHERE transaction_date = %s AND docstatus != 2
    """, (today_str,))[0][0] or 0.0

    today_orders_count = frappe.db.count("Sales Order", filters={"transaction_date": today_str, "docstatus": ["!=", 2]})

    pending_deliveries_count = frappe.db.count("Sales Order", filters={"status": ["in", ["To Deliver", "To Deliver and Bill"]], "docstatus": 1})

    total_customers_count = frappe.db.count("Customer")

    # 2. Financial Time Series (Last 14 days)
    start_date = frappe.utils.add_days(today_str, -13)
    
    so_daily = frappe.db.sql("""
        SELECT transaction_date, COALESCE(SUM(grand_total), 0) as total
        FROM `tabSales Order`
        WHERE transaction_date >= %s AND docstatus != 2
        GROUP BY transaction_date
        ORDER BY transaction_date ASC
    """, (start_date,), as_dict=True)

    po_daily = frappe.db.sql("""
        SELECT transaction_date, COALESCE(SUM(grand_total), 0) as total
        FROM `tabPurchase Order`
        WHERE transaction_date >= %s AND docstatus != 2
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

@frappe.whitelist()
def extend_bootinfo(bootinfo):
    """Force default home page to be our custom dashboard, and expose
    Narjes Settings' Home Dashboard defaults + Quick Shortcuts for
    narjes_home.js to use (see NARJES_STORE_SYSTEM.md §14.3 — this used to
    get silently dropped by an earlier draft of the SO/PO automation work,
    which emptied the Home Dashboard's shortcuts grid for every user)."""
    bootinfo.home_page = "narjes-home"

    settings = frappe.get_cached_doc("Narjes Settings")
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
