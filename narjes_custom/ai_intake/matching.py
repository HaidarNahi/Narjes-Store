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

# Threshold for fuzzy name matching — below this, it's "no match"
FUZZY_THRESHOLD = 85


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

def match_customer(extracted_phones: list, extracted_name: str) -> dict:
    """
    Find the best existing Customer match.

    Args:
        extracted_phones: list of raw phone strings from AI extraction
        extracted_name:   customer name string from AI extraction

    Returns dict with keys:
        customer    (str | None)   — Customer.name (doc name)
        method      (str)          — "Phone" | "Fuzzy Name" | "None"
        confidence  (float)        — 0–100
    """
    # ---- Step 1: Phone matching (exact, confidence = 100) ----
    normalized_extracted = [normalize_phone(p) for p in (extracted_phones or []) if p]
    normalized_extracted = [p for p in normalized_extracted if p]

    if normalized_extracted:
        customers = frappe.get_all(
            "Customer",
            fields=["name", "customer_name", "main_phone_number", "secondary_phone_number"],
        )
        for cust in customers:
            stored_main = normalize_stored_phone(cust.get("main_phone_number"))
            stored_sec  = normalize_stored_phone(cust.get("secondary_phone_number"))
            for extracted_num in normalized_extracted:
                if extracted_num and (
                    (stored_main and extracted_num == stored_main) or
                    (stored_sec  and extracted_num == stored_sec)
                ):
                    return {
                        "customer": cust["name"],
                        "method": "Phone",
                        "confidence": 100.0,
                    }

    # ---- Step 2: Fuzzy name matching ----
    if extracted_name:
        customers = frappe.get_all("Customer", fields=["name", "customer_name"])
        best_score = 0.0
        best_customer = None

        for cust in customers:
            # Use WRatio: handles token reordering, partial matches, transliteration
            score = fuzz.WRatio(
                extracted_name.strip().lower(),
                (cust.get("customer_name") or "").strip().lower(),
            )
            if score > best_score:
                best_score = score
                best_customer = cust["name"]

        if best_score >= FUZZY_THRESHOLD and best_customer:
            return {
                "customer": best_customer,
                "method": "Fuzzy Name",
                "confidence": round(best_score, 1),
            }

    # ---- Step 3: No match ----
    return {
        "customer": None,
        "method": "None",
        "confidence": 0.0,
    }
