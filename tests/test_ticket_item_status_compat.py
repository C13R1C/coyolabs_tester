import unittest

from app.utils.statuses import TicketItemStatus


class TicketItemStatusCompatTests(unittest.TestCase):
    def test_requested_alias_maps_to_pending(self):
        self.assertEqual(TicketItemStatus.PENDING, "PENDING")
        self.assertEqual(TicketItemStatus.REQUESTED, TicketItemStatus.PENDING)

    def test_ready_and_missing_aliases_map_to_valid_db_statuses(self):
        self.assertEqual(TicketItemStatus.READY_FOR_PICKUP, TicketItemStatus.PENDING)
        self.assertEqual(TicketItemStatus.MISSING, TicketItemStatus.DELIVERED)


if __name__ == "__main__":
    unittest.main()
