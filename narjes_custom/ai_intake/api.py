"""
narjes_custom.ai_intake.api
=============================
Whitelisted Frappe API endpoints for AI Order Intake.

  1. process_intake()   — reads the order form (no AI) for the phone, asks
                          Gemini for the rest, resolves the customer by phone,
                          and returns a record for review
  2. lookup_phones()    — re-resolves when the reviewer changes the phones
  3. confirm_intake()   — re-checks everything on the server and writes the
                          Customer (if new) and the Sales Order
  4. discard_intake()   — clears an intake nobody will confirm
  5. get_item_catalog_endpoint() — items + prices for the review screen

The customer is decided by phone number only. A Sales Order is never created
for a customer who does not own, as a stored main or secondary phone, at least
one of the phones the order is confirmed with.
"""

import hashlib
import json

import frappe
from frappe.utils import cint, now_datetime, today

from narjes_custom import customer_phones
from narjes_custom.ai_intake import settings as ai_settings
from narjes_custom.ai_intake import template
from narjes_custom.ai_intake.extraction import (
    ExtractionError,
    extract_order_with_meta,
    get_item_catalog,
)
from narjes_custom.business_logic import is_discount_excessive
from narjes_custom.phones import canonical, display, national
from narjes_custom.setup import flower_placeholder

# Longest order text accepted; real ones are ~500 characters.
MAX_TEXT_LENGTH = 20000

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
    "insta": "Instagram", "instagram": "Instagram", "instgram": "Instagram", "انستا": "Instagram", "أنستا": "Instagram",
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
# Shared pieces
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


def _normalize_governorate(gov) -> str:
    """Map a governorate onto a valid Customer.governorate option, or ""."""
    gov = (gov or "").strip()
    if not gov:
        return ""
    try:
        field = frappe.get_meta("Customer").get_field("governorate")
        valid = [opt for opt in (field.options or "").split("\n") if opt.strip()] if field else []
    except Exception:
        return gov
    if gov in valid:
        return gov
    bare = gov.replace("ال", "").strip()
    return next((opt for opt in valid if opt.replace("ال", "").strip() == bare), "")


def _phone_entries(keys, methods=None, owners=None) -> list:
    methods = methods or {}
    owners = owners or {}
    return [
        {"e164": key, "display": display(key), "method": methods.get(key, ""), "owners": owners.get(key, [])}
        for key in keys
    ]


def _resolution_payload(resolution) -> dict:
    """The resolution plus what the reviewer needs to see about each customer."""
    payload = {
        "status": resolution["status"],
        "customer": resolution["customer"],
        "candidates": [customer_phones.customer_summary(name) for name in resolution["candidates"]],
        "disabled": resolution["disabled"],
        "token": resolution["token"],
    }
    payload["customer_preview"] = (
        customer_phones.customer_summary(resolution["customer"]) if resolution["customer"] else None
    )
    return payload


def _load_json(value, default):
    try:
        return json.loads(value) if value else default
    except (TypeError, ValueError):
        return default


def _notes(form, extracted, problems) -> dict:
    """Everything the reviewer should read before confirming, grouped."""
    notes = {"phone": [], "diff": [], "ai": [], "template": list(form.notes)}
    for raw in problems:
        notes["phone"].append(f"Could not read '{raw}' as a phone number. Check the message and type the right number.")
    if not form.phones and not problems:
        notes["phone"].append("The order has no phone number. Type the customer's phone to continue.")
    if form.phone_source == "free_text" and form.phones:
        notes["phone"].append("The phone was not in the order form's 📞 field. Confirm it is the customer's before continuing.")

    if extracted:
        ai_keys = [k for k in (canonical(p) for p in (extracted.get("phone_numbers") or [])) if k]
        for key in ai_keys:
            if key not in form.phone_keys:
                notes["diff"].append(f"The AI read {display(key)}, which is not in the 📞 field. It was ignored.")
        for raw in extracted.get("phone_numbers") or []:
            if raw and not canonical(raw):
                notes["diff"].append(f"The AI produced '{raw}', which is not a valid phone number. It was ignored.")
        notes["ai"] = [str(n) for n in (extracted.get("extraction_notes") or [])]
    return notes


def _prefill(form, extracted) -> dict:
    """New-customer fields: the order form first, the AI's reading second."""
    extracted = extracted or {}
    return {
        "customer_name": form.name or (extracted.get("customer_name") or "").strip(),
        "username": form.username or (extracted.get("username") or "").strip().lstrip("@"),
        "platform": _normalize_channel(form.platform) or _normalize_channel(extracted.get("platform")),
        "governorate": _normalize_governorate(extracted.get("governorate")),
        "full_address": form.address or (extracted.get("address") or "").strip(),
    }


