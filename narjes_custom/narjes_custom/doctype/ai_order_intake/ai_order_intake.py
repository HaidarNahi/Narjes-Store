# Copyright (c) 2026, Haidar Nahi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AIOrderIntake(Document):
    def before_insert(self):
        if not self.status:
            self.status = "Draft"

    def validate(self):
        # Prevent manual editing of confirmed records
        if self.is_new():
            return
        if self.status == "Confirmed" and self.get_doc_before_save():
            old = self.get_doc_before_save()
            if old.status == "Confirmed":
                frappe.throw(
                    "A confirmed AI Order Intake record cannot be edited. "
                    "If there is an error, create a new intake from the corrected text."
                )
