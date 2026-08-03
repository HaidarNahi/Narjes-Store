"""
narjes_custom.ai_intake.extraction
====================================
Gemini extraction layer — AI is used ONLY here.
AI never touches the database. All it does is parse raw text → structured dict.

Every knob (model, temperature, timeout, retries, prompt, catalog and
example handling) comes from the `AI Intake Settings` Single doctype via
`narjes_custom.ai_intake.settings`. The API key resolves from that doctype
first, then falls back to site_config.json:
    bench --site narjes.local set-config gemini_api_key "YOUR_KEY_HERE"
"""

import json
import time

import frappe
from google import genai
from google.genai import types

from narjes_custom.ai_intake import settings as ai_settings


# ---------------------------------------------------------------------------
# Dynamic item catalog — always fresh from the Item master
# ---------------------------------------------------------------------------

def get_item_catalog() -> list[dict]:
    """
    Fetch all active, non-disabled items from the Item master.
    Returns list of dicts: [{"name": "Wood Stand", "item_name": "...", "item_group": "..."}]

    Deliberately unfiltered: the review screen autocompletes against this, so
    it must show every item a human could pick. The narrowing knobs in AI
    Intake Settings apply to get_prompt_catalog() only.
    """
    return frappe.get_all(
        "Item",
        filters={"disabled": 0},
        fields=["name", "item_name", "item_group"],
        order_by="name asc",
    )


def get_prompt_catalog(settings=None) -> list[dict]:
    """
    The subset of the catalog that gets sent to the model, after the
    `Only These Item Groups` and `Max Catalog Items` settings.
    """
    filters = {"disabled": 0}

    groups = ai_settings.get_lines("catalog_item_groups", settings)
    if groups:
        filters["item_group"] = ["in", groups]

    limit = ai_settings.get_int("max_catalog_items", settings)

    return frappe.get_all(
        "Item",
        filters=filters,
        fields=["name", "item_name", "item_group"],
        order_by="name asc",
        limit=limit if limit > 0 else None,
    )


def _build_catalog_for_prompt(catalog: list[dict], include_item_name: bool = True) -> str:
    """Format the item catalog as a readable list for the AI prompt."""
    lines = []
    for item in catalog:
        # Show the item code (name) and the group for disambiguation
        line = f"  - \"{item['name']}\" (group: {item['item_group']}"
        # The item name is often the Arabic one while the code is not, so it
        # is what a customer's message actually resembles
        if include_item_name and item.get("item_name") and item["item_name"] != item["name"]:
            line += f", name: {item['item_name']}"
        lines.append(line + ")")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Few-shot examples
# ---------------------------------------------------------------------------

FEW_SHOT_EXAMPLES = [
    {
        "input": (
            "السلام عليكم، عندي طلب لو سمحت.\n"
            "الاسم: احمد محمد\n"
            "رقم الهاتف: 07701234567\n"
            "المنتج: MDF 30*40 كانفاس، الكمية 2، السعر 20000\n"
            "التوصيل: الخميس"
        ),
        "output": {
            "customer_name": "احمد محمد",
            "phone_numbers": ["07701234567"],
            "username": None,
            "address": None,
            "governorate": None,
            "delivery_date": None,
            "gift": False,
            "priority": None,
            "currency": "IQD",
            "order_items": [
                {
                    "description": "MDF 30*40 كانفاس",
                    "item_code_hint": "MDF 30*40",
                    "qty": 2,
                    "unit_price": 20000,
                    "notes": ""
                }
            ],
            "extraction_notes": ["delivery_date: mentioned 'Thursday' but no date specified"]
        }
    },
    {
        "input": (
            "طلب جديد:\n"
            "حسين علي - 0790-555-1234\n"
            "لوحة 40x60 مع ستاند خشب + وردة\n"
            "السعر: 35000\n"
            "هدية - ضروري يوصل الجمعة"
        ),
        "output": {
            "customer_name": "حسين علي",
            "phone_numbers": ["07905551234"],
            "username": None,
            "address": None,
            "governorate": None,
            "delivery_date": None,
            "gift": True,
            "priority": "High",
            "currency": "IQD",
            "order_items": [
                {
                    "description": "لوحة 40x60",
                    "item_code_hint": "mdf 40*60",
                    "qty": 1,
                    "unit_price": 35000,
                    "notes": ""
                },
                {
                    "description": "ستاند خشب",
                    "item_code_hint": "Wood Stand",
                    "qty": 1,
                    "unit_price": 0,
                    "notes": "included with order or priced separately unclear"
                },
                {
                    "description": "وردة",
                    "item_code_hint": "Flower",
                    "qty": 1,
                    "unit_price": 0,
                    "notes": "included with order or priced separately unclear"
                }
            ],
            "extraction_notes": [
                "delivery_date: mentioned 'Friday' but no specific date",
                "Wood Stand and Flower prices unclear — may be included in main price"
            ]
        }
    },
    {
        "input": (
            "طلب زبون:\n"
            "الاسم: سارة احمد (07801112233)\n"
            "العنوان: بغداد - الكرادة شارع الصناعة\n"
            "الطلب: لوحة كانفاس 50x70 عدد 1 بسعر 45000 د.ع\n"
            "خصم: 5000\n"
            "ملاحظات اضافية: تغليف خارجي بشريطة حمراء وكتابة كارت معايدة (كل عام وانت بخير)"
        ),
        "output": {
            "customer_name": "سارة احمد",
            "phone_numbers": ["07801112233"],
            "username": None,
            "address": "الكرادة شارع الصناعة",
            "governorate": "بغداد",
            "delivery_date": None,
            "gift": False,
            "priority": None,
            "discount_amount": 5000,
            "custom_details": "تغليف خارجي بشريطة حمراء وكتابة كارت معايدة (كل عام وانت بخير)",
            "currency": "IQD",
            "order_items": [
                {
                    "description": "لوحة كانفاس 50x70",
                    "item_code_hint": "50*70",
                    "qty": 1,
                    "unit_price": 45000,
                    "notes": ""
                }
            ],
            "extraction_notes": []
        }
    },
]


