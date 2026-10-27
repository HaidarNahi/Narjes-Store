"""
narjes_custom.customer_phones
=============================
Which customer owns a phone number — the only thing that decides who an
AI-intake order (or a storefront order) belongs to.

Rules this module enforces:

* A phone is compared by its canonical E.164 key (narjes_custom.phones),
  never by how it was typed. The keys live in two hidden, indexed Customer
  fields that every save refills, so a lookup is one indexed query.
* No two customers may share a phone. Saving a customer with a new or
  changed number another customer already owns is refused — from the
  desk, quick entry, data import, intake and the storefront alike. Older
  data that already breaks the rule is left alone until someone edits
  those numbers (the Customer Phone Check report lists it), and lookups
  treat such a number as owned by both customers: a human must choose.
* Check-then-write is serialised per phone number with a MariaDB named lock
  held until the transaction commits, so two saves of the same new number
  at the same moment cannot both succeed.
"""

import hashlib
import json

import frappe
from frappe import _

from narjes_custom.phones import canonical, display

# Bump when the canonical form changes: the next migrate re-fills every key.
PHONE_INDEX_VERSION = "1"
_INDEX_DEFAULT = "narjes_phone_index"

PHONE_FIELDS = (
    ("main_phone_number", "custom_main_phone_e164"),
    ("secondary_phone_number", "custom_secondary_phone_e164"),
)

_LOCK_TIMEOUT = 10


class DuplicatePhoneError(frappe.ValidationError):
    pass


class PhoneLockError(frappe.ValidationError):
    pass


# ---------------------------------------------------------------- keys


def customer_keys(row) -> tuple:
    """(main, secondary) E.164 keys for a Customer row or doc.

    A secondary equal to the main number is not indexed twice.
    """
    main = canonical(row.get("main_phone_number")) if row.get("main_phone_number") else None
    secondary = canonical(row.get("secondary_phone_number")) if row.get("secondary_phone_number") else None
    if secondary and secondary == main:
        secondary = None
    return main, secondary


def index_ready() -> bool:
    """True once backfill() has filled the indexed keys on this site.

    Until then (the minutes between a code sync and its migrate) lookups
    compute keys from the raw phone fields instead: slower, never wrong.
    """
    try:
        return frappe.db.get_default(_INDEX_DEFAULT) == PHONE_INDEX_VERSION
    except Exception:
        return False


def owners(keys, exclude=None) -> dict:
    """{key: [customer names that own it]} for each key, sorted."""
    keys = [k for k in dict.fromkeys(keys or []) if k]
    result = {k: [] for k in keys}
    if not keys:
        return result

    if index_ready():
        rows = frappe.get_all(
            "Customer",
            or_filters=[
                ["custom_main_phone_e164", "in", keys],
                ["custom_secondary_phone_e164", "in", keys],
            ],
            fields=["name", "custom_main_phone_e164", "custom_secondary_phone_e164"],
        )
        pairs = [(r.name, (r.custom_main_phone_e164, r.custom_secondary_phone_e164)) for r in rows]
    else:
        rows = frappe.get_all("Customer", fields=["name", "main_phone_number", "secondary_phone_number"])
        pairs = [(r.name, customer_keys(r)) for r in rows]

    for name, customer_key_pair in pairs:
        if name == exclude:
            continue
        for key in customer_key_pair:
            if key in result and name not in result[key]:
                result[key].append(name)
    for key in result:
        result[key].sort()
    return result


