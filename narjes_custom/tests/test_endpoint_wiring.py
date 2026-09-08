"""Every whitelisted endpoint is actually reachable.

This suite exists because of a specific, embarrassing failure. On 4 September
2026 a commit about money reports added rate limiting to the storefront and
wrote the decorators in this order:

    @rate_limit(**RATE_PLACE_ORDER)
    @frappe.whitelist(allow_guest=True)
    def place_order(payload): ...

which is backwards. `frappe.whitelist()` registers *the function object it is
handed* in a module-level set; `rate_limit` then wraps it, and the wrapper is
what the module exports. Frappe resolves the wrapper, does not find it in the
set, and refuses the call. Every guest endpoint on the shop returned HTTP 403
for four days, and the pages kept rendering perfectly so nothing looked wrong.

The app had 116 passing tests at the time. Not one of them could have caught
it, because all 116 call pure functions directly and none of them ask the
question this file asks: *is this thing reachable at all?*

That is the real gap these tests close. Every bug that has actually hurt this
project has been a wiring bug — the storefront JS calling `frappe.call` on a
page that never loads Frappe, a fabricated "N/A" item row blocking sheet-only
orders, and this. None were arithmetic. Arithmetic is the part that was
already tested.

No database, no site, no bench: these are import-time and registry-level
assertions, so they run in CI in under a second alongside the existing suite.
"""

import importlib
import inspect
import unittest

import frappe

# --------------------------------------------------------------- known broken
#
# These six are the endpoints described above. They are STILL BROKEN, on
# purpose: as of 8 September 2026 the shop has explicitly deferred all
# storefront work, and the fix — swapping two decorator lines in each — is a
# storefront change.
#
# They are quarantined here rather than deleted, and rather than left failing,
# so that three things stay true at once: the main suite is green, the defect
# is recorded in executable form instead of a stale TODO, and the day someone
# swaps those decorators the xfail turns into an XPASS that says so out loud.
#
# When that happens: move these back into ENDPOINTS and delete
# TestKnownBrokenStorefrontEndpoints.
STOREFRONT_ENDPOINTS_KNOWN_BROKEN = [
    ("narjes_custom.storefront.orders", "quote", True),
    ("narjes_custom.storefront.orders", "place_order", True),
    ("narjes_custom.storefront.orders", "submit_design_request", True),
    ("narjes_custom.storefront.api", "get_items", True),
    ("narjes_custom.storefront.api", "search", True),
    ("narjes_custom.storefront.api", "upload_reference", True),
]

# (module path, function name, must be reachable by a signed-out visitor)
ENDPOINTS = [
    # desk — signed-in only
    ("narjes_custom.api", "get_customer_info", False),
    ("narjes_custom.api", "submit_and_mark_done", False),
    ("narjes_custom.api", "bulk_move_phase", False),
    ("narjes_custom.api", "discard_draft", False),
    ("narjes_custom.api", "cancel_sales_order_and_links", False),
    ("narjes_custom.api", "get_home_dashboard_data", False),
    ("narjes_custom.api", "ensure_narjes_dashboard_workspace", False),
    ("narjes_custom.ai_intake.api", "process_intake", False),
    ("narjes_custom.ai_intake.api", "confirm_intake", False),
    ("narjes_custom.ai_intake.api", "get_item_catalog_endpoint", False),
    ("narjes_custom.ai_intake.api", "get_customers_for_search", False),
    ("narjes_custom.expenses.api", "parse_expense", False),
    ("narjes_custom.expenses.api", "get_expense_summary", False),
    ("narjes_custom.debts", "get_dashboard", False),
    ("narjes_custom.debts", "get_settlements", False),
    ("narjes_custom.salaries", "post_commission_expense", False),
    ("narjes_custom.salaries", "get_dashboard", False),
]


def _resolve(module_path, func_name):
    """Fetch the attribute exactly the way Frappe's request handler does.

    This is the whole point: Frappe calls `frappe.get_attr("module.func")`,
    which returns whatever the module currently exports under that name —
    the outermost decorator's wrapper, not the function you wrote. Importing
    and reading the attribute reproduces that precisely.
    """
    module = importlib.import_module(module_path)
    return getattr(module, func_name, None)


class TestEndpointsAreReachable(unittest.TestCase):
    """The check that the 4 September regression would have failed."""

    def test_every_endpoint_is_whitelisted(self):
        broken = []
        for module_path, func_name, _guest in ENDPOINTS:
            fn = _resolve(module_path, func_name)
            if fn is None:
                broken.append(f"{module_path}.{func_name} — does not exist")
            elif fn not in frappe.whitelisted:
                broken.append(
                    f"{module_path}.{func_name} — exported object is not in "
                    f"frappe.whitelisted (check decorator order: "
                    f"@frappe.whitelist must be the OUTERMOST decorator)"
                )
        self.assertEqual([], broken, "\n  " + "\n  ".join(broken) if broken else "")

    def test_guest_endpoints_allow_guests(self):
        """allow_guest=True has to survive the decorator stack too.

        A endpoint can be in `whitelisted` and still missing from
        `guest_methods`, which fails only for signed-out visitors — i.e. only
        for actual customers, and never for whoever is testing it while logged
        into the desk.
        """
        broken = []
        for module_path, func_name, guest in ENDPOINTS:
            if not guest:
                continue
            fn = _resolve(module_path, func_name)
            if fn is not None and fn not in frappe.guest_methods:
                broken.append(f"{module_path}.{func_name} — not reachable by a guest")
        self.assertEqual([], broken, "\n  " + "\n  ".join(broken) if broken else "")

    def test_desk_endpoints_do_not_allow_guests(self):
        """The inverse mistake: leaking a desk endpoint to the public."""
        leaked = []
        for module_path, func_name, guest in ENDPOINTS:
            if guest:
                continue
            fn = _resolve(module_path, func_name)
            if fn is not None and fn in frappe.guest_methods:
                leaked.append(f"{module_path}.{func_name} — is guest-accessible and should not be")
        self.assertEqual([], leaked, "\n  " + "\n  ".join(leaked) if leaked else "")


