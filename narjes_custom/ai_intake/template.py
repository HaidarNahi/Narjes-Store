"""
narjes_custom.ai_intake.template
================================
Reads the shop's own order template without AI.

Every order pasted into AI Order Intake is a form the shop sends to its
customers, in one of a few versions:

    v2:  👤 اسم الزبون · @ اسم المستخدم · 📱 منصة الطلب · 📅 تاريخ استلام الطلب ·
         🚚 تاريخ تسليم الطلب · 🖼️ تفاصيل الطلب · 🎁 تغليف هدية · 📍 العنوان ·
         📞 رقم الهاتف · (💸 قيمة الخصم) · 💰 مبلغ الطلب · 🚚 خدمة التوصيل ·
         💳 المبلغ الكلي · ‼️ملاحظة
    v1:  🔹طلب باسم · … · 📞رقم الموبايل · 💵 مبلغ الطلب · 🚗خدمة التوصيل · …

The phone always sits in the 📞 section — on the label line or on the few
lines under it, sometimes behind a sub-label (الرقم الثاني، رقم احتياط). That
section is the only place a customer-identity phone is read from: reading it
deterministically means a phone can never be one the AI mistyped.

Pure functions only — no Frappe import — so the tests run without a site.
"""

import re
import unicodedata
from dataclasses import dataclass, field

from narjes_custom.phones import PhoneHit, clean_text, find_phones, unreadable_groups

# (key, label pattern). A line is a label line when, after dropping leading
# emoji/symbols and invisible marks, it starts with one of these and a colon.
LABELS = (
    ("name", r"(?:اسم\s*الزبون|طلب\s*باسم)"),
    ("username", r"@?\s*اسم\s*المستخدم"),
    ("platform", r"منصة\s*الطلب"),
    ("received", r"تاريخ\s*استلام\s*الطلب"),
    ("delivery", r"تاريخ\s*تسليم\s*الطلب"),
    ("details", r"تفاصيل\s*الطلب"),
    ("gift", r"تغليف\s*هدي[ةه](?:\s*او\s*لا)?"),
    ("address", r"العنوان"),
    ("phone", r"رقم\s*(?:ال)?(?:هاتف|موبايل|جوال|تلفون|تليفون)"),
    ("discount", r"(?:قيمة\s*)?الخصم"),
    ("amount", r"مبلغ\s*الطلب"),
    ("fee", r"خدمة\s*التوصيل"),
    ("total", r"المبلغ\s*الكلي"),
    ("note", r"ملاحظ[ةه]"),
)
_LABEL_RE = [(key, re.compile(rf"^(?:{pattern})\s*[:：]\s*(?P<value>.*)$")) for key, pattern in LABELS]

# How many lines under a label still belong to it.
_CONTINUATION_CAP = {"phone": 6, "details": 12, "address": 4}
_DEFAULT_CAP = 3

# Lines whose numbers are money or dates — never searched for a phone when
# the message is not a recognised template.
_NO_PHONE_KEYS = {"received", "delivery", "discount", "amount", "fee", "total"}

# Fewer distinct known labels than this and the text is not the template.
_MIN_LABELS = 4

_GIFT_NO = {"بدون", "لا", "كلا", "no"}
_GIFT_YES = {"نعم", "اي", "ايه", "اكيد", "yes"}


@dataclass
class TemplateResult:
    recognised: bool = False
    version: str | None = None  # "v1" | "v2" | None
    labels: list = field(default_factory=list)  # known keys, in order of appearance
    fields: dict = field(default_factory=dict)  # key -> text (label value + continuation lines)
    phone_section: str | None = None
    phone_source: str = "none"  # "template" | "free_text" | "none"
    phones: list[PhoneHit] = field(default_factory=list)
    phone_problems: list = field(default_factory=list)  # digit runs that are not a valid phone
    name: str = ""
    username: str = ""
    platform: str = ""
    address: str = ""
    amounts: dict = field(default_factory=dict)  # order / fee / total / discount -> int IQD
    assumed_thousands: list = field(default_factory=list)  # amount keys read as thousands
    gift_hint: bool | None = None
    notes: list = field(default_factory=list)

    @property
    def phone_keys(self) -> list:
        return [hit.e164 for hit in self.phones]


def _strip_leading_symbols(line: str) -> str:
    """Drop emoji, symbols and punctuation in front of the label text."""
    i = 0
    while i < len(line) and line[i] != "@" and not ("؀" <= line[i] <= "ۿ"):
        i += 1
    return line[i:]


def _starts_with_symbol(line: str) -> bool:
    stripped = line.lstrip()
    return bool(stripped) and unicodedata.category(stripped[0]).startswith("S")


def _label(cleaned_line: str):
    """(key, value) for a label line, ("other", value) for an unknown
    emoji-led "label:" line (a template field we don't know yet), or None."""
    body = re.sub(r"\s+", " ", _strip_leading_symbols(cleaned_line)).strip()
    for key, regex in _LABEL_RE:
        match = regex.match(body)
        if match:
            return key, match.group("value").strip()
    colon = cleaned_line.find(":")
    if _starts_with_symbol(cleaned_line) and 0 < colon <= 40:
        return "other", cleaned_line[colon + 1:].strip()
    return None


