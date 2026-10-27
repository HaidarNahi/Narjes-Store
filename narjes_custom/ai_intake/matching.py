"""
narjes_custom.ai_intake.matching
================================
Deterministic customer matching — zero AI involvement.

Phone storage note: Customer.main_phone_number and secondary_phone_number
are Int fields, so the leading zero of Iraqi numbers (e.g. 07701234567)
is dropped when stored (stored as 7701234567 — 10 digits).
Normalization here handles this asymmetry.
"""

import re

import frappe
from rapidfuzz import fuzz

from narjes_custom.ai_intake import settings as ai_settings

# Fallback threshold for fuzzy name matching — below this, it's "no match".
# The live value comes from AI Intake Settings; this applies only when that
# doctype can't be read (see settings.DEFAULTS).
FUZZY_THRESHOLD = 85

# Names shorter than this are never fuzzy-matched, on either side. A customer
# saved as "R" or "m" (an Instagram initial) otherwise "resembles" everyone:
# one shared letter is a full partial match.
MIN_FUZZY_NAME_LENGTH = 3


# ---------------------------------------------------------------------------
# Phone normalization
# ---------------------------------------------------------------------------

def normalize_phone(raw: str) -> str:
    """
    Normalize an Iraqi phone number to a canonical 11-digit string
    starting with '07' (e.g. '07701234567').

    Handles:
      07701234567     -> 07701234567
      +9647701234567  -> 07701234567
      009647701234567 -> 07701234567
      9647701234567   -> 07701234567
      7701234567      -> 07701234567  (stored Int, missing leading 0)
      0770-123-4567   -> 07701234567
      0770 123 4567   -> 07701234567
    """
    if raw is None:
        return ""

    # Strip everything except digits
    digits = re.sub(r"\D", "", str(raw))

    if not digits:
        return ""

    # Remove Iraqi country code variants
    if digits.startswith("00964"):
        digits = "0" + digits[5:]
    elif digits.startswith("964") and len(digits) >= 12:
        digits = "0" + digits[3:]

    # Handle stored Int format: 10 digits starting with 7 (missing leading 0)
    if len(digits) == 10 and digits.startswith("7"):
        digits = "0" + digits

    return digits


def normalize_stored_phone(stored_int) -> str:
    """
    Convert a phone number stored as an Int in Frappe's DB back to
    a normalized 11-digit string.
    """
    if not stored_int:
        return ""
    return normalize_phone(str(stored_int))


# ---------------------------------------------------------------------------
# Customer matching
# ---------------------------------------------------------------------------

def find_customer_by_phone(phones: list) -> str | None:
    """The Customer whose main or secondary phone is one of `phones`, else None."""
    wanted = {normalize_phone(p) for p in (phones or []) if p}
    wanted.discard("")
    if not wanted:
        return None

    customers = frappe.get_all(
        "Customer",
        fields=["name", "main_phone_number", "secondary_phone_number"],
    )
    for cust in customers:
        stored = {
            normalize_stored_phone(cust.get("main_phone_number")),
            normalize_stored_phone(cust.get("secondary_phone_number")),
        }
        if wanted & stored:
            return cust["name"]
    return None


def best_name_match(extracted_name: str, threshold: float) -> tuple[str | None, float]:
    """The existing customer whose name is closest to `extracted_name`.

    Returns (customer, score), or (None, 0.0) below `threshold`.

    Scored with token_sort_ratio, not WRatio. WRatio falls back to partial
    matching, which scores a lone shared letter at 90 — so a customer saved as
    a single initial was proposed for every name containing that letter. Word order
    still doesn't matter, and spelling variants ("zanab ali" / "zainab ali")
    still score in the 90s.
    """
    name = (extracted_name or "").strip().lower()
    if len(name) < MIN_FUZZY_NAME_LENGTH:
        return None, 0.0

    best_score = 0.0
    best_customer = None
    for cust in frappe.get_all("Customer", fields=["name", "customer_name"]):
        candidate = (cust.get("customer_name") or "").strip().lower()
        if len(candidate) < MIN_FUZZY_NAME_LENGTH:
            continue
        score = fuzz.token_sort_ratio(name, candidate)
        if score > best_score:
            best_score = score
            best_customer = cust["name"]

    if best_customer and best_score >= threshold:
        return best_customer, round(best_score, 1)
    return None, 0.0


def match_customer(
    extracted_phones: list, extracted_name: str, threshold: float | None = None
) -> dict:
    """
    Find the best existing Customer match.

    Args:
        extracted_phones: list of raw phone strings from AI extraction
        extracted_name:   customer name string from AI extraction
        threshold:        fuzzy score floor; None reads it from AI Intake Settings

    Returns dict with keys:
        customer    (str | None)   — Customer.name (doc name)
        method      (str)          — "Phone" | "Fuzzy Name" | "None"
        confidence  (float)        — 0–100
        name_hint   (dict | None)  — a similar-named customer that was NOT
                                     matched because the phone differs
                                     ({"customer", "confidence"})
    """
    no_match = {"customer": None, "method": "None", "confidence": 0.0, "name_hint": None}

    # ---- Step 1: Phone matching (exact, confidence = 100) ----
    phones = [p for p in (normalize_phone(p) for p in (extracted_phones or []) if p) if p]
    by_phone = find_customer_by_phone(phones)
    if by_phone:
        return {"customer": by_phone, "method": "Phone", "confidence": 100.0, "name_hint": None}

    # ---- Step 2: Fuzzy name matching ----
    settings = ai_settings.get_settings()
    if threshold is None:
        threshold = ai_settings.get_float("fuzzy_match_threshold", settings)

    if not extracted_name or not ai_settings.get_bool("enable_fuzzy_name_match", settings):
        return no_match

    customer, score = best_name_match(extracted_name, threshold)
    if not customer:
        return no_match

    # The message carries a phone number that belongs to no one, so this is
    # most likely a new person who shares a common name. Pre-selecting the old record would send the order to the
    # wrong phone and address; offer it as a hint for the reviewer instead.
    if phones:
        return {**no_match, "name_hint": {"customer": customer, "confidence": score}}

    return {"customer": customer, "method": "Fuzzy Name", "confidence": score, "name_hint": None}
