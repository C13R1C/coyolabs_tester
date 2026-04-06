import unittest

from app.utils.statuses import TicketItemStatus


class TicketItemStatusCompatTests(unittest.TestCase):
    def test_requested_alias_maps_to_pending(self):
        self.assertEqual(TicketItemStatus.PENDING, "PENDING")
        self.assertEqual(TicketItemStatus.REQUESTED, TicketItemStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