def parse_iqd(value):
    """(amount_in_iqd, assumed_thousands) for a template money value, or None.

    "35 الف" → (35000, False) · "5الاف" → (5000, False) · "مجاني" → (0, False)
    · "35" → (35000, True): the shop writes thousands without the word ·
    "تكسي" → None (not an amount).
    """
    text = clean_text(value).strip()
    if not text:
        return None
    if "مجان" in text:
        return 0, False
    text = re.sub(r"(?<=\d)[,٬](?=\d{3}\b)", "", text)
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    unit = re.match(r"\s*(?:الف|الاف|آلاف|ألف|الل|k\b|K\b)", text[match.end():])
    if unit:
        return round(number * 1000), False
    if number < 1000:
        return round(number * 1000), True
    return round(number), False


def _gift_hint(value: str):
    text = re.sub(r"\s+", " ", value).strip().lower()
    if not text or text in _GIFT_NO:
        return False
    if text in _GIFT_YES or text.split(" ")[0] in _GIFT_YES:
        return True
    return None


def _collapse(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", text).strip()[:limit]


def parse(text: str) -> TemplateResult:
    result = TemplateResult()
    lines = (text or "").splitlines()

    collected = {}  # key -> list of lines
    current = None
    taken = 0
    known = []
    above_phone = []  # non-label lines directly above the 📞 label

    for index, raw in enumerate(lines):
        cleaned = clean_text(raw)
        labelled = _label(cleaned)
        if labelled:
            key, value = labelled
            if key == "other":
                current = None  # an unknown field ends the previous one
                continue
            if key in collected:
                result.notes.append(f"The field '{key}' appears more than once; the first one is used.")
                current = None
                continue
            collected[key] = [value]
            known.append(key)
            current, taken = key, 0
            if key == "phone":
                # Staff sometimes type the answer before the label on the same
                # line ("0770… 📞 رقم الهاتف:"): that text is part of the field.
                prefix = cleaned[: len(cleaned) - len(_strip_leading_symbols(cleaned))]
                if any(ch.isdigit() for ch in prefix):
                    collected[key].insert(0, prefix)
                # …or on the line above it. Kept aside; used only if the field
                # itself holds no number (see below).
                for previous in reversed(lines[max(0, index - 2):index]):
                    previous = clean_text(previous)
                    if not previous.strip():
                        continue
                    if _label(previous):
                        break
                    above_phone.insert(0, previous)
            if key == "name":
                result.version = "v2" if re.search(r"اسم\s*الزبون", cleaned) else "v1"
            continue
        if current is None:
            continue
        if taken < _CONTINUATION_CAP.get(current, _DEFAULT_CAP):
            collected[current].append(cleaned)
            taken += 1

    result.labels = known
    result.fields = {key: "\n".join(parts).strip() for key, parts in collected.items()}
    result.recognised = len(set(known)) >= _MIN_LABELS
    if not result.recognised:
        result.version = None

    # ---- identity phones -------------------------------------------------
    if result.recognised and "phone" in collected:
        section = "\n".join(collected["phone"])
        result.phone_section = section
        result.phones = find_phones(section)
        result.phone_problems = unreadable_groups(section)
        result.phone_source = "template" if result.phones else "none"
        if not result.phones and above_phone:
            above = "\n".join(above_phone)
            result.phones = find_phones(above)
            if result.phones:
                # A number typed above the label could belong to the field
                # above it, so the reviewer must confirm it like free text.
                result.phone_source = "free_text"
                result.phone_problems += unreadable_groups(above)
                result.notes.append(
                    "The 📞 field is empty; the number on the line above it was used. Confirm it is the customer's."
                )
    else:
        searchable = "\n".join(
            clean_text(raw) for raw in lines
            if not ((lab := _label(clean_text(raw))) and lab[0] in _NO_PHONE_KEYS)
        )
        result.phones = find_phones(searchable)
        result.phone_problems = unreadable_groups(searchable)
        result.phone_source = "free_text" if result.phones else "none"
        if result.recognised:
            result.notes.append("The order form has no phone field; numbers were looked for in the whole message.")

    # ---- other fields (prefill only; never used for matching) -----------
    fields = result.fields
    result.name = _collapse(fields.get("name", ""), 140)
    result.username = _collapse(fields.get("username", ""), 140).lstrip("@").strip()
    result.platform = _collapse(fields.get("platform", ""), 60)
    result.address = " - ".join(
        part.strip() for part in fields.get("address", "").splitlines() if part.strip()
    )[:500]
    for key, amount_key in (("amount", "order"), ("fee", "fee"), ("total", "total"), ("discount", "discount")):
        if key not in fields:
            continue
        parsed = parse_iqd(fields[key].split("\n")[0])
        if parsed is None:
            continue
        result.amounts[amount_key], assumed = parsed
        if assumed:
            result.assumed_thousands.append(amount_key)
    if "gift" in fields:
        result.gift_hint = _gift_hint(fields["gift"].split("\n")[0])

    return result