def _form_snapshot(form) -> dict:
    return {
        "version": form.version,
        "name": form.name,
        "username": form.username,
        "platform": form.platform,
        "address": form.address,
        "amounts": form.amounts,
        "assumed_thousands": form.assumed_thousands,
        "gift_hint": form.gift_hint,
        "notes": form.notes,
        "fields": form.fields,
    }


# ---------------------------------------------------------------------------
# Endpoint 1: process_intake
# ---------------------------------------------------------------------------

@frappe.whitelist()
def process_intake(raw_text: str, force_new: int = 0) -> dict:
    """
    Step 1 of the AI intake flow. Never creates a Customer or a Sales Order.

    - The same text again returns the record already made from it, unless
      the reviewer asked to process it as a new order (`force_new`).
    - The customer's phone is read from the order form without AI; Gemini
      reads the rest. The AI's phones are only compared with the form's.
    - The customer is resolved by phone (MATCHED / NEW / CONFLICT / NO_PHONE).
    """
    _require_intake_permission()

    if not ai_settings.is_enabled():
        frappe.throw(
            "AI Order Intake is turned off. A System Manager can re-enable it "
            "in AI Intake Settings. Orders already in the queue can still be reviewed."
        )

    if not raw_text or not raw_text.strip():
        frappe.throw("Please paste the order text before processing.")
    if len(raw_text) > MAX_TEXT_LENGTH:
        frappe.throw(f"The order text is too long ({len(raw_text):,} characters). Paste one order at a time.")

    base_hash = _hash_text(raw_text)
    input_hash = base_hash
    reuse = None
    existing = frappe.db.get_value(
        "AI Order Intake", {"input_hash": base_hash}, ["name", "status", "created_sales_order"], as_dict=True
    )
    if cint(force_new):
        input_hash = f"{base_hash}#{frappe.generate_hash(length=8)}"
    elif existing:
        if existing.status == "Confirmed" or existing.created_sales_order:
            return {
                "duplicate": True,
                "can_force_new": True,
                "intake_name": existing.name,
                "created_sales_order": existing.created_sales_order,
                "message": (
                    "This exact order text was already processed. "
                    f"Sales Order {existing.created_sales_order} was created from it."
                ),
            }
        if existing.status in ("Draft", "Needs Review"):
            return _intake_to_response(frappe.get_doc("AI Order Intake", existing.name))
        if existing.status == "Failed":
            reuse = existing.name
        else:  # Discarded: it stays discarded; this becomes a new record
            input_hash = f"{base_hash}#{frappe.generate_hash(length=8)}"

    # ── The order form, read without AI ────────────────────────────────────
    form = template.parse(raw_text)

    # ── Gemini for the rest ─────────────────────────────────────────────────
    extracted, meta, error = None, {}, None
    try:
        extracted, meta = extract_order_with_meta(raw_text)
    except ExtractionError as e:
        error = str(e)
    except Exception as e:
        error = f"Unexpected error during extraction: {e!s}"
        frappe.log_error(title="AI intake: extraction crashed", message=frappe.get_traceback())

    # ── Customer, by phone only ─────────────────────────────────────────────
    resolution = customer_phones.resolve(form.phone_keys)
    methods = {hit.e164: hit.method for hit in form.phones}

    values = {
        "raw_text": raw_text,
        "input_hash": input_hash,
        "status": "Needs Review" if extracted is not None else "Failed",
        "error_message": error,
        "extracted_json": json.dumps(extracted, ensure_ascii=False, indent=2) if extracted is not None else None,
        "phone_source": form.phone_source,
        "detected_phones": json.dumps(_phone_entries(form.phone_keys, methods), ensure_ascii=False),
        "phone_problems": "\n".join(form.phone_problems),
        "match_status": resolution["status"],
        "matched_customer": resolution["customer"],
        "match_method": "Phone" if resolution["status"] == "MATCHED" else "None",
        "match_confidence": 100.0 if resolution["status"] == "MATCHED" else 0.0,
        "match_candidates": json.dumps(resolution["candidates"], ensure_ascii=False),
        "resolution_token": resolution["token"],
        "template_version": form.version or "",
        "template_fields": json.dumps(_form_snapshot(form), ensure_ascii=False, indent=2),
        "ai_model": meta.get("model"),
        "ai_latency_ms": meta.get("latency_ms"),
        "ai_attempts": meta.get("attempts"),
        "ai_finish_reason": meta.get("finish_reason"),
        "ai_prompt_tokens": meta.get("prompt_tokens"),
        "ai_cached_tokens": meta.get("cached_tokens"),
        "ai_output_tokens": meta.get("output_tokens"),
        "ai_thinking_tokens": meta.get("thinking_tokens"),
    }

    if reuse:
        intake = frappe.get_doc("AI Order Intake", reuse)
        intake.update(values)
        intake.save(ignore_permissions=True)
    else:
        intake = frappe.get_doc({"doctype": "AI Order Intake", **values})
        intake.insert(ignore_permissions=True)
    frappe.db.commit()

    if extracted is None:
        return {"status": "Failed", "intake_name": intake.name, "error_message": error}
    return _intake_to_response(intake, form=form, extracted=extracted, resolution=resolution)


