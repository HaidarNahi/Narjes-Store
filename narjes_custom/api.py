# pyrefly: ignore [missing-import]
import frappe
# pyrefly: ignore [missing-import]
from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
# pyrefly: ignore [missing-import]
from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice


def automate_po_flow(doc, method):
    try:
        pr = make_purchase_receipt(doc.name)
        pr.insert(ignore_permissions=True)
        pr.submit()

        pi = make_purchase_invoice(pr.name)
        pi.insert(ignore_permissions=True)
        pi.submit()

        pe = get_payment_entry("Purchase Invoice", pi.name)
        pe.reference_no = f"AUTO-{doc.name}"
        pe.reference_date = frappe.utils.today()
        pe.insert(ignore_permissions=True)
        pe.submit()

        frappe.msgprint(
            f"Auto-generated Purchase Recipt, Purchase Invoice, and Payment Entry for {doc.name}")

    except Exception as e:
        frappe.throw(f"Auto-creation failed: {str(e)}")

# --- NEW SALES AUTOMATION ---


def automate_so_flow(doc, method):
    try:
        # 1. Create and Submit Delivery Note
        dn = make_delivery_note(doc.name)
        dn.insert(ignore_permissions=True)
        dn.submit()

        # 2. Create and Submit Sales Invoice
        si = make_sales_invoice(dn.name)
        si.insert(ignore_permissions=True)
        si.submit()

        # 3. Create and Receive Payment Entry
        pe = get_payment_entry("Sales Invoice", si.name)
        pe.reference_no = f"AUTO-{doc.name}"
        pe.reference_date = frappe.utils.today()
        pe.insert(ignore_permissions=True)
        pe.submit()

        frappe.msgprint(
            f"Auto-generated Delivert Note, Sales Invoice, and Payment Entry for {doc.name}")

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

    if gov == 'بغداد':
        fee = 4000
    elif gov:
        fee = 6000

    if doc.meta.has_field("delivery_fees"):
        doc.delivery_fees = fee
    if doc.meta.has_field("total_with_delivery_fees"):
        doc.total_with_delivery_fees = (doc.get("total") or 0) + fee

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
            
    # Set the discount apply setting so standard Frappe calculates discount from the full total correctly
    doc.apply_discount_on = "Grand Total"

def sales_order_validate(doc, method):
    # We no longer manually overwrite grand_total!
    # By injecting the tax row in before_validate, ERPNext's standard calculate_taxes_and_totals
    # will naturally compute a balanced grand_total and properly format the GL entries!
    pass

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
