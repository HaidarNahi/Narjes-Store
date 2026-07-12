"""
narjes_custom.ai_intake.api
=============================
Whitelisted Frappe API endpoints for AI Order Intake.

Three endpoints, cleanly separated responsibilities:
  1. process_intake()      — extraction + matching, returns a record for review
  2. confirm_intake()      — human-confirmed, writes Customer + Sales Order
  3. get_item_catalog()    — returns available items for frontend autocomplete
  4. get_customers_for_search() — live customer search
"""

import hashlib
import json

import frappe
from frappe.utils import today

from narjes_custom.ai_intake.extraction import (
    ExtractionError,
    extract_order,
    get_item_catalog,
    is_complete_extraction,
)
from narjes_custom.ai_intake.matching import match_customer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_text(raw_text: str) -> str:
    """SHA-256 of normalized text (stripped, lowercased) for idempotency."""
    normalized = " ".join(raw_text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _get_default_so_items_params():
    """Get required SO item defaults from ERPNext."""
    warehouses = frappe.get_all(
        "Warehouse", filters={"is_group": 0, "disabled": 0}, pluck="name", limit=1
    )
    default_warehouse = warehouses[0] if warehouses else None
    default_uom = "Nos"
    return default_warehouse, default_uom


# ---------------------------------------------------------------------------
# Endpoint 1: process_intake
# ---------------------------------------------------------------------------

@frappe.whitelist()
def process_intake(raw_text: str) -> dict:
    """
    Step 1 of the AI intake flow.

    - Checks idempotency (same text → same hash → returns existing record)
    - Calls Gemini for extraction (AI layer)
    - Runs deterministic customer matching (no AI)
    - Creates and returns an AI Order Intake record

    Returns a dict with the intake record data for the frontend review screen.
    Never creates Customer or Sales Order — that only happens in confirm_intake().
    """
    if not raw_text or not raw_text.strip():
        frappe.throw("Please paste the order text before processing.")

    input_hash = _hash_text(raw_text)

    # ── Idempotency check ──────────────────────────────────────────────────
    existing = frappe.db.get_value(
        "AI Order Intake",
        {"input_hash": input_hash},
        ["name", "status", "created_sales_order", "extracted_json"],
        as_dict=True,
    )
    if existing:
        if existing.status == "Confirmed" or existing.created_sales_order:
            return {
                "duplicate": True,
                "intake_name": existing.name,
                "created_sales_order": existing.created_sales_order,
                "message": (
                    f"This exact order text was already processed. "
                    f"Sales Order {existing.created_sales_order} was created from it."
                ),
            }
        elif existing.status in ["Draft", "Needs Review"]:
            doc = frappe.get_doc("AI Order Intake", existing.name)
            return _intake_to_response(doc)
        # If it's Failed, we continue to retry processing!

    # ── AI Extraction ──────────────────────────────────────────────────────
    extracted = None
    error_msg = None
    status = "Draft"

    try:
        extracted = extract_order(raw_text)
        status = "Needs Review"
    except ExtractionError as e:
        error_msg = str(e)
        status = "Failed"
    except Exception as e:
        error_msg = f"Unexpected error during extraction: {str(e)}"
        status = "Failed"

    # ── Deterministic Customer Matching (no AI) ────────────────────────────
    match_result = {"customer": None, "method": "None", "confidence": 0.0}
    if extracted:
        try:
            match_result = match_customer(
                extracted_phones=extracted.get("phone_numbers", []),
                extracted_name=extracted.get("customer_name", ""),
            )
        except Exception as e:
            if extracted.get("extraction_notes") is None:
                extracted["extraction_notes"] = []
            extracted["extraction_notes"].append(f"Customer matching error: {str(e)}")

    # ── Save or Update AI Order Intake record ──────────────────────────────
    if existing and existing.status == "Failed":
        intake = frappe.get_doc("AI Order Intake", existing.name)
        intake.status = status
        intake.extracted_json = json.dumps(extracted, ensure_ascii=False, indent=2) if extracted else None
        intake.matched_customer = match_result.get("customer")
        intake.match_confidence = match_result.get("confidence", 0.0)
        intake.match_method = match_result.get("method", "None")
        intake.error_message = error_msg
        intake.save(ignore_permissions=True)
    else:
        intake = frappe.get_doc({
            "doctype": "AI Order Intake",
            "raw_text": raw_text,
            "input_hash": input_hash,
            "status": status,
            "extracted_json": json.dumps(extracted, ensure_ascii=False, indent=2) if extracted else None,
            "matched_customer": match_result.get("customer"),
            "match_confidence": match_result.get("confidence", 0.0),
            "match_method": match_result.get("method", "None"),
            "error_message": error_msg,
        })
        intake.insert(ignore_permissions=True)

    frappe.db.commit()

    if status == "Failed":
        return {
            "status": "Failed",
            "intake_name": intake.name,
            "error_message": error_msg,
        }

    return _intake_to_response(intake, extracted=extracted)


def _intake_to_response(intake_doc, extracted=None) -> dict:
    """Serialize an AI Order Intake doc for the frontend review screen."""
    if extracted is None and intake_doc.extracted_json:
        try:
            extracted = json.loads(intake_doc.extracted_json)
        except Exception:
            extracted = {}

    # Include the live item catalog so the frontend can do client-side validation
    catalog = get_item_catalog()

    return {
        "duplicate": False,
        "intake_name": intake_doc.name,
        "status": intake_doc.status,
        "error_message": intake_doc.error_message,
        "extracted": extracted or {},
        "match": {
            "customer": intake_doc.matched_customer,
            "confidence": intake_doc.match_confidence,
            "method": intake_doc.match_method,
        },
        "created_customer": intake_doc.created_customer,
        "created_sales_order": intake_doc.created_sales_order,
        "item_catalog": catalog,
    }


# ---------------------------------------------------------------------------
# Endpoint 2: confirm_intake
# ---------------------------------------------------------------------------

@frappe.whitelist()
def confirm_intake(intake_name: str, reviewed_data: str) -> dict:
    """
    Step 2 of the AI intake flow — called ONLY after human review.
    """
    intake = frappe.get_doc("AI Order Intake", intake_name)
    if intake.status == "Confirmed":
        frappe.throw(f"This intake ({intake_name}) is already confirmed.")
    if intake.status == "Failed" and not frappe.conf.get("allow_retry_failed_intake"):
        frappe.throw(
            "This intake failed during extraction. "
            "Please start a new intake with the corrected text."
        )

    data = json.loads(reviewed_data) if isinstance(reviewed_data, str) else reviewed_data

    items = data.get("order_items", [])
    if not items:
        frappe.throw("Cannot confirm: the order must have at least one item.")

    created_customer_name = None
    customer_docname = None

    # ── Customer: create or use existing ──────────────────────────────────
    if data.get("customer_choice") == "new":
        customer_name_str = data.get("customer_name", "").strip()
        if not customer_name_str:
            frappe.throw("Cannot create a new customer without a name.")

        existing_by_name = frappe.db.get_value(
            "Customer", {"customer_name": customer_name_str}, "name"
        )
        if existing_by_name:
            frappe.throw(
                f"A customer named '{customer_name_str}' already exists ({existing_by_name}). "
                "Switch to 'Use existing customer' or use a different name."
            )

        cust = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": customer_name_str,
            "customer_type": "Individual",
            "main_phone_number": data.get("main_phone_number"),
            "secondary_phone_number": data.get("secondary_phone_number"),
            "username": data.get("username") or "",
            "governorate": data.get("governorate") or "",
            "full_address": data.get("full_address") or "",
        })
        cust.insert(ignore_permissions=True)
        customer_docname = cust.name
        created_customer_name = cust.name
    else:
        customer_docname = data.get("customer_name") or intake.matched_customer
        if not customer_docname:
            frappe.throw("No customer selected. Please choose an existing customer or create a new one.")
        if not frappe.db.exists("Customer", customer_docname):
            frappe.throw(f"Customer '{customer_docname}' not found.")

    # ── Build Sales Order items ────────────────────────────────────────────
    default_warehouse, default_uom = _get_default_so_items_params()

    so_items = []
    for item in items:
        item_code = item.get("item_code", "").strip()
        if not item_code:
            frappe.throw(
                f"Item code is required for all items. Missing for: {item.get('description')}"
            )
        if not frappe.db.exists("Item", item_code):
            frappe.throw(
                f"Item '{item_code}' does not exist in the item master. "
                "Please correct the item code in the review screen."
            )
        so_items.append({
            "item_code": item_code,
            "item_name": item.get("item_name") or item_code,
            "description": item.get("description") or item_code,
            "qty": float(item.get("qty") or 1),
            "rate": float(item.get("rate") or item.get("unit_price") or 0),
            "uom": default_uom,
            "warehouse": default_warehouse,
            "additional_notes": item.get("notes") or "",
        })

    # ── Create Sales Order ─────────────────────────────────────────────────
    so = frappe.get_doc({
        "doctype": "Sales Order",
        "customer": customer_docname,
        "transaction_date": today(),
        "delivery_date": data.get("delivery_date") or today(),
        "currency": data.get("currency") or "IQD",
        "gift": 1 if data.get("gift") else 0,
        "priority": data.get("priority") or "",
        "governorate_of_delivery": data.get("governorate_of_delivery") or "",
        "order_type": "Sales",
        "items": so_items,
    })
    so.insert(ignore_permissions=True)

    # ── Update AI Order Intake ─────────────────────────────────────────────
    frappe.db.set_value("AI Order Intake", intake_name, {
        "status": "Confirmed",
        "created_customer": created_customer_name,
        "created_sales_order": so.name,
    })
    frappe.db.commit()

    return {
        "success": True,
        "sales_order": so.name,
        "customer": customer_docname,
        "created_new_customer": created_customer_name is not None,
    }


# ---------------------------------------------------------------------------
# Endpoint 3: get_item_catalog
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_item_catalog_endpoint() -> list:
    """Return available items for the frontend autocomplete."""
    return get_item_catalog()


# ---------------------------------------------------------------------------
# Endpoint 4: get_customers_for_search
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_customers_for_search(query: str) -> list:
    """Live search for customers by name — used in the review screen."""
    return frappe.get_all(
        "Customer",
        filters=[["customer_name", "like", f"%{query}%"]],
        fields=["name", "customer_name", "main_phone_number"],
        limit=10,
    )