def _intake_to_response(intake, form=None, extracted=None, resolution=None) -> dict:
    """The review payload. The resolution is always current: a stored intake
    is re-resolved, because customers may have changed since it was made."""
    form = form or template.parse(intake.raw_text or "")
    if extracted is None:
        extracted = _load_json(intake.extracted_json, {})
    detected = _load_json(intake.detected_phones, [])
    keys = [p.get("e164") for p in detected if p.get("e164")]
    if resolution is None:
        resolution = customer_phones.resolve(keys)
    methods = {p.get("e164"): p.get("method") for p in detected}

    # Catalog with the shop's own prices, for the item rows
    catalog = get_catalog_with_prices()

    return {
        "duplicate": False,
        "intake_name": intake.name,
        "status": intake.status,
        "error_message": intake.error_message,
        "phone_source": intake.phone_source or form.phone_source,
        "phones": _phone_entries(keys, methods, resolution["owners"]),
        "phone_problems": [p for p in (intake.phone_problems or "").split("\n") if p],
        "phone_section": form.phone_section or "",
        "resolution": _resolution_payload(resolution),
        "prefill": _prefill(form, extracted),
        "extracted": extracted or {},
        "amounts": {**form.amounts, "assumed_thousands": form.assumed_thousands},
        "gift_hint": form.gift_hint,
        "notes": _notes(form, extracted, form.phone_problems),
        "item_catalog": catalog,
        "ai": {
            "model": intake.ai_model,
            "latency_ms": intake.ai_latency_ms,
            "attempts": intake.ai_attempts,
            "finish_reason": intake.ai_finish_reason,
        },
    }


# ---------------------------------------------------------------------------
# Endpoint 2: lookup_phones
# ---------------------------------------------------------------------------

@frappe.whitelist()
def lookup_phones(intake_name: str, phones: str) -> dict:
    """Who owns these phones right now (the reviewer changed the phones). Read-only."""
    _require_intake_permission()
    if not frappe.db.exists("AI Order Intake", intake_name):
        frappe.throw(f"AI Order Intake {intake_name} not found.")
    raw_list = _load_json(phones, []) if isinstance(phones, str) else (phones or [])
    keys, invalid = [], []
    for raw in raw_list:
        key = canonical(raw)
        if key:
            if key not in keys:
                keys.append(key)
        elif str(raw or "").strip():
            invalid.append(str(raw))
    resolution = customer_phones.resolve(keys)
    return {
        "ok": not invalid,
        "invalid": invalid,
        "phones": _phone_entries(keys, owners=resolution["owners"]),
        "resolution": _resolution_payload(resolution),
    }


# ---------------------------------------------------------------------------
# Endpoint 3: confirm_intake
# ---------------------------------------------------------------------------

CUSTOMER_MODES = ("matched", "pick", "new", "add_phone_to_existing")


def _identity_phones(intake, data) -> tuple:
    """(keys, phone_source) the order is confirmed with, after the rules:

    - phones from the message may be kept or dropped, never edited;
    - a phone the message does not contain is accepted only when the message
      had none, or with an explicit override reason;
    - a phone found outside the order form must be confirmed by the reviewer.
    """
    detected = [p.get("e164") for p in _load_json(intake.detected_phones, []) if p.get("e164")]
    keys = []
    for raw in data.get("phones") or []:
        key = canonical(raw)
        if not key:
            frappe.throw(f"'{raw}' is not a valid phone number.")
        if key not in keys:
            keys.append(key)
    if not keys:
        frappe.throw("A customer phone number is required to confirm the order.")

    typed = [k for k in keys if k not in detected]
    override = (data.get("override_reason") or "").strip()
    if typed and detected and not override:
        frappe.throw(
            f"{display(typed[0])} is not in the order message. Use the message's phone, or say why it is wrong."
        )
    if typed:
        return keys, "reviewer"
    if intake.phone_source == "free_text" and not data.get("phones_confirmed"):
        frappe.throw("Confirm that the phone found in the message is the customer's.")
    return keys, intake.phone_source or "template"


