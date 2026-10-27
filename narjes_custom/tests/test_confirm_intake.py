"""Tests for confirm_intake — the server re-checks before an order exists.

Frappe and the phone index are replaced by fakes; what's under test is the
decision logic: which inputs may create a Sales Order, for which customer,
and that nothing is written when a check fails.
"""

import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import mock

from narjes_custom.ai_intake import api

A = "+9647700000101"
B = "+9647800000102"
C = "+9647500000103"


class Refused(Exception):
    pass


def resolution(status, customer=None, candidates=(), owners=None, disabled=(), token="T"):
    return {"status": status, "customer": customer, "candidates": list(candidates), "owners": owners or {},
            "phones": [], "disabled": list(disabled), "token": token}


class Harness:
    def __init__(self, intake_status="Needs Review", detected=(A,), phone_source="template",
                 resolutions=None, owners=None, disabled_customer=False):
        self.intake = SimpleNamespace(
            status=intake_status, created_sales_order="SO-OLD" if intake_status == "Confirmed" else None,
            detected_phones=json.dumps([{"e164": k} for k in detected]), phone_source=phone_source,
        )
        self.resolutions = resolutions or {}
        self.owners_map = owners or {}
        self.so = mock.Mock(name="SO")
        self.so.name = "SO-NEW"
        self.frappe = SimpleNamespace(
            db=SimpleNamespace(
                sql=mock.Mock(), commit=mock.Mock(), set_value=mock.Mock(),
                get_value=mock.Mock(return_value=1 if disabled_customer else 0),
            ),
            get_doc=mock.Mock(return_value=self.intake),
            conf={}, session=SimpleNamespace(user="reviewer@example.com"),
            has_permission=mock.Mock(return_value=True),
            throw=self._throw,
        )
        self.patches = [
            mock.patch.object(api, "frappe", self.frappe),
            mock.patch.object(api, "now_datetime", return_value="2026-10-28 10:00:00"),
            mock.patch.object(api.ai_settings, "get_settings", return_value=None),
            mock.patch.object(api.ai_settings, "get_bool", return_value=False),
            mock.patch.object(api.customer_phones, "lock_phones"),
            mock.patch.object(api.customer_phones, "resolve", side_effect=self._resolve),
            mock.patch.object(api.customer_phones, "owners", side_effect=lambda keys: {k: self.owners_map.get(k, []) for k in keys}),
            mock.patch.object(api.customer_phones, "customer_summary", side_effect=lambda n: {"name": n}),
            mock.patch.object(api, "_build_sales_order", return_value=self.so),
            mock.patch.object(api, "_create_customer", return_value="New Customer"),
            mock.patch.object(api, "_add_phones", return_value=[]),
        ]

    @staticmethod
    def _throw(msg, *a, **kw):
        raise Refused(msg)

    def _resolve(self, keys):
        return self.resolutions[tuple(keys)]

    def confirm(self, **data):
        payload = {"resolution_token": "T", "order": {"order_items": [{"item_code": "X"}]}, **data}
        mocks = {}
        with ExitStack() as stack:
            for p in self.patches:
                m = stack.enter_context(p)
                mocks[getattr(p, "attribute", "")] = m
            self.mocks = mocks
            return api.confirm_intake("AI-INTAKE-1", json.dumps(payload))

    @property
    def wrote_order(self):
        return self.so.insert.called


