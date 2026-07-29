"""
Unit tests for narjes_custom.business_logic — pure Python, zero Frappe DB
dependency, same spirit as ai_intake/tests/test_matching.py. Run via:

    python -m pytest apps/narjes_custom/narjes_custom/tests/test_business_logic.py -v

These cover exactly the functions NARJES_STORE_SYSTEM.md §14.9/§15 called
out as needing a safety net before the staged canvas/sheet/flower costing
automation goes live: delivery fee, canvas/sheet cost, and Sales Revenue
Report profit calculation.
"""

import unittest

from narjes_custom.business_logic import (
    compute_canvas_cost,
    compute_delivery_fee,
    compute_profit,
    compute_profit_percentage,
    compute_sheet_cost,
    is_discount_excessive,
)


class TestComputeDeliveryFee(unittest.TestCase):
    def test_baghdad(self):
        self.assertEqual(compute_delivery_fee('بغداد', 4000, 6000), 4000)

    def test_other_governorate(self):
        self.assertEqual(compute_delivery_fee('البصرة', 4000, 6000), 6000)

    def test_no_governorate(self):
        self.assertEqual(compute_delivery_fee(None, 4000, 6000), 0)
        self.assertEqual(compute_delivery_fee('', 4000, 6000), 0)

    def test_respects_configured_settings_values_not_hardcoded(self):
        # This is the regression this function exists to prevent — see
        # NARJES_STORE_SYSTEM.md §6.2/§14.3: an earlier draft hardcoded
        # 4000/6000 regardless of what Narjes Settings actually held.
        self.assertEqual(compute_delivery_fee('بغداد', 5000, 7000), 5000)
        self.assertEqual(compute_delivery_fee('كربلاء', 5000, 7000), 7000)

    def test_blank_settings_values_default_to_zero(self):
        self.assertEqual(compute_delivery_fee('بغداد', None, None), 0)
        self.assertEqual(compute_delivery_fee('كربلاء', None, None), 0)


class TestComputeCanvasCost(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(compute_canvas_cost(1000, 0.95), 950.0)

    def test_zero_area(self):
        self.assertEqual(compute_canvas_cost(0, 0.95), 0)

    def test_none_values_default_to_zero(self):
        self.assertEqual(compute_canvas_cost(None, 0.95), 0)
        self.assertEqual(compute_canvas_cost(1000, None), 0)


class TestComputeSheetCost(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(compute_sheet_cost(3, 250), 750)

    def test_zero_qty(self):
        self.assertEqual(compute_sheet_cost(0, 250), 0)

    def test_none_values_default_to_zero(self):
        self.assertEqual(compute_sheet_cost(None, 250), 0)
        self.assertEqual(compute_sheet_cost(3, None), 0)


class TestComputeProfit(unittest.TestCase):
    def test_profitable_order(self):
        self.assertEqual(compute_profit(20000, 8000, 2000), 10000)

    def test_loss_making_order(self):
        self.assertEqual(compute_profit(5000, 8000, 2000), -5000)

    def test_none_values_default_to_zero(self):
        self.assertEqual(compute_profit(None, None, None), 0)


class TestComputeProfitPercentage(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(compute_profit_percentage(5000, 10000), 50.0)

    def test_zero_selling_rate_does_not_raise(self):
        # This is the exact guard already present in the shipped report —
        # confirming it stays correct if the surrounding code is refactored.
        self.assertEqual(compute_profit_percentage(0, 0), 0)
        self.assertEqual(compute_profit_percentage(100, 0), 0)

    def test_negative_profit(self):
        self.assertEqual(compute_profit_percentage(-2000, 10000), -20.0)


class TestIsDiscountExcessive(unittest.TestCase):
    def test_within_bound(self):
        self.assertFalse(is_discount_excessive(4000, 10000, 50))

    def test_exactly_at_bound_is_not_excessive(self):
        self.assertFalse(is_discount_excessive(5000, 10000, 50))

    def test_over_bound(self):
        self.assertTrue(is_discount_excessive(6000, 10000, 50))

    def test_zero_subtotal_never_flagged_here(self):
        # A zero/negative subtotal is a different validation problem
        # (confirm_intake already requires at least one item), not
        # something this specific check should raise on.
        self.assertFalse(is_discount_excessive(1000, 0, 50))
        self.assertFalse(is_discount_excessive(1000, -500, 50))

    def test_no_discount(self):
        self.assertFalse(is_discount_excessive(0, 10000, 50))


if __name__ == "__main__":
    unittest.main()
