# AI Order Intake v2 — customers are matched by phone number only

## The rule

A Sales Order created by AI Order Intake (or by storefront checkout) belongs
to a customer **only if that customer owns, as a stored main or secondary
phone, one of the phone numbers the order is confirmed with.** Names,
usernames and addresses never decide who the customer is. The server checks
this at confirm time and asserts it once more right before the Sales Order is
inserted.

Why: name matching attached orders to the wrong customers. A customer saved as
a single initial "resembled" every name containing that letter, and a new
customer sharing a common name with an old one landed on the old customer's
record, with the old phone and address.

## Where the phone comes from

The pasted text is the shop's own order form (v1 `🔹طلب باسم…`, v2
`👤 اسم الزبون…`, and v2 with a `💸 قيمة الخصم` line). The phone always sits in
the `📞 رقم الهاتف` / `📞رقم الموبايل` section: on the label line, on the lines
under it, or behind a sub-label (`الرقم الثاني`, `رقم احتياط`).

`ai_intake/template.py` reads that section **without AI**, so a phone can never
be one the model mistyped. Gemini still reads everything else (items, dates,
governorate…), and its phones are only compared with the form's. A difference
is shown to the reviewer, and the AI's version is ignored.

| Situation | `phone_source` | What the reviewer does |
|---|---|---|
| valid number(s) in the 📞 field | `template` | nothing; may untick extra numbers |
| 📞 field empty, a number on the line above it, or no order form at all | `free_text` | ticks "This is the customer's phone" |
| no readable number | `none` | types the phone and presses Check |
| the message's number is wrong | `reviewer` | "The phone in the message is wrong" + a reason |

## One canonical phone form

`narjes_custom/phones.py` turns every spelling (`٠٧٧٠١٢٣٤٥٦٧`, `0770 123 4567`,
`+964 770 123 4567`, `7701234567`, invisible right-to-left marks…) into one E.164
key (`+9647701234567`) using libphonenumber, and refuses anything that isn't a
valid number. Digit runs that look like a phone but aren't one are reported,
not dropped.

## Who owns a number

`narjes_custom/customer_phones.py`:

- Two hidden, indexed Customer fields (`custom_main_phone_e164`,
  `custom_secondary_phone_e164`) hold the keys, refilled on every save and
  backfilled after every migrate.
- `resolve(phones)` → `NO_PHONE` · `NEW` (nobody owns them) · `MATCHED`
  (exactly one customer) · `CONFLICT` (two or more — a person picks), plus a
  token that changes whenever the answer could.
- Saving a customer with a **new or changed** number that another customer
  owns, or that isn't valid, is refused everywhere (desk, quick entry, import,
  intake, storefront), under a MariaDB named lock per number held until
  commit. Unchanged older data never blocks a save.

## Confirming

`confirm_intake` trusts nothing from the browser: it re-reads the phones,
re-resolves under the locks, refuses with `resolution_changed` (writing
nothing) if customers changed since review, and allows exactly four choices:

1. `matched` — the phone's owner (optionally saving an extra number in a free slot);
2. `pick` — one of the owners in a conflict;
3. `new` — a new customer, only when nobody owns the phones;
4. `add_phone_to_existing` — an existing customer with a new number, found by
   their **old phone**, never by name.

## Reports

- **Customer Phone Check**: numbers shared by two customers, invalid numbers,
  the same number twice, customers with no number.
- **Intake Phone Audit**: confirmed orders whose customer owns none of the
  message's phones (most likely misattributed by the old name matching). Staff
  fix them by hand; nothing is changed automatically.

## AI call

`extract_order_with_meta()` stores the model, latency, attempts, finish reason
and prompt/output/thinking/cached token counts on every intake. A reply that
won't parse (usually cut off: thinking tokens count against the output budget)
is retried once with twice the budget. The Thinking Level setting is empty by
default (the model's own level); lowering it is a measured choice.

`bench --site <site> execute narjes_custom.tools.intake_v2_replay.run` prints
counts (no personal data) of how v2 reads the intake history.
