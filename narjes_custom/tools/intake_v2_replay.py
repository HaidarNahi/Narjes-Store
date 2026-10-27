"""Replay intake v2's phone reading over the AI Order Intake history.

Read-only, and it prints counts only — never a name, phone or message — so
it is safe to run on production:

    bench --site <site> execute narjes_custom.tools.intake_v2_replay.run

What it answers:
- how many messages are the shop's order form, and in which version;
- where the identity phone comes from (📞 field / elsewhere / none);
- whether the order-form phones equal the phones the AI read before v2;
- how v2 would resolve each message against today's customers;
- for confirmed intakes, whether the order's customer owns a message phone.
"""

import json
from collections import Counter

import frappe

from narjes_custom import customer_phones
from narjes_custom.ai_intake import template
from narjes_custom.phones import canonical


def run(limit=None):
    intakes = frappe.get_all(
        "AI Order Intake",
        fields=["raw_text", "extracted_json", "status", "created_sales_order"],
        order_by="creation asc",
        limit=int(limit) if limit else None,
    )
    order_customers = dict(
        frappe.get_all(
            "Sales Order",
            filters={"name": ["in", [i.created_sales_order for i in intakes if i.created_sales_order]]},
            fields=["name", "customer"],
            as_list=True,
        )
    ) if any(i.created_sales_order for i in intakes) else {}

    counts = Counter()
    for intake in intakes:
        form = template.parse(intake.raw_text or "")
        counts["messages"] += 1
        counts["recognised as the order form" if form.recognised else "not the order form (free text)"] += 1
        if form.recognised:
            counts[f"form version:{form.version or 'no name line'}"] += 1
        counts[f"phone source:{form.phone_source}"] += 1
        if form.phone_problems:
            counts["messages with unreadable digits"] += 1

        try:
            ai_phones = json.loads(intake.extracted_json or "{}").get("phone_numbers") or []
        except (TypeError, ValueError):
            ai_phones = []
        ai_keys = {k for k in (canonical(p) for p in ai_phones) if k}
        mine = set(form.phone_keys)
        if mine == ai_keys:
            counts["form phones = AI phones"] += 1
        elif not mine:
            counts["AI only (form has none)"] += 1
        elif not ai_keys:
            counts["form only (AI read none)"] += 1
        else:
            counts["form and AI differ"] += 1
        if any(p and not canonical(p) for p in ai_phones):
            counts["AI produced an invalid phone"] += 1

        resolution = customer_phones.resolve(form.phone_keys)
        counts[f"resolves today as:{resolution['status']}"] += 1

        if intake.status == "Confirmed" and intake.created_sales_order and form.phone_keys:
            customer = order_customers.get(intake.created_sales_order)
            owners = customer_phones.owners(form.phone_keys)
            if customer and any(customer in owners.get(k, []) for k in form.phone_keys):
                counts["confirmed: customer owns a message phone"] += 1
            else:
                counts["confirmed: customer owns NO message phone"] += 1

    total = counts["messages"] or 1
    print(f"Intake v2 replay over {counts['messages']} message(s):")
    for key in sorted(k for k in counts if k != "messages"):
        print(f"  {key:<45} {counts[key]:>5}  ({100 * counts[key] / total:.1f}%)")
    return dict(counts)