# ---------------------------------------------------------------------------
# Response schema (Gemini structured output)
# ---------------------------------------------------------------------------

EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "customer_name": {"type": "STRING"},
        "phone_numbers": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        },
        "username": {"type": "STRING", "nullable": True},
        "address": {"type": "STRING", "nullable": True},
        "governorate": {"type": "STRING", "nullable": True},
        "delivery_date": {"type": "STRING", "nullable": True},
        "gift": {"type": "BOOLEAN"},
        "priority": {"type": "STRING", "nullable": True},
        "discount_amount": {"type": "NUMBER", "nullable": True},
        "custom_details": {"type": "STRING", "nullable": True},
        "currency": {"type": "STRING"},
        "order_items": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "description": {"type": "STRING"},
                    "item_code_hint": {"type": "STRING", "nullable": True},
                    "qty": {"type": "NUMBER"},
                    "unit_price": {"type": "NUMBER"},
                    "notes": {"type": "STRING"}
                },
                "required": ["description", "qty", "unit_price"]
            }
        },
        "extraction_notes": {
            "type": "ARRAY",
            "items": {"type": "STRING"}
        }
    },
    "required": ["customer_name", "phone_numbers", "order_items", "currency", "gift", "extraction_notes"]
}


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

def resolve_few_shot_examples(settings=None) -> list[dict]:
    """
    The examples to teach the model with: the admin's JSON override from
    AI Intake Settings if it parses, otherwise the built-ins above.

    Falling back rather than raising is deliberate — a typo in the override
    should cost prompt quality, not block every order coming in. The doctype
    validates the JSON on save, so a broken value can only get here if it was
    written around the form.
    """
    raw = ai_settings.get_str("few_shot_examples", settings).strip()
    if not raw:
        return FEW_SHOT_EXAMPLES

    try:
        parsed = json.loads(raw)
    except Exception:
        return FEW_SHOT_EXAMPLES

    if not isinstance(parsed, list) or not parsed:
        return FEW_SHOT_EXAMPLES

    examples = [ex for ex in parsed if isinstance(ex, dict) and "input" in ex and "output" in ex]
    return examples or FEW_SHOT_EXAMPLES


def _build_system_prompt(catalog: list[dict], settings) -> str:
    base_prompt = settings.system_prompt_base or "You are an order intake assistant."
    rules = settings.extraction_rules or ""

    prompt = f"{base_prompt}\n\nRULES:\n{rules}"

    # Dynamically inject Governorate options so the AI doesn't invent invalid ones
    if ai_settings.get_bool("append_governorates", settings):
        try:
            meta = frappe.get_meta("Customer")
            gov_field = meta.get_field("governorate")
            if gov_field and gov_field.options:
                valid_options = [opt for opt in gov_field.options.split("\n") if opt.strip()]
                prompt += (
                    f"\n\nVALID GOVERNORATE OPTIONS (You MUST pick one of these exactly, or return null):\n"
                    f"{', '.join(valid_options)}"
                )
        except Exception:
            pass

    if ai_settings.get_bool("append_catalog", settings):
        items_list = _build_catalog_for_prompt(
            catalog,
            include_item_name=ai_settings.get_bool("catalog_include_item_name", settings),
        )
        prompt += f"\n\nAVAILABLE ITEM CATALOG:\n{items_list}"

    if ai_settings.get_bool("append_examples", settings):
        few_shot_text = ""
        for i, ex in enumerate(resolve_few_shot_examples(settings), 1):
            few_shot_text += (
                f"\n\n--- Example {i} ---\n"
                f"Input:\n{ex['input']}\n\n"
                f"Expected JSON output:\n{json.dumps(ex['output'], ensure_ascii=False, indent=2)}"
            )
        prompt += f"\n\nFEW-SHOT EXAMPLES:{few_shot_text}"

    prompt += "\n\nDISCOUNT RULE: Extract any explicitly mentioned discount amount from the text and place it in the 'discount_amount' field as a number (e.g. 5000 for 5000 IQD discount, or 10000). If no discount is mentioned, use null."
    prompt += "\n\nCUSTOM DETAILS RULE: Extract any additional details, special instructions, custom notes, or unmapped text into the 'custom_details' field as text. If no extra details are mentioned, use null."

    extra = ai_settings.get_str("extra_instructions", settings).strip()
    if extra:
        prompt += f"\n\nADDITIONAL INSTRUCTIONS:\n{extra}"

    prompt += "\n\nNow extract the order data from the user's message and return ONLY valid JSON matching the schema."
    return prompt


