"""Tests for narjes_custom.customer_phones — who owns a phone number.

No database: a small in-memory stand-in answers the few queries the module
makes. All customers and numbers are invented.
"""

import unittest
from types import SimpleNamespace
from typing import ClassVar
from unittest import mock

from narjes_custom import customer_phones as cp

A = "+9647700000101"
B = "+9647800000102"
C = "+9647500000103"


class FakeFrappe:
    """Just enough of `frappe` for customer_phones."""

    def __init__(self, customers, index_ready=False):
        # customers: {name: {"main_phone_number": .., "secondary_phone_number": .., "disabled": 0}}
        self.customers = customers
        self.default = cp.PHONE_INDEX_VERSION if index_ready else None
        self.sql_calls = []
        self.after_commit = mock.Mock()
        self.after_rollback = mock.Mock()
        self.local = SimpleNamespace(site="test.site", narjes_phone_locks=None)
        self.db = SimpleNamespace(
            get_default=lambda key: self.default,
            sql=self._sql,
            after_commit=self.after_commit,
            after_rollback=self.after_rollback,
        )
        self.utils = SimpleNamespace(get_link_to_form=lambda doctype, name: name)
        self.ValidationError = cp.frappe.ValidationError

    def _sql(self, query, values=None):
        self.sql_calls.append((query, values))
        return [[1]]

    def _row(self, name):
        data = self.customers[name]
        keys = cp.customer_keys(data)
        return SimpleNamespace(
            name=name,
            main_phone_number=data.get("main_phone_number"),
            secondary_phone_number=data.get("secondary_phone_number"),
            custom_main_phone_e164=keys[0],
            custom_secondary_phone_e164=keys[1],
            get=lambda f, _d=data: _d.get(f),
        )

    def get_all(self, doctype, filters=None, or_filters=None, fields=None, pluck=None, **kw):
        names = list(self.customers)
        if filters and "disabled" in filters:
            wanted = set(filters["name"][1])
            return [n for n in names if n in wanted and self.customers[n].get("disabled")]
        rows = [self._row(n) for n in names]
        if or_filters:
            keys = set(or_filters[0][2])
            rows = [r for r in rows if r.custom_main_phone_e164 in keys or r.custom_secondary_phone_e164 in keys]
        return rows

    @staticmethod
    def throw(msg, exc=None, title=None):
        raise (exc or Exception)(msg)


def patched(customers, index_ready=False):
    fake = FakeFrappe(customers, index_ready)
    return fake, mock.patch.multiple(cp, frappe=fake, _=lambda s: s)


class TestResolve(unittest.TestCase):
    CUSTOMERS: ClassVar[dict] = {
        "X": {"main_phone_number": "07700000101", "secondary_phone_number": "0780 000 0102"},
        "Y": {"main_phone_number": "+964 750 000 0103"},
        "D1": {"main_phone_number": "07700000105"},
        "D2": {"main_phone_number": "٠٧٧٠٠٠٠٠١٠٥"},
        "Off": {"main_phone_number": "07700000106", "disabled": 1},
    }

    def run_both(self, keys):
        """Same answer from the indexed path and the raw-field path."""
        answers = []
        for ready in (True, False):
            _fake, patch = patched(self.CUSTOMERS, index_ready=ready)
            with patch:
                answers.append(cp.resolve(keys))
        self.assertEqual(answers[0], answers[1])
        return answers[0]

    def test_no_phone(self):
        self.assertEqual(self.run_both([])["status"], "NO_PHONE")

    def test_new(self):
        r = self.run_both(["+9647700000199"])
        self.assertEqual((r["status"], r["customer"]), ("NEW", None))

    def test_matched_by_main_or_secondary(self):
        self.assertEqual(self.run_both([A])["customer"], "X")
        self.assertEqual(self.run_both([B])["customer"], "X")
        r = self.run_both([A, B])
        self.assertEqual((r["status"], r["customer"]), ("MATCHED", "X"))

    def test_extra_unowned_phone_still_matches(self):
        r = self.run_both([A, "+9647700000199"])
        self.assertEqual((r["status"], r["customer"]), ("MATCHED", "X"))

    def test_two_owners_is_a_conflict(self):
        r = self.run_both([A, C])
        self.assertEqual((r["status"], r["candidates"]), ("CONFLICT", ["X", "Y"]))

    def test_legacy_shared_number_is_a_conflict(self):
        r = self.run_both(["+9647700000105"])
        self.assertEqual((r["status"], r["candidates"]), ("CONFLICT", ["D1", "D2"]))

    def test_disabled_customer_is_flagged(self):
        r = self.run_both(["+9647700000106"])
        self.assertEqual((r["status"], r["customer"], r["disabled"]), ("MATCHED", "Off", ["Off"]))

    def test_token_is_stable_and_changes_with_owners(self):
        t1 = self.run_both([A])["token"]
        self.assertEqual(t1, self.run_both([A])["token"])
        changed = dict(self.CUSTOMERS, Z={"main_phone_number": "07700000101"})
        _fake, patch = patched(changed)
        with patch:
            self.assertNotEqual(t1, cp.resolve([A])["token"])

    def test_names_never_matter(self):
        # resolve() only ever sees phone keys; there is no name argument at all.
        import inspect

        self.assertEqual(list(inspect.signature(cp.resolve).parameters), ["keys"])