class TestDecoratorOrder(unittest.TestCase):
    """Catch the ordering directly, so the failure names its own cause.

    The reachability tests above would fail too, but they say "not
    whitelisted", which sends the next person hunting through permissions.
    This one points straight at the two lines that need swapping.
    """

    def test_rate_limited_endpoints_have_whitelist_outermost(self):
        wrong = []
        for module_path, func_name, _guest in ENDPOINTS:
            fn = _resolve(module_path, func_name)
            if fn is None:
                continue
            # A rate_limit wrapper sets __wrapped__ via functools.wraps. If the
            # exported object is that wrapper AND is not itself whitelisted,
            # the decorators are inverted.
            inner = getattr(fn, "__wrapped__", None)
            if inner is not None and fn not in frappe.whitelisted and inner in frappe.whitelisted:
                wrong.append(
                    f"{module_path}.{func_name} — @frappe.whitelist is under "
                    f"@rate_limit; swap them so whitelist is outermost"
                )
        self.assertEqual([], wrong, "\n  " + "\n  ".join(wrong) if wrong else "")


class TestKnownBrokenStorefrontEndpoints(unittest.TestCase):
    """The six guest endpoints that are known to be unreachable.

    Marked expectedFailure because the fix is deliberately deferred, not
    because the assertion is wrong. If this starts XPASSing, someone has fixed
    the decorator order — delete this class and move the endpoints back into
    ENDPOINTS.
    """

    @unittest.expectedFailure
    def test_storefront_endpoints_are_whitelisted(self):
        broken = []
        for module_path, func_name, _guest in STOREFRONT_ENDPOINTS_KNOWN_BROKEN:
            fn = _resolve(module_path, func_name)
            if fn is None or fn not in frappe.whitelisted:
                broken.append(f"{module_path}.{func_name}")
        self.assertEqual(
            [],
            broken,
            "@frappe.whitelist is under @rate_limit on: " + ", ".join(broken),
        )

    def test_the_known_break_is_still_exactly_what_we_think_it_is(self):
        """Pin the *cause*, so this can't quietly become a different bug.

        expectedFailure only proves something is broken. This proves it is
        broken for the reason recorded above — the inner function is
        whitelisted and the exported wrapper is not — so if the failure mode
        ever changes, that shows up as a real failure rather than hiding
        inside an expected one.
        """
        for module_path, func_name, _guest in STOREFRONT_ENDPOINTS_KNOWN_BROKEN:
            fn = _resolve(module_path, func_name)
            self.assertIsNotNone(fn, f"{module_path}.{func_name} vanished entirely")
            inner = getattr(fn, "__wrapped__", None)
            self.assertIsNotNone(
                inner, f"{module_path}.{func_name} is no longer a wrapped function"
            )
            self.assertIn(
                inner,
                frappe.whitelisted,
                f"{module_path}.{func_name}: the inner function should still be "
                f"whitelisted — if it isn't, this is a different bug now",
            )


class TestScheduledTasksResolve(unittest.TestCase):
    """Every scheduler_events target must import and be callable.

    A scheduled job whose path is wrong does not crash anything — it just
    silently never runs, which is precisely the failure mode the maintenance
    module exists to prevent. Same class of bug, same blind spot.
    """

    def test_scheduler_targets_exist(self):
        from narjes_custom import hooks

        broken = []
        for _freq, paths in (getattr(hooks, "scheduler_events", {}) or {}).items():
            for path in paths:
                module_path, _, func_name = path.rpartition(".")
                fn = _resolve(module_path, func_name)
                if fn is None:
                    broken.append(f"{path} — does not exist")
                elif not callable(fn):
                    broken.append(f"{path} — is not callable")
                elif inspect.signature(fn).parameters:
                    broken.append(f"{path} — scheduler calls this with no arguments")
        self.assertEqual([], broken, "\n  " + "\n  ".join(broken) if broken else "")


class TestDocEventsResolve(unittest.TestCase):
    """Same for doc_events: a typo'd hook silently stops firing."""

    def test_doc_event_targets_exist(self):
        from narjes_custom import hooks

        broken = []
        for doctype, events in (getattr(hooks, "doc_events", {}) or {}).items():
            for event, path in events.items():
                module_path, _, func_name = path.rpartition(".")
                fn = _resolve(module_path, func_name)
                if fn is None:
                    broken.append(f"{doctype}.{event} -> {path} — does not exist")
                elif not callable(fn):
                    broken.append(f"{doctype}.{event} -> {path} — is not callable")
        self.assertEqual([], broken, "\n  " + "\n  ".join(broken) if broken else "")


if __name__ == "__main__":
    unittest.main()