class TestConfirmIntake(unittest.TestCase):
    def test_matched_customer(self):
        h = Harness(resolutions={(A,): resolution("MATCHED", "X")}, owners={A: ["X"]})
        result = h.confirm(customer_mode="matched", customer="X", phones=["٠٧٧٠٠٠٠٠١٠١"])
        self.assertEqual((result["ok"], result["customer"], result["sales_order"]), (True, "X", "SO-NEW"))
        self.assertTrue(h.wrote_order)
        written = h.frappe.db.set_value.call_args[0][2]
        self.assertEqual((written["status"], written["customer_mode"], written["phone_source"]), ("Confirmed", "matched", "template"))
        h.mocks["lock_phones"].assert_called_once_with([A])

    def test_already_confirmed_returns_the_existing_order(self):
        h = Harness(intake_status="Confirmed")
        result = h.confirm(customer_mode="matched", customer="X", phones=[A])
        self.assertEqual(result, {"ok": False, "reason": "already_confirmed", "sales_order": "SO-OLD"})
        self.assertFalse(h.wrote_order)

    def test_discarded_is_refused(self):
        h = Harness(intake_status="Discarded")
        with self.assertRaises(Refused):
            h.confirm(customer_mode="matched", customer="X", phones=[A])

    def test_customers_changed_since_review(self):
        h = Harness(resolutions={(A,): resolution("MATCHED", "Y", token="NEW-TOKEN")})
        result = h.confirm(customer_mode="new", phones=[A], new_customer={"customer_name": "Z"})
        self.assertEqual((result["ok"], result["reason"]), (False, "resolution_changed"))
        self.assertEqual(result["resolution"]["customer"], "Y")
        self.assertFalse(h.wrote_order)
        self.assertFalse(h.mocks["_create_customer"].called)

    def test_matched_mode_cannot_choose_another_customer(self):
        h = Harness(resolutions={(A,): resolution("MATCHED", "X")}, owners={A: ["X"]})
        with self.assertRaises(Refused):
            h.confirm(customer_mode="matched", customer="Someone Else", phones=[A])
        self.assertFalse(h.wrote_order)

    def test_conflict_pick_one_of_the_owners(self):
        res = resolution("CONFLICT", candidates=["X", "Y"], owners={A: ["X"], C: ["Y"]})
        h = Harness(detected=(A, C), resolutions={(A, C): res}, owners={A: ["X"], C: ["Y"]})
        self.assertEqual(h.confirm(customer_mode="pick", customer="Y", phones=[A, C])["customer"], "Y")
        h = Harness(detected=(A, C), resolutions={(A, C): res}, owners={A: ["X"], C: ["Y"]})
        with self.assertRaises(Refused):
            h.confirm(customer_mode="pick", customer="Z", phones=[A, C])

    def test_new_customer_only_when_nobody_owns_the_phones(self):
        h = Harness(resolutions={(A,): resolution("NEW")}, owners={A: ["New Customer"]})
        result = h.confirm(customer_mode="new", phones=[A], new_customer={"customer_name": "زبون جديد"})
        self.assertEqual((result["customer"], result["created_new_customer"]), ("New Customer", True))
        h.mocks["_create_customer"].assert_called_once_with({"customer_name": "زبون جديد"}, [A])
        h = Harness(resolutions={(A,): resolution("MATCHED", "X")}, owners={A: ["X"]})
        with self.assertRaises(Refused):
            h.confirm(customer_mode="new", phones=[A], new_customer={"customer_name": "زبون جديد"})

    def test_phone_not_in_message_needs_a_reason(self):
        h = Harness(detected=(A,), resolutions={(B,): resolution("MATCHED", "X")}, owners={B: ["X"]})
        with self.assertRaises(Refused):
            h.confirm(customer_mode="matched", customer="X", phones=[B])
        h = Harness(detected=(A,), resolutions={(B,): resolution("MATCHED", "X")}, owners={B: ["X"]})
        h.confirm(customer_mode="matched", customer="X", phones=[B], override_reason="Customer corrected the number on the phone")
        written = h.frappe.db.set_value.call_args[0][2]
        self.assertEqual(written["phone_source"], "reviewer")
        self.assertIn("corrected", written["phone_override_reason"])

    def test_typed_phone_is_fine_when_the_message_had_none(self):
        h = Harness(detected=(), phone_source="none", resolutions={(A,): resolution("MATCHED", "X")}, owners={A: ["X"]})
        h.confirm(customer_mode="matched", customer="X", phones=["0770 000 0101"])
        self.assertEqual(h.frappe.db.set_value.call_args[0][2]["phone_source"], "reviewer")

    def test_free_text_phone_must_be_confirmed(self):
        h = Harness(phone_source="free_text", resolutions={(A,): resolution("MATCHED", "X")}, owners={A: ["X"]})
        with self.assertRaises(Refused):
            h.confirm(customer_mode="matched", customer="X", phones=[A])
        h = Harness(phone_source="free_text", resolutions={(A,): resolution("MATCHED", "X")}, owners={A: ["X"]})
        self.assertTrue(h.confirm(customer_mode="matched", customer="X", phones=[A], phones_confirmed=True)["ok"])

    def test_no_phone_or_invalid_phone_is_refused(self):
        for phones in ([], ["0770 000 01"]):
            with self.subTest(phones=phones):
                h = Harness()
                with self.assertRaises(Refused):
                    h.confirm(customer_mode="new", phones=phones, new_customer={"customer_name": "Z"})
                self.assertFalse(h.wrote_order)

    def test_ownership_is_asserted_before_the_order(self):
        # resolve() says MATCHED but owners() (re-read) says nobody: nothing is ordered.
        h = Harness(resolutions={(A,): resolution("MATCHED", "X")}, owners={})
        with self.assertRaises(Refused) as ctx:
            h.confirm(customer_mode="matched", customer="X", phones=[A])
        self.assertIn("Internal check failed", str(ctx.exception))
        self.assertFalse(h.wrote_order)

    def test_disabled_customer_is_refused(self):
        h = Harness(resolutions={(A,): resolution("MATCHED", "X", disabled=["X"])}, owners={A: ["X"]})
        with self.assertRaises(Refused):
            h.confirm(customer_mode="matched", customer="X", phones=[A])

    def test_existing_customer_with_a_new_number(self):
        res = {(A,): resolution("NEW"), (B,): resolution("MATCHED", "Y")}
        h = Harness(resolutions=res, owners={A: ["Y"]})
        result = h.confirm(customer_mode="add_phone_to_existing", customer="Y", phones=[A], old_phone="0780 000 0102")
        self.assertEqual(result["customer"], "Y")
        h.mocks["_add_phones"].assert_called_once_with("Y", [A])
        h.mocks["lock_phones"].assert_called_once_with([A, B])
        h = Harness(resolutions=res, owners={A: ["Y"]})
        with self.assertRaises(Refused):  # the old number belongs to Y, not Z
            h.confirm(customer_mode="add_phone_to_existing", customer="Z", phones=[A], old_phone="0780 000 0102")

    def test_unknown_mode_is_refused(self):
        h = Harness()
        with self.assertRaises(Refused):
            h.confirm(customer_mode="by_name", customer="X", phones=[A])


if __name__ == "__main__":
    unittest.main()