def _add_phones(customer_name, keys) -> list:
    """Put each phone into a free slot of the customer; the Customer hook re-checks ownership."""
    if not keys:
        return []
    customer = frappe.get_doc("Customer", customer_name)
    for key in keys:
        if not customer.main_phone_number:
            customer.main_phone_number = national(key)
        elif not customer.secondary_phone_number:
            customer.secondary_phone_number = national(key)
        else:
            frappe.throw(
                f"{customer.customer_name} already has two phone numbers. Change one on the customer first."
            )
    customer.save(ignore_permissions=True)
    return [display(k) for k in keys]


def _create_customer(new_customer, keys) -> str:
    name = (new_customer.get("customer_name") or "").strip()
    if not name:
        frappe.throw("Cannot create a new customer without a name.")
    if len(keys) > 2:
        frappe.throw("A customer can hold two phone numbers. Keep at most two for this order.")
    customer = frappe.get_doc({
        "doctype": "Customer",
        "customer_name": name,
        "customer_type": "Individual",
        "main_phone_number": national(keys[0]),
        "secondary_phone_number": national(keys[1]) if len(keys) > 1 else "",
        "username": (new_customer.get("username") or "").strip().lstrip("@"),
        "governorate": _normalize_governorate(new_customer.get("governorate")),
        "full_address": (new_customer.get("full_address") or "").strip(),
        # Where this customer came to us from — only ever set on a customer we
        # create, never overwriting the channel on an existing record
        "channal": _normalize_channel(new_customer.get("platform")),
    })
    customer.insert(ignore_permissions=True)
    return customer.name


def _build_sales_order(customer_name, order, settings):
    """The Sales Order for a confirmed intake (not yet inserted)."""
    items = order.get("order_items") or []
    if not items:
        frappe.throw("Cannot confirm: the order must have at least one item.")

    default_warehouse, default_uom = _get_default_so_items_params(settings)

    so_items = []
    flower_items = []
    for item in items:
        item_code = (item.get("item_code") or "").strip()
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
                "delivery_date": order.get("delivery_date") or today()
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
            "delivery_date": order.get("delivery_date") or today(),
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
    discount_amount = float(order.get("discount_amount") or 0)
    order_subtotal = sum((item.get("qty") or 0) * (item.get("rate") or 0) for item in so_items)
    order_subtotal += sum((f.get("qty") or 0) * (f.get("rate") or 0) for f in flower_items)
    if is_discount_excessive(discount_amount, order_subtotal, max_discount_percentage):
        frappe.throw(
            f"The discount ({discount_amount:,.0f}) is more than {max_discount_percentage:g}% of the "
            f"order subtotal ({order_subtotal:,.0f}). Please double-check it on the review screen — "
            f"if it's genuinely correct, create/adjust this Sales Order manually instead of through AI intake."
        )

    return frappe.get_doc({
        "doctype": "Sales Order",
        "customer": customer_name,
        "transaction_date": today(),
        "delivery_date": order.get("delivery_date") or today(),
        "currency": order.get("currency") or ai_settings.get_str("default_currency", settings),
        "gift": 1 if order.get("gift") else 0,
        "priority": order.get("priority") or "",
        "custom_details": order.get("custom_details") or "",
        "discount_amount": discount_amount,
        "additional_discount_percentage": 0,
        "governorate_of_delivery": order.get("governorate_of_delivery") or "",
        "order_type": "Sales",
        "items": so_items,
        "custom_flower_items": flower_items,
    })