def resolve(keys) -> dict:
    """Who the phones in an order belong to.

    status: NO_PHONE (no phones) · NEW (nobody owns any of them) ·
    MATCHED (exactly one customer owns one or more of them) ·
    CONFLICT (two or more customers own them — a human picks).
    `token` changes whenever any part of the answer changes, so a confirm
    can prove nothing moved since the reviewer looked.
    """
    keys = [k for k in dict.fromkeys(keys or []) if k]
    own = owners(keys)
    customers = []
    for key in keys:
        for name in own.get(key, []):
            if name not in customers:
                customers.append(name)

    if not keys:
        status = "NO_PHONE"
    elif not customers:
        status = "NEW"
    elif len(customers) == 1:
        status = "MATCHED"
    else:
        status = "CONFLICT"

    disabled = (
        sorted(frappe.get_all("Customer", filters={"name": ["in", customers], "disabled": 1}, pluck="name"))
        if customers
        else []
    )
    result = {
        "status": status,
        "customer": customers[0] if status == "MATCHED" else None,
        "candidates": sorted(customers) if status == "CONFLICT" else [],
        "owners": own,
        "phones": keys,
        "disabled": disabled,
    }
    result["token"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


# ---------------------------------------------------------------- locks


def _lock_name(key: str) -> str:
    return f"nphone:{frappe.local.site}:{key}"[:64]


def _release_locks():
    held = getattr(frappe.local, "narjes_phone_locks", None) or []
    frappe.local.narjes_phone_locks = None
    for name in held:
        try:
            frappe.db.sql("SELECT RELEASE_LOCK(%s)", (name,))
        except Exception:
            pass  # the lock dies with the connection anyway


def lock_phones(keys):
    """Hold a named lock per phone until this transaction commits or rolls back."""
    if getattr(frappe.local, "narjes_phone_locks", None) is None:
        frappe.local.narjes_phone_locks = []
        frappe.db.after_commit.add(_release_locks)
        frappe.db.after_rollback.add(_release_locks)
    for key in sorted({k for k in keys if k}):
        name = _lock_name(key)
        got = frappe.db.sql("SELECT GET_LOCK(%s, %s)", (name, _LOCK_TIMEOUT))[0][0]
        if got != 1:
            frappe.throw(
                _("Phone {0} is being saved by someone else right now. Try again in a moment.").format(display(key)),
                exc=PhoneLockError,
            )
        frappe.local.narjes_phone_locks.append(name)


# ---------------------------------------------------------------- Customer hook


def on_customer_validate(doc, method=None):
    """Refill the phone keys and refuse a number another customer owns.

    Only numbers that are new or changed in this save are checked, so staff
    can still edit customers whose old data breaks the rules. A number being
    replaced or cleared is locked too, so an intake confirming against it
    can't commit an order to this customer while the number is taken away.
    """
    before = doc.get_doc_before_save()
    seen, changed, released = [], [], []
    for raw_field, key_field in PHONE_FIELDS:
        raw = str(doc.get(raw_field) or "").strip()
        was = str((before.get(raw_field) if before else "") or "").strip()
        is_changed = doc.is_new() or raw != was
        key = canonical(raw) if raw else None
        if is_changed and was:
            released.append(canonical(was))

        if raw and not key and is_changed:
            frappe.throw(
                _("{0}: '{1}' is not a valid phone number.").format(_(doc.meta.get_label(raw_field)), raw),
                title=_("Invalid phone number"),
            )
        if key and key in seen:
            if is_changed:
                frappe.throw(_("The main and secondary phone are the same number."), title=_("Duplicate phone"))
            key = None

        doc.set(key_field, key)
        if key:
            seen.append(key)
            if is_changed:
                changed.append(key)

    if not changed and not any(released):
        return
    lock_phones(changed + released)
    if not changed:
        return
    for key, others in owners(changed, exclude=doc.name).items():
        if others:
            frappe.throw(
                _("Phone {0} already belongs to customer {1}. Use that customer, or change the number there first.").format(
                    display(key), frappe.utils.get_link_to_form("Customer", others[0])
                ),
                exc=DuplicatePhoneError,
                title=_("Phone already in use"),
            )


# ---------------------------------------------------------------- maintenance


def backfill():
    """Fill the indexed phone keys for every customer (after_migrate).

    Runs after setup.custom_fields.run because post_model_sync patches run
    before custom fields from fixtures/after_migrate exist. Writes only rows
    whose keys changed, without running hooks or touching `modified`.
    """
    if not frappe.db.has_column("Customer", "custom_main_phone_e164"):
        print("Customer phone index: fields not created yet; skipped.")
        return
    rows = frappe.get_all(
        "Customer",
        fields=[
            "name",
            "main_phone_number",
            "secondary_phone_number",
            "custom_main_phone_e164",
            "custom_secondary_phone_e164",
        ],
    )
    updated = 0
    for row in rows:
        keys = customer_keys(row)
        if keys != (row.custom_main_phone_e164 or None, row.custom_secondary_phone_e164 or None):
            frappe.db.set_value(
                "Customer",
                row.name,
                {"custom_main_phone_e164": keys[0], "custom_secondary_phone_e164": keys[1]},
                update_modified=False,
            )
            updated += 1
    frappe.db.set_default(_INDEX_DEFAULT, PHONE_INDEX_VERSION)
    frappe.db.commit()
    print(f"Customer phone index: {len(rows)} customer(s), {updated} updated.")


# ---------------------------------------------------------------- display


def customer_summary(name):
    """What the intake review screen shows about a customer."""
    frappe.has_permission("Customer", "read", throw=True)
    row = frappe.db.get_value(
        "Customer",
        name,
        [
            "name",
            "customer_name",
            "main_phone_number",
            "secondary_phone_number",
            "governorate",
            "full_address",
            "disabled",
        ],
        as_dict=True,
    )
    if not row:
        return None
    keys = customer_keys(row)
    last = frappe.get_all(
        "Sales Order",
        filters={"customer": name, "docstatus": ["<", 2]},
        fields=["name", "transaction_date"],
        order_by="transaction_date desc, creation desc",
        limit=1,
    )
    return {
        "name": row.name,
        "customer_name": row.customer_name,
        "phones": [display(k) for k in keys if k],
        "phone_keys": [k for k in keys if k],
        "free_slot": next((raw for raw, _key in PHONE_FIELDS if not row.get(raw)), None),
        "governorate": row.governorate or "",
        "full_address": (row.full_address or "")[:120],
        "disabled": bool(row.disabled),
        "last_order": last[0] if last else None,
    }
