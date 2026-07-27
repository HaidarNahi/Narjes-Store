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

def _build_system_prompt(catalog: list[dict], settings) -> str:
    base_prompt = settings.system_prompt_base or "You are an order intake assistant."
    rules = settings.extraction_rules or ""
    
    prompt = f"{base_prompt}\n\nRULES:\n{rules}"
    
    # Dynamically inject Governorate options so the AI doesn't invent invalid ones
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
    
    if settings.append_catalog:
        items_list = _build_catalog_for_prompt(catalog)
        prompt += f"\n\nAVAILABLE ITEM CATALOG:\n{items_list}"
        
    if settings.append_examples:
        few_shot_text = ""
        for i, ex in enumerate(FEW_SHOT_EXAMPLES, 1):
            few_shot_text += (
                f"\n\n--- Example {i} ---\n"
                f"Input:\n{ex['input']}\n\n"
                f"Expected JSON output:\n{json.dumps(ex['output'], ensure_ascii=False, indent=2)}"
            )
        prompt += f"\n\nFEW-SHOT EXAMPLES:{few_shot_text}"
        
    prompt += "\n\nDISCOUNT RULE: Extract any explicitly mentioned discount amount from the text and place it in the 'discount_amount' field as a number (e.g. 5000 for 5000 IQD discount, or 10000). If no discount is mentioned, use null."
    prompt += "\n\nCUSTOM DETAILS RULE: Extract any additional details, special instructions, custom notes, or unmapped text into the 'custom_details' field as text. If no extra details are mentioned, use null."
    prompt += "\n\nNow extract the order data from the user's message and return ONLY valid JSON matching the schema."
    return prompt


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
    settings = frappe.get_doc("AI Intake Settings")
    
    # Use API key from settings if available, else fallback to site config
    api_key = settings.get_password("api_key") if settings.get("api_key") else frappe.conf.get("gemini_api_key")
    if not api_key:
        raise ExtractionError(
            "Gemini API key not configured. "
            "Set it in 'AI Intake Settings' or run: bench --site narjes.local set-config gemini_api_key YOUR_KEY"
        )

    # Fetch live catalog
    catalog = get_item_catalog()

    client = genai.Client(api_key=api_key)
    
    model_name = settings.model_name or "gemini-2.5-flash"
    temperature = float(settings.temperature) if settings.temperature is not None else 0.1
    max_tokens = int(settings.max_tokens) if settings.max_tokens is not None else 4096

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=[raw_text],
            config=types.GenerateContentConfig(
                system_instruction=_build_system_prompt(catalog, settings),
                response_mime_type="application/json",
                response_schema=EXTRACTION_SCHEMA,
                temperature=temperature,
                max_output_tokens=max_tokens,
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
