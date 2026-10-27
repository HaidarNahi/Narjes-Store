# Copyright (c) 2026, Haidar Nahi and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# Statuses an intake can still be confirmed or discarded from.
OPEN_STATUSES = ("Draft", "Needs Review", "Failed")


class AIOrderIntake(Document):
    def before_insert(self):
        if not self.status:
            self.status = "Draft"

    def validate(self):
        if self.is_new():
            return
        old = self.get_doc_before_save()
        if not old:
            return
        # A confirmed record is the audit trail of an order: never edited.
        if old.status == "Confirmed":
            frappe.throw(
                "A confirmed AI Order Intake record cannot be edited. "
                "If there is an error, create a new intake from the corrected text."
            )
        # A discarded intake stays discarded; process the text again instead.
        if old.status == "Discarded" and self.status != "Discarded":
            frappe.throw(
                "A discarded AI Order Intake cannot be reopened. Paste the order text again to process it."
            )