class FakeDoc:
    def __init__(self, name, values, before=None):
        self.name = name
        self.values = dict(values)
        self._before = before
        self.meta = SimpleNamespace(get_label=lambda f: f)

    def get(self, field):
        return self.values.get(field)

    def set(self, field, value):
        self.values[field] = value

    def is_new(self):
        return self._before is None

    def get_doc_before_save(self):
        return None if self._before is None else SimpleNamespace(get=self._before.get)


class TestCustomerValidate(unittest.TestCase):
    CUSTOMERS: ClassVar[dict] = {
        "X": {"main_phone_number": "07700000101"},
        "Legacy": {"main_phone_number": "077000001019"},  # invalid, from before the rule
    }

    def validate(self, doc):
        fake, patch = patched(self.CUSTOMERS, index_ready=True)
        with patch:
            cp.on_customer_validate(doc)
        return fake

    def test_new_customer_with_free_number_gets_keys(self):
        doc = FakeDoc("New", {"main_phone_number": "٠٧٨٠ ٠٠٠ ٠١٠٢", "secondary_phone_number": ""})
        fake = self.validate(doc)
        self.assertEqual(doc.values["custom_main_phone_e164"], B)
        self.assertIsNone(doc.values["custom_secondary_phone_e164"])
        self.assertEqual([c[1][0] for c in fake.sql_calls], ["nphone:test.site:" + B])

    def test_new_customer_with_owned_number_is_refused(self):
        doc = FakeDoc("New", {"main_phone_number": "0770 000 0101"})
        with self.assertRaises(cp.DuplicatePhoneError):
            self.validate(doc)

    def test_owned_number_as_secondary_is_refused(self):
        doc = FakeDoc("New", {"main_phone_number": "07800000102", "secondary_phone_number": "+9647700000101"})
        with self.assertRaises(cp.DuplicatePhoneError):
            self.validate(doc)

    def test_invalid_new_number_is_refused(self):
        doc = FakeDoc("New", {"main_phone_number": "0770 000 01"})
        with self.assertRaises(Exception) as ctx:
            self.validate(doc)
        self.assertIn("not a valid phone number", str(ctx.exception))

    def test_same_number_twice_is_refused(self):
        doc = FakeDoc("New", {"main_phone_number": "07800000102", "secondary_phone_number": "0780 000 0102"})
        with self.assertRaises(Exception) as ctx:
            self.validate(doc)
        self.assertIn("same number", str(ctx.exception))

    def test_saving_own_unchanged_number_is_fine(self):
        doc = FakeDoc("X", {"main_phone_number": "07700000101"}, before={"main_phone_number": "07700000101"})
        fake = self.validate(doc)
        self.assertEqual(doc.values["custom_main_phone_e164"], A)
        self.assertEqual(fake.sql_calls, [])  # nothing changed, nothing locked

    def test_legacy_invalid_number_does_not_block_other_edits(self):
        doc = FakeDoc("Legacy", {"main_phone_number": "077000001019"}, before={"main_phone_number": "077000001019"})
        self.validate(doc)
        self.assertIsNone(doc.values["custom_main_phone_e164"])

    def test_changing_to_an_owned_number_is_refused(self):
        doc = FakeDoc("Legacy", {"main_phone_number": "07700000101"}, before={"main_phone_number": "077000001019"})
        with self.assertRaises(cp.DuplicatePhoneError):
            self.validate(doc)

    def test_clearing_a_number_locks_it(self):
        # an intake confirming against the old number must wait for this save
        doc = FakeDoc("X", {"main_phone_number": ""}, before={"main_phone_number": "07700000101"})
        fake = self.validate(doc)
        self.assertIsNone(doc.values["custom_main_phone_e164"])
        self.assertEqual([c[1][0] for c in fake.sql_calls], ["nphone:test.site:" + A])

    def test_replacing_a_number_locks_old_and_new(self):
        doc = FakeDoc("X", {"main_phone_number": "07800000102"}, before={"main_phone_number": "07700000101"})
        fake = self.validate(doc)
        locked = [c[1][0] for c in fake.sql_calls if c[0].startswith("SELECT GET_LOCK")]
        self.assertEqual(locked, ["nphone:test.site:" + A, "nphone:test.site:" + B])


class TestLocks(unittest.TestCase):
    def test_locks_sorted_short_and_released_once_registered(self):
        fake, patch = patched({})
        with patch:
            cp.lock_phones([C, A, A, None])
            cp.lock_phones([B])
            names = [c[1][0] for c in fake.sql_calls]
            # sorted within each call (C's key sorts before A's), duplicates and None dropped
            self.assertEqual(names, ["nphone:test.site:" + C, "nphone:test.site:" + A, "nphone:test.site:" + B])
            self.assertTrue(all(len(n) <= 64 for n in names))
            self.assertEqual(fake.after_commit.add.call_count, 1)
            self.assertEqual(fake.after_rollback.add.call_count, 1)
            cp._release_locks()
            released = [c[1][0] for c in fake.sql_calls if "RELEASE_LOCK" in c[0]]
            self.assertEqual(sorted(released), sorted(names))
            self.assertIsNone(fake.local.narjes_phone_locks)

    def test_busy_lock_is_refused(self):
        fake, patch = patched({})
        fake.db.sql = lambda q, v=None: [[0]]
        with patch, self.assertRaises(cp.PhoneLockError):
            cp.lock_phones([A])


if __name__ == "__main__":
    unittest.main()
