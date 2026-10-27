"""Raise AI Intake Settings' output budget from 4096 to 8192 tokens.

Gemini 3 models count their thinking tokens against max_output_tokens and
cannot turn thinking off, so 4096 left too little room: one production reply
came back cut off after 370 characters of JSON. Only the old default is
changed — a value someone chose on purpose is left alone.
"""

import frappe


def execute():
    if frappe.db.get_single_value("AI Intake Settings", "max_tokens") == 4096:
        frappe.db.set_single_value("AI Intake Settings", "max_tokens", 8192)
