import unittest

from app.controllers.reservations_controller import _is_ticket_operable_for_item_updates
from app.utils.statuses import LabTicketStatus


class TicketOperabilityTests(unittest.TestCase):
    def test_operable_statuses_for_item_updates(self):
        self.assertTrue(_is_ticket_operable_for_item_updates(LabTicketStatus.OPEN))
        self.assertTrue(_is_ticket_operable_for_item_updates(LabTicketStatus.READY_FOR_PICKUP))
        self.assertTrue(_is_ticket_operable_for_item_updates(LabTicketStatus.CLOSURE_REQUESTED))

    def test_non_operable_closed_statuses(self):
        self.assertFalse(_is_ticket_operable_for_item_updates(LabTicketStatus.CLOSED))
        self.assertFalse(_is_ticket_operable_for_item_updates(LabTicketStatus.CLOSED_WITH_DEBT))


if __name__ == "__main__":
    unittest.main()
