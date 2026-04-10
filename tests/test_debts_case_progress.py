import unittest
from types import SimpleNamespace

from app.controllers.debts_controller import _case_item_progress


class DebtCaseProgressTests(unittest.TestCase):
    def test_returns_zeroes_for_empty_case(self):
        self.assertEqual(_case_item_progress([]), (0, 0, 0))

    def test_calculates_progress_by_paid_items(self):
        items = [
            SimpleNamespace(original_amount=2, amount=2, remaining_amount=0),
            SimpleNamespace(original_amount=3, amount=3, remaining_amount=1),
            SimpleNamespace(original_amount=1, amount=1, remaining_amount=0),
        ]
        self.assertEqual(_case_item_progress(items), (2, 3, 67))


if __name__ == "__main__":
    unittest.main()