def build_system_prompt(settings=None) -> str:
    """The exact system instruction an extraction would send right now.

    Used by the Preview System Prompt button so prompt edits can be checked
    against the real assembled text instead of guessed at.
    """
    if settings is None:
        settings = ai_settings.get_settings()
    return _build_system_prompt(get_prompt_catalog(settings), settings)


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

class ExtractionError(Exception):
    """Raised when Gemini call fails or returns unusable output."""
    pass


def resolve_api_key(settings=None) -> str:
    """The API key in use: the one on AI Intake Settings, else site config."""
    if settings is None:
        settings = ai_settings.get_settings()
    if settings is not None and settings.get("api_key"):
        return settings.get_password("api_key")
    return frappe.conf.get("gemini_api_key")


def _is_worth_retrying(exc: Exception) -> bool:
    """
    Whether a failed Gemini call could plausibly succeed on a second attempt.

    Rate limits and 5xx are transient; so is anything that never got an HTTP
    status at all (timeout, DNS, dropped connection). A 400/401/403/404 means
    the key, model name or request is wrong — retrying that just makes the
    user wait longer for the same error.
    """
    code = getattr(exc, "code", None)
    if code is None:
        return True
    return code == 429 or code >= 500


def extract_order(raw_text: str) -> dict:
    """
    Extract structured order data from raw_text using the configured Gemini model.

    Returns a dict matching the extraction schema.
    Raises ExtractionError on API failure.
    Never touches the Frappe database (except reading settings and the Item catalog).
    """
    settings = ai_settings.get_settings()

    api_key = resolve_api_key(settings)
    if not api_key:
        raise ExtractionError(
            "Gemini API key not configured. "
            "Set it in 'AI Intake Settings' or run: bench --site narjes.local set-config gemini_api_key YOUR_KEY"
        )

    catalog = get_prompt_catalog(settings)

    model_name = ai_settings.get_str("model_name", settings)
    temperature = ai_settings.get_float("temperature", settings)
    max_tokens = ai_settings.get_int("max_tokens", settings)
    timeout_seconds = ai_settings.get_int("request_timeout", settings)
    max_retries = max(0, ai_settings.get_int("max_retries", settings))

    client = genai.Client(
        api_key=api_key,
        # google-genai takes the request timeout in milliseconds
        http_options=types.HttpOptions(timeout=timeout_seconds * 1000),
    )

    config = types.GenerateContentConfig(
        system_instruction=_build_system_prompt(catalog, settings),
        response_mime_type="application/json",
        response_schema=EXTRACTION_SCHEMA,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )

    response = None
    last_error = None
    attempts_made = 0
    for attempt in range(max_retries + 1):
        attempts_made = attempt + 1
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[raw_text],
                config=config,
            )
            break
        except Exception as e:
            last_error = e
            if attempt == max_retries or not _is_worth_retrying(e):
                break
            # Back off a little between attempts so a rate limit has a
            # chance to clear instead of being hammered
            time.sleep(2 ** attempt)

    if response is None:
        attempts = "1 attempt" if attempts_made == 1 else f"{attempts_made} attempts"
        raise ExtractionError(f"Gemini API call failed after {attempts}: {str(last_error)}")

    # Parse the structured response
    try:
        extracted = json.loads(response.text)
    except Exception as e:
        raise ExtractionError(
            f"Failed to parse Gemini response as JSON: {str(e)}\n"
            f"Raw: {getattr(response, 'text', 'N/A')}"
        )

    # Sanity-check required fields
    if not extracted.get("customer_name") and not extracted.get("phone_numbers"):
        raise ExtractionError("Extraction returned no customer identifier (no name, no phone).")

    return extracted


def is_complete_extraction(extracted: dict) -> bool:
    """
    Returns True if the extraction has enough data to create a Sales Order
    without manual review.

    Needs: (customer_name OR phone) AND at least one item with qty > 0.
    """
    has_customer_id = bool(extracted.get("customer_name")) or bool(extracted.get("phone_numbers"))
    items = extracted.get("order_items") or []
    has_items = any(
        item.get("description") and (item.get("qty") or 0) > 0
        for item in items
    )
    return has_customer_id and has_items
