"""Storefront guest checkout finds its customer by phone only.

The guest endpoints themselves are known-broken and quarantined (see
test_endpoint_wiring.py); this covers the one change made to them: which
customer a guest order is attached to.
"""

import unittest
from types import SimpleNamespace
from unittest import mock

from narjes_custom.storefront import orders


class Refused(Exception):
    pass


class TestResolveCustomer(unittest.TestCase):
    def run_resolve(self, resolution, phone="٠٧٧٠ ٠٠٠ ٠١٠١"):
        existing = mock.Mock(name="existing customer")
        existing.name = "Old Customer"
        existing.meta.has_field.return_value = True
        existing.get.return_value = "already set"
        new = mock.Mock(name="new customer")
        new.name = "New Customer"
        new.meta.has_field.return_value = True
        fake = SimpleNamespace(
            get_doc=mock.Mock(return_value=existing),
            new_doc=mock.Mock(return_value=new),
            log_error=mock.Mock(),
            throw=mock.Mock(side_effect=Refused),
            _=lambda s: s,
        )
        with mock.patch.object(orders, "frappe", fake), \
             mock.patch.object(orders.customer_phones, "lock_phones") as lock, \
             mock.patch.object(orders.customer_phones, "resolve", return_value=resolution) as resolve:
            result = orders._resolve_customer("Same Name As Someone", phone, "بغداد", "address")
        return result, fake, lock, resolve, new

    def test_existing_owner_of_the_phone(self):
        result, fake, lock, resolve, _new = self.run_resolve({"status": "MATCHED", "customer": "Old Customer", "candidates": []})
        self.assertEqual(result, "Old Customer")
        resolve.assert_called_once_with(["+9647700000101"])
        lock.assert_called_once_with(["+9647700000101"])
        fake.new_doc.assert_not_called()

    def test_new_phone_makes_a_new_customer_whatever_the_name(self):
        result, _fake, _lock, _resolve, new = self.run_resolve({"status": "NEW", "customer": None, "candidates": []})
        self.assertEqual(result, "New Customer")
        new.set.assert_any_call("main_phone_number", "07700000101")
        new.insert.assert_called_once()

    def test_shared_number_is_never_guessed(self):
        with self.assertRaises(Refused):
            self.run_resolve({"status": "CONFLICT", "customer": None, "candidates": ["A", "B"]})

    def test_invalid_phone_is_refused(self):
        with self.assertRaises(Refused):
            self.run_resolve({"status": "NO_PHONE", "customer": None, "candidates": []}, phone="0770 000 01")


if __name__ == "__main__":
    unittest.main()
