"""
narjes_custom.ai_intake.extraction
====================================
Gemini 2.5 Flash extraction layer — AI is used ONLY here.
AI never touches the database. All it does is parse raw text → structured dict.

API key must be set in site_config.json:
    bench --site narjes.local set-config gemini_api_key "YOUR_KEY_HERE"
"""

import json

import frappe
from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Dynamic item catalog — always fresh from the Item master
# ---------------------------------------------------------------------------

def get_item_catalog() -> list[dict]:
    """
    Fetch all active, non-disabled items from the Item master.
    Returns list of dicts: [{"name": "Wood Stand", "item_name": "...", "item_group": "..."}]
    """
    return frappe.get_all(
        "Item",
        filters={"disabled": 0},
        fields=["name", "item_name", "item_group"],
        order_by="name asc",
    )


def _build_catalog_for_prompt(catalog: list[dict]) -> str:
    """Format the item catalog as a readable list for the AI prompt."""
    lines = []
    for item in catalog:
        # Show both the item code (name) and the group for disambiguation
        lines.append(f"  - \"{item['name']}\" (group: {item['item_group']})")
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

def _build_system_prompt(catalog: list[dict]) -> str:
    items_list = _build_catalog_for_prompt(catalog)
    few_shot_text = ""
    for i, ex in enumerate(FEW_SHOT_EXAMPLES, 1):
        few_shot_text += (
            f"\n\n--- Example {i} ---\n"
            f"Input:\n{ex['input']}\n\n"
            f"Expected JSON output:\n{json.dumps(ex['output'], ensure_ascii=False, indent=2)}"
        )

    return f"""You are an order intake assistant for a canvas printing business in Iraq.
Your ONLY job is to extract structured order data from informal, messy customer messages.
These messages are typically from WhatsApp and may be in Arabic, English, or mixed.

RULES:
1. Extract ONLY what is explicitly stated. Never guess or hallucinate values.
2. For any field you cannot determine with confidence, use null (or empty array for lists).
3. For delivery_date: if a specific date is mentioned, output it as YYYY-MM-DD. If only a day name (e.g. "Thursday") is mentioned, note it in extraction_notes and set delivery_date to null.
4. For priority: output "High", "Medium", or "Low" only if explicitly mentioned or strongly implied (e.g. "ضروري", "urgent", "عاجل" → "High"). Otherwise null.
5. For gift: true only if explicitly stated (e.g. "هدية", "gift").
6. For currency: default to "IQD" unless USD ($, دولار) is clearly mentioned.

ITEM MATCHING — CRITICAL RULES:
7. For item_code_hint: you MUST match to the MOST SPECIFIC item from the catalog below.
   - ALWAYS prefer a more specific match over a generic one.
   - Example: if the customer says "ستاند خشب" (wooden stand), match to "Wood Stand", NOT to the generic "Stand".
   - Example: if the customer says "ستاند حديد" or "metal stand", match to "Metal Stand", NOT to the generic "Stand".
   - Use the generic "Stand" ONLY if the customer does not specify any type of stand.
   - The item_code_hint value MUST be the EXACT "name" string from the catalog (case-sensitive, character-perfect). Do NOT invent item codes.
   - If NO item in the catalog is a close match, set item_code_hint to null and add a note to extraction_notes explaining what the customer requested.

AVAILABLE ITEM CATALOG:
{items_list}

8. For phone_numbers: extract ALL phone numbers mentioned, include country code if present, do not normalize.
9. Add extraction_notes for EVERY field you were uncertain about.

FEW-SHOT EXAMPLES:{few_shot_text}

Now extract the order data from the user's message and return ONLY valid JSON matching the schema."""


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

class ExtractionError(Exception):
    """Raised when Gemini call fails or returns unusable output."""
    pass


def extract_order(raw_text: str) -> dict:
    """
    Extract structured order data from raw_text using Gemini 2.5 Flash.

    Returns a dict matching the extraction schema.
    Raises ExtractionError on API failure.
    Never touches the Frappe database (except reading Item catalog).
    """
    api_key = frappe.conf.get("gemini_api_key")
    if not api_key:
        raise ExtractionError(
            "Gemini API key not configured. "
            "Run: bench --site narjes.local set-config gemini_api_key YOUR_KEY"
        )

    # Fetch live catalog
    catalog = get_item_catalog()

    client = genai.Client(api_key=api_key)

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[raw_text],
            config=types.GenerateContentConfig(
                system_instruction=_build_system_prompt(catalog),
                response_mime_type="application/json",
                response_schema=EXTRACTION_SCHEMA,
                temperature=0.1,    # Low temperature = more deterministic extraction
                max_output_tokens=4096,
            ),
        )
    except Exception as e:
        raise ExtractionError(f"Gemini API call failed: {str(e)}")

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
