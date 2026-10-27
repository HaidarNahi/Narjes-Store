"""
narjes_custom.phones
====================
One canonical form for every phone number in the app.

Customer identity in AI Order Intake rests on phone numbers alone, so two
spellings of the same number must compare equal and a number that cannot be
read must never quietly turn into a different one. Real order messages write
the same Iraqi mobile number as ٠٧٧٠١٢٣٤٥٦٧, 0770 123 4567, +964 770 123 4567
or 7701234567, often wrapped in invisible right-to-left marks. Everything here
reduces those to one E.164 key (+9647701234567) using Google's libphonenumber
(the `phonenumbers` package Frappe already depends on), and refuses anything
libphonenumber does not consider a valid number.

Pure functions only — no Frappe import — so the tests run without a site.
"""

import re
import unicodedata
from dataclasses import dataclass

import phonenumbers
from phonenumbers import Leniency, PhoneNumberFormat, PhoneNumberMatcher

DEFAULT_REGION = "IQ"

# A run of digits with single space/dash/dot separators, optionally led by +
# or 00. Used for the shapes PhoneNumberMatcher skips (a spaced 10-digit
# "770 000 0101" written without its leading 0).
# Long enough for two numbers in one run; _fallback_hits splits them.
_CANDIDATE = re.compile(r"(?<![\d+])(?:\+|00)?\d(?:[ \-.]?\d){8,40}(?!\d)")
_SEPARATOR = re.compile(r"[ \-.]")

# Anything long enough to be a phone number: if no valid number covers it,
# the reviewer is shown it instead of it being silently dropped. Nine digits
# is the floor: a mobile number one digit short still has ten, while a date
# such as 2026-10-27 has eight and must not be reported.
_DIGIT_GROUP = re.compile(r"(?<!\d)\+?\d(?:[ \-.]?\d){8,}(?!\d)")


@dataclass(frozen=True)
class PhoneHit:
    """A valid phone number found in a piece of text."""

    e164: str
    raw: str
    start: int  # positions refer to clean_text(text)
    end: int
    method: str  # "matcher" | "fallback"


def clean_text(value) -> str:
    """Normalise text before looking for numbers in it.

    - drops every invisible format character (Unicode category Cf: the
      bidi marks U+200E/F, U+202A–E, U+2066–9, zero-width joiners, BOM,
      soft hyphen) that WhatsApp and Instagram scatter around numbers;
    - turns every kind of space (NBSP, narrow NBSP, …) into a plain space;
    - turns every decimal digit (Arabic-Indic ٠-٩, Persian ۰-۹, fullwidth)
      into its ASCII digit.
    """
    if value is None:
        return ""
    out = []
    for ch in str(value):
        category = unicodedata.category(ch)
        if category == "Cf":
            continue
        if category == "Zs":
            out.append(" ")
            continue
        digit = unicodedata.decimal(ch, None)
        out.append(str(digit) if digit is not None else ch)
    return "".join(out)


def _e164(number) -> str:
    return phonenumbers.format_number(number, PhoneNumberFormat.E164)


def _valid(text: str, region: str):
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException:
        return None
    return number if phonenumbers.is_valid_number(number) else None


def _overlaps(start: int, end: int, hits) -> bool:
    return any(start < h.end and h.start < end for h in hits)


def _fallback_hits(match, region: str) -> list[PhoneHit]:
    """Valid numbers inside one candidate run, tried left to right.

    A run can hold two numbers separated by a single space
    ("770 000 0101 780 000 0102"); the whole run is not a number, so try the
    longest run of whole digit groups starting at each group instead.
    """
    text = match.group(0)
    base = match.start()
    groups = []  # (start, end) of each digit group inside text
    pos = 0
    for part in _SEPARATOR.split(text):
        groups.append((pos, pos + len(part)))
        pos += len(part) + 1

    hits = []
    i = 0
    while i < len(groups):
        for j in range(len(groups), i, -1):
            start, end = groups[i][0], groups[j - 1][1]
            piece = text[start:end]
            digits = sum(c.isdigit() for c in piece)
            if not 9 <= digits <= 15:
                continue
            number = _valid(piece, region)
            if number:
                hits.append(PhoneHit(_e164(number), piece, base + start, base + end, "fallback"))
                i = j
                break
        else:
            i += 1
    return hits


def _scan(text, region: str) -> tuple[str, list[PhoneHit]]:
    """Every valid number in text, in order, duplicates included."""
    cleaned = clean_text(text)
    hits = [
        PhoneHit(_e164(m.number), m.raw_string, m.start, m.end, "matcher")
        for m in PhoneNumberMatcher(cleaned, region, leniency=Leniency.VALID)
    ]
    for match in _CANDIDATE.finditer(cleaned):
        if _overlaps(match.start(), match.end(), hits):
            continue
        hits.extend(_fallback_hits(match, region))
    hits.sort(key=lambda h: h.start)
    return cleaned, hits


def find_phones(text, region: str = DEFAULT_REGION) -> list[PhoneHit]:
    """The distinct valid phone numbers in text, in the order they appear."""
    _cleaned, hits = _scan(text, region)
    seen, distinct = set(), []
    for hit in hits:
        if hit.e164 not in seen:
            seen.add(hit.e164)
            distinct.append(hit)
    return distinct


def unreadable_groups(text, region: str = DEFAULT_REGION) -> list[str]:
    """Digit groups long enough to be a phone number that are not one.

    "0770 000 010" (a digit short) or "077000001019" (a digit too many) end
    up here, so the reviewer sees exactly what the customer wrote instead of
    the number disappearing.
    """
    cleaned, hits = _scan(text, region)
    return [
        m.group(0)
        for m in _DIGIT_GROUP.finditer(cleaned)
        if not _overlaps(m.start(), m.end(), hits)
    ]


def canonical(raw, region: str = DEFAULT_REGION) -> str | None:
    """The E.164 key for one stored or typed phone value, or None.

    None when the value is empty, not a valid number, or holds two different
    numbers ("0770… / 0780…" in one field is ambiguous: neither is chosen).
    """
    if raw is None:
        return None
    text = clean_text(raw).strip()
    if not text:
        return None
    keys = {hit.e164 for hit in find_phones(text, region)}
    if len(keys) == 1:
        return keys.pop()
    if keys:
        return None
    number = _valid(text, region)
    return _e164(number) if number else None


def is_iraqi(e164: str) -> bool:
    return bool(e164) and e164.startswith("+964")


def national(e164: str) -> str:
    """How the shop stores a number: 07700000101 for Iraq, E.164 otherwise."""
    if not e164:
        return ""
    if is_iraqi(e164):
        return "0" + e164[len("+964"):]
    return e164


def display(e164: str) -> str:
    """How a number is shown to staff: 0770 000 0101, or +971 50 … abroad."""
    if not e164:
        return ""
    number = phonenumbers.parse(e164, None)
    fmt = PhoneNumberFormat.NATIONAL if is_iraqi(e164) else PhoneNumberFormat.INTERNATIONAL
    return phonenumbers.format_number(number, fmt)
