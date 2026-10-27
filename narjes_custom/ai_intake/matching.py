"""
narjes_custom.ai_intake.matching
================================
Customer matching for intake and the storefront — by phone number only.

Names are never used. A name-based fuzzy match used to attach orders to the
wrong customer: a customer saved as "R" "resembled" every name containing
an r, and a new "zainab" with a new number landed on the old zainab's record,
phone and address. Identity now comes only from exact equality of canonical
phone numbers; see narjes_custom.phones (the canonical form) and
narjes_custom.customer_phones (who owns which number).

This module keeps the names older callers import.
"""

from narjes_custom import customer_phones
from narjes_custom.phones import canonical, national


def normalize_phone(raw) -> str:
    """The number as the shop stores it (07701234567), or "" if invalid."""
    key = canonical(raw)
    return national(key) if key else ""


def normalize_stored_phone(stored) -> str:
    """Same as normalize_phone; kept for older callers (stored values may be ints)."""
    return normalize_phone(stored)


def _keys(phones) -> list:
    return [k for k in (canonical(p) for p in (phones or []) if p) if k]


def find_customer_by_phone(phones) -> str | None:
    """The one customer that owns any of these phones, else None.

    None also when two different customers own them: that is for a person
    to decide, never for this function to guess.
    """
    result = customer_phones.resolve(_keys(phones))
    return result["customer"] if result["status"] == "MATCHED" else None


def match_customer(extracted_phones, extracted_name=None, threshold=None) -> dict:
    """Match by phone. `extracted_name` and `threshold` are accepted for old
    callers and deliberately ignored: a name never decides the customer."""
    result = customer_phones.resolve(_keys(extracted_phones))
    if result["status"] == "MATCHED":
        return {"customer": result["customer"], "method": "Phone", "confidence": 100.0, "status": "MATCHED"}
    return {
        "customer": None,
        "method": "Conflict" if result["status"] == "CONFLICT" else "None",
        "confidence": 0.0,
        "status": result["status"],
        "candidates": result["candidates"],
    }