@frappe.whitelist()
def confirm_intake(intake_name: str, reviewed_data: str) -> dict:
    """
    Step 2 — called only after a person reviewed the order.

    Everything the review screen showed is re-checked here, under a lock per
    phone number: the phones, who owns them (the resolution token must still
    match), and that the chosen customer really owns one of them. Expected
    outcomes (already confirmed, customers changed meanwhile) are returned;
    invalid input is refused with a clear message.
    """
    _require_intake_permission()
    settings = ai_settings.get_settings()
    data = json.loads(reviewed_data) if isinstance(reviewed_data, str) else (reviewed_data or {})

    # One confirm at a time per intake
    frappe.db.sql("SELECT name FROM `tabAI Order Intake` WHERE name = %s FOR UPDATE", (intake_name,))
    intake = frappe.get_doc("AI Order Intake", intake_name)
    if intake.status == "Confirmed":
        return {"ok": False, "reason": "already_confirmed", "sales_order": intake.created_sales_order}
    if intake.status == "Discarded":
        frappe.throw("This intake was discarded. Paste the order text again to process it.")
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

    mode = data.get("customer_mode")
    if mode not in CUSTOMER_MODES:
        frappe.throw("Choose how the customer is decided before confirming.")

    keys, phone_source = _identity_phones(intake, data)
    old_key = canonical(data.get("old_phone")) if mode == "add_phone_to_existing" else None
    customer_phones.lock_phones(keys + ([old_key] if old_key else []))

    resolution = customer_phones.resolve(keys)
    if resolution["token"] != data.get("resolution_token"):
        return {"ok": False, "reason": "resolution_changed", "resolution": _resolution_payload(resolution)}

    chosen = (data.get("customer") or "").strip()
    created_customer = None
    added = []

    if mode == "matched":
        if resolution["status"] != "MATCHED" or chosen != resolution["customer"]:
            frappe.throw("These phones don't belong to that customer.")
        extra = [canonical(p) for p in (data.get("add_phones_to_customer") or [])]
        extra = [k for k in extra if k in keys and not resolution["owners"].get(k)]
        customer = chosen
    elif mode == "pick":
        if resolution["status"] != "CONFLICT" or chosen not in resolution["candidates"]:
            frappe.throw("Pick one of the customers that own these phones.")
        extra = []
        customer = chosen
    elif mode == "new":
        if resolution["status"] != "NEW":
            frappe.throw("One of these phones already belongs to a customer, so a new customer can't be created.")
        customer = created_customer = _create_customer(data.get("new_customer") or {}, keys)
        extra = []
    else:  # add_phone_to_existing
        if resolution["status"] != "NEW":
            frappe.throw("These phones already belong to a customer.")
        if not old_key:
            frappe.throw("Enter the customer's old phone number.")
        previous = customer_phones.resolve([old_key])
        if previous["status"] != "MATCHED" or previous["customer"] != chosen:
            frappe.throw(f"{display(old_key)} does not belong to that customer.")
        customer = chosen
        extra = keys

    if customer in resolution["disabled"] or frappe.db.get_value("Customer", customer, "disabled"):
        frappe.throw(f"Customer {customer} is disabled. Enable the customer first.")

    added = _add_phones(customer, extra)

    # The rule this whole flow exists for, checked once more before anything
    # is ordered: the customer owns at least one of the order's phones.
    owned = customer_phones.owners(keys)
    if not any(customer in owned.get(k, []) for k in keys):
        frappe.throw(
            "Internal check failed: the chosen customer does not own any of the order's phone numbers. "
            "Nothing was saved."
        )

    so = _build_sales_order(customer, data.get("order") or {}, settings)
    so.insert(ignore_permissions=True)

    frappe.db.set_value("AI Order Intake", intake_name, {
        "status": "Confirmed",
        "matched_customer": customer,
        "match_status": customer_phones.resolve(keys)["status"],
        "match_method": "Phone",
        "created_customer": created_customer,
        "created_sales_order": so.name,
        "customer_mode": mode,
        "final_phones": json.dumps([display(k) for k in keys], ensure_ascii=False),
        "phone_source": phone_source,
        "phone_override_reason": (data.get("override_reason") or "").strip() if phone_source == "reviewer" else None,
        "confirmed_by": frappe.session.user,
        "confirmed_at": now_datetime(),
    })
    frappe.db.commit()

    return {
        "ok": True,
        "sales_order": so.name,
        "customer": customer,
        "created_new_customer": created_customer is not None,
        "added_phones": added,
    }


# ---------------------------------------------------------------------------
# Endpoint 4: discard_intake
# ---------------------------------------------------------------------------

@frappe.whitelist()
def discard_intake(intake_name: str, reason: str) -> dict:
    """Take an intake out of the review queue for good."""
    _require_intake_permission()
    reason = (reason or "").strip()
    if not reason:
        frappe.throw("Say why this intake is being discarded.")
    status = frappe.db.get_value("AI Order Intake", intake_name, "status")
    if status not in ("Draft", "Needs Review", "Failed"):
        frappe.throw(f"An intake that is {status or 'missing'} cannot be discarded.")
    frappe.db.set_value("AI Order Intake", intake_name, {"status": "Discarded", "discard_reason": reason[:500]})
    frappe.db.commit()
    return {"ok": True, "intake_name": intake_name}


# ---------------------------------------------------------------------------
# Endpoint 5: get_item_catalog
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_item_catalog_endpoint() -> list:
    """Return available items, with prices, for the frontend autocomplete."""
    # Selling prices for the whole catalogue in one response.
    frappe.has_permission("Item", ptype="read", throw=True)
    return get_catalog_with_prices()
