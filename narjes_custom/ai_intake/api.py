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
from narjes_custom.ai_intake import settings as ai_settings
from narjes_custom.ai_intake.matching import match_customer
from narjes_custom.business_logic import is_discount_excessive
from narjes_custom.setup import flower_placeholder

# Fallback for the discount guardrail, used only when AI Intake Settings
# can't be read. A discount above this percentage of the order subtotal
# blocks confirm_intake outright rather than trusting the (AI-extracted,
# human-reviewed-but-not-guaranteed-reviewed) discount_amount value — see
# the sanity check in confirm_intake() and NARJES_STORE_SYSTEM.md §8.4/§15.
MAX_DISCOUNT_PERCENTAGE = 50


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _hash_text(raw_text: str) -> str:
    """SHA-256 of normalized text (stripped, lowercased) for idempotency."""
    normalized = " ".join(raw_text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _usable_warehouse(name):
    """True if `name` is a warehouse orders may actually be fulfilled from.

    Transit warehouses are excluded. "Goods In Transit" is a staging area for
    stock moving between branches — it is never where sellable stock lives, so
    an order pointing at it is guaranteed to fail at submit with "Insufficient
    Stock" no matter how much stock the shop actually holds.
    """
    if not name:
        return False
    row = frappe.db.get_value(
        "Warehouse", name, ["is_group", "disabled", "warehouse_type"], as_dict=True
    )
    return bool(row) and not row.is_group and not row.disabled and row.warehouse_type != "Transit"


def _get_default_so_items_params(settings=None):
    """
    Warehouse and UOM for Sales Order lines built from an intake.

    The warehouse is resolved in a fixed order of preference, and every
    candidate is checked with `_usable_warehouse` before it is accepted:

        1. AI Intake Settings.default_warehouse — the explicit choice.
        2. Stock Settings.default_warehouse — what the rest of ERPNext uses.
        3. The alphabetically first non-group, non-transit warehouse.

    Step 3 used to be `get_all(..., limit=1)` with no `order_by`, which meant
    Frappe's default of `modified desc` — so the warehouse an order was
    assigned to was whichever warehouse someone had edited most recently, and
    it silently CHANGED as staff touched warehouse records. That is how orders
    ended up demanding stock from "Goods In Transit": moving stock around to
    satisfy the previous error re-ordered the table and moved the target.
    Ordering by name makes the fallback stable and repeatable; excluding
    transit makes it correct.
    """
    default_warehouse = ai_settings.get_setting("default_warehouse", settings)

    if not _usable_warehouse(default_warehouse):
        default_warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")

    if not _usable_warehouse(default_warehouse):
        candidates = frappe.get_all(
            "Warehouse",
            filters={"is_group": 0, "disabled": 0, "warehouse_type": ("!=", "Transit")},
            pluck="name",
            order_by="name asc",
            limit=1,
        )
        default_warehouse = candidates[0] if candidates else None

    default_uom = ai_settings.get_str("default_uom", settings) or "Nos"
    return default_warehouse, default_uom


# The channel values Customer.channal accepts, keyed by what people actually
# write on the order line. The AI is constrained to the canonical values by
# the response schema; this catches anything typed by hand on the review screen.
_CHANNEL_ALIASES = {
    "insta": "Instagram", "instagram": "Instagram", "انستا": "Instagram", "أنستا": "Instagram",
    "face": "Facebook", "facebook": "Facebook", "فيسبوك": "Facebook", "فيس": "Facebook",
    "whatsapp": "Whatsapp", "whats": "Whatsapp", "واتساب": "Whatsapp", "واتس": "Whatsapp",
    "telegram": "Telegram", "تلكرام": "Telegram", "تليجرام": "Telegram",
    "tiktok": "TikTok", "tik tok": "TikTok", "تيك توك": "TikTok", "تيكتوك": "TikTok",
    "website": "Website", "site": "Website", "الموقع": "Website",
}


def _normalize_channel(raw) -> str:
    """Map a free-text platform onto a valid Customer.channal option.

    Returns "" when it doesn't resolve — an invalid Select value would make
    the Customer insert fail, and losing the channel is much cheaper than
    losing the whole order.
    """
    if not raw:
        return ""
    value = str(raw).strip()
    if not value:
        return ""

    try:
        options = frappe.get_meta("Customer").get_field("channal").options or ""
        valid = [o.strip() for o in options.split("\n") if o.strip()]
    except Exception:
        return ""

    for option in valid:
        if value.lower() == option.lower():
            return option

    mapped = _CHANNEL_ALIASES.get(value.lower())
    return mapped if mapped in valid else ""


def get_catalog_with_prices() -> list:
    """The item catalog plus each item's selling price, for the review screen.

    The prompt catalog deliberately carries no prices — showing them to the
    model invites it to price the order, which is the shop's decision. The
    reviewer does need them, so they are attached here instead, and the price
    box on each row is pre-filled from this rather than from the extraction.
    """
    catalog = get_item_catalog()
    price_list = (
        frappe.db.get_single_value("Selling Settings", "selling_price_list")
        or "Standard Selling"
    )
    prices = dict(
        frappe.get_all(
            "Item Price",
            filters={"price_list": price_list, "selling": 1},
            fields=["item_code", "price_list_rate"],
            as_list=True,
        )
    )
    for item in catalog:
        item["standard_rate"] = float(prices.get(item["name"]) or 0)
    return catalog


def _default_selling_rate(item_code: str) -> float:
    """The item's own selling price, used when intake supplies no rate.

    Prices are the shop's decision, not the AI's — the model is told to leave
    unit_price at 0 and let the catalog answer. Reading the rate here rather
    than leaving it unset keeps the discount guardrail meaningful, since that
    check runs on this subtotal before the Sales Order exists.
    """
    price_list = (
        frappe.db.get_single_value("Selling Settings", "selling_price_list")
        or "Standard Selling"
    )
    rate = frappe.db.get_value(
        "Item Price",
        {"item_code": item_code, "price_list": price_list, "selling": 1},
        "price_list_rate",
    )
    return float(rate or 0)


# ---------------------------------------------------------------------------
# Endpoint 1: process_intake
# ---------------------------------------------------------------------------

def _require_intake_permission():
	"""AI intake is order-entry, so it demands the same rights as order-entry.

	`@frappe.whitelist()` only proves the caller is signed in — it says nothing
	about what they may do. Without this, any account that can log in could
	call confirm_intake() and submit a Sales Order, and submitting one runs
	automate_so_flow(): a Delivery Note, a Sales Invoice, a Payment Entry and
	several Journal Entries, all posted to the general ledger. That is write
	access to the company's books from an unprivileged session.

	process_intake() is gated too, for a different reason: every call spends
	real money at Gemini, so leaving it open is an invitation to run up the
	bill.
	"""
	frappe.has_permission("Sales Order", ptype="create", throw=True)


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
    _require_intake_permission()

    if not ai_settings.is_enabled():
        frappe.throw(
            "AI Order Intake is turned off. A System Manager can re-enable it "
            "in AI Intake Settings. Orders already in the queue can still be reviewed."
        )

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

    # Include the live item catalog so the frontend can do client-side
    # validation and pre-fill each row's price from the shop's own price list
    catalog = get_catalog_with_prices()

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
    _require_intake_permission()

    settings = ai_settings.get_settings()

    intake = frappe.get_doc("AI Order Intake", intake_name)
    if intake.status == "Confirmed":
        frappe.throw(f"This intake ({intake_name}) is already confirmed.")

    # site_config still wins if set, so an existing deployment that relied on
    # it keeps working; otherwise the AI Intake Settings checkbox decides.
    allow_retry = frappe.conf.get("allow_retry_failed_intake") or ai_settings.get_bool(
        "allow_retry_failed_intake", settings
    )
    if intake.status == "Failed" and not allow_retry:
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
            # Automatically use the existing customer
            customer_docname = existing_by_name
            frappe.msgprint(f"Customer '{customer_name_str}' already exists. Automatically linking to the existing record instead of creating a new one.")
        else:
            # Normalize governorate
            gov = data.get("governorate") or ""
            if gov:
                try:
                    meta = frappe.get_meta("Customer")
                    gov_field = meta.get_field("governorate")
                    if gov_field and gov_field.options:
                        valid_options = [opt for opt in gov_field.options.split("\n") if opt.strip()]
                        if gov not in valid_options:
                            gov_normalized = gov.replace("ال", "").strip()
                            for opt in valid_options:
                                if opt.replace("ال", "").strip() == gov_normalized:
                                    gov = opt
                                    break
                except Exception:
                    pass

            cust = frappe.get_doc({
                "doctype": "Customer",
                "customer_name": customer_name_str,
                "customer_type": "Individual",
                "main_phone_number": data.get("main_phone_number"),
                "secondary_phone_number": data.get("secondary_phone_number"),
                "username": data.get("username") or "",
                "governorate": gov,
                "full_address": data.get("full_address") or "",
                # Where this customer came to us from, taken off the order's
                # "منصة الطلب" line — only ever set on a customer we create,
                # never overwriting the channel on an existing record
                "channal": _normalize_channel(data.get("platform")),
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
    default_warehouse, default_uom = _get_default_so_items_params(settings)

    so_items = []
    flower_items = []
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
            
        qty = float(item.get("qty") or 1)
        # Intake deliberately does not price anything: the AI leaves unit_price
        # at 0 and the reviewer only overrides when this order is genuinely
        # priced differently. A 0 here means "use the catalog price", not "free".
        rate = float(item.get("rate") or item.get("unit_price") or 0)
        if not rate:
            rate = _default_selling_rate(item_code)

        is_flower = frappe.db.get_value("Item", item_code, "custom_is_flower")
        
        if is_flower:
            flower_items.append({
                # The Flower Item child doctype's Link field is `flower_item`,
                # not `item_code`. Writing item_code left the mandatory link
                # empty, so every intake containing a flower died on insert
                # with "Flower Item Row #1: Value missing for: Item".
                "flower_item": item_code,
                "qty": qty,
                "rate": rate,
                "amount": qty * rate,
                "delivery_date": data.get("delivery_date") or today()
            })
        else:
            so_items.append({
                "item_code": item_code,
                "item_name": item.get("item_name") or item_code,
                "description": item.get("description") or item_code,
                "qty": qty,
                "rate": rate,
                "uom": default_uom,
                "warehouse": default_warehouse,
                "additional_notes": item.get("notes") or "",
            })

    # An order that is nothing but flowers still needs a row in `items`:
    # ERPNext marks Sales Order.items mandatory, and an empty table does not
    # even fail cleanly — it crashes inside the totals calculation.
    #
    # Flowers stay where they belong. custom_flower_items is the only place a
    # flower is ever recorded, so `items` gets a single zero-value placeholder
    # line instead (see narjes_custom.setup.flower_placeholder for why it has
    # to be a priceless item of its own rather than the flower at rate 0).
    #
    # Net effect: net_total 0, flowers billed exactly once through the
    # "Flower Items" charge row, grand total as quoted.
    if not so_items and flower_items:
        so_items.append({
            "item_code": flower_placeholder.ensure(),
            "qty": 1,
            "rate": 0,
            "price_list_rate": 0,
            # belt and braces: rate 0, price 0, and explicitly not chargeable,
            # so the line cannot start billing if an Item Price ever appears
            "is_free_item": 1,
            "uom": default_uom,
            "warehouse": default_warehouse,
            "delivery_date": data.get("delivery_date") or today(),
        })

    # ── Discount sanity check ───────────────────────────────────────────────
    # discount_amount and every item's rate come straight from AI-extracted
    # customer-supplied free text with no server-side bound. A human is
    # expected to review it on the review screen, but that's not a
    # guarantee — a crafted or garbled message could push an unreasonable
    # discount through unnoticed. This is a coarse backstop, not a
    # replacement for review: it blocks the exceptional case rather than
    # trying to validate every number (see NARJES_STORE_SYSTEM.md §8.4).
    max_discount_percentage = ai_settings.get_float("max_discount_percentage", settings)
    discount_amount = float(data.get("discount_amount") or 0)
    order_subtotal = sum((item.get("qty") or 0) * (item.get("rate") or 0) for item in so_items)
    order_subtotal += sum((f.get("qty") or 0) * (f.get("rate") or 0) for f in flower_items)
    if is_discount_excessive(discount_amount, order_subtotal, max_discount_percentage):
        frappe.throw(
            f"The discount ({discount_amount:,.0f}) is more than {max_discount_percentage:g}% of the "
            f"order subtotal ({order_subtotal:,.0f}). Please double-check it on the review screen — "
            f"if it's genuinely correct, create/adjust this Sales Order manually instead of through AI intake."
        )

    # ── Create Sales Order ─────────────────────────────────────────────────
    so = frappe.get_doc({
        "doctype": "Sales Order",
        "customer": customer_docname,
        "transaction_date": today(),
        "delivery_date": data.get("delivery_date") or today(),
        "currency": data.get("currency") or ai_settings.get_str("default_currency", settings),
        "gift": 1 if data.get("gift") else 0,
        "priority": data.get("priority") or "",
        "custom_details": data.get("custom_details") or "",
        "discount_amount": float(data.get("discount_amount") or 0),
        "additional_discount_percentage": 0,
        "governorate_of_delivery": data.get("governorate_of_delivery") or "",
        "order_type": "Sales",
        "items": so_items,
        "custom_flower_items": flower_items,
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
    """Return available items, with prices, for the frontend autocomplete."""
    # Selling prices for the whole catalogue in one response — the same reason
    # get_customers_for_search() checks before answering.
    frappe.has_permission("Item", ptype="read", throw=True)
    return get_catalog_with_prices()


# ---------------------------------------------------------------------------
# Endpoint 4: get_customers_for_search
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_customers_for_search(query: str) -> list:
    """Live search for customers by name — used in the review screen."""
    frappe.has_permission("Customer", ptype="read", throw=True)
    return frappe.get_all(
        "Customer",
        filters=[["customer_name", "like", f"%{query}%"]],
        fields=["name", "customer_name", "main_phone_number"],
        limit=10,
    )
