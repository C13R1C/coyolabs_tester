import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.controllers.users_controller import _pending_assignable_roles


class PendingAssignableRolesTests(unittest.TestCase):
    def test_staff_cannot_assign_admin_role(self):
        actor = SimpleNamespace(role="STAFF")
        with patch("app.controllers.users_controller.current_user", actor):
            self.assertEqual(_pending_assignable_roles(), ("TEACHER", "STAFF"))

    def test_admin_can_assign_basic_roles_only(self):
        actor = SimpleNamespace(role="ADMIN")
        with patch("app.controllers.users_controller.current_user", actor):
            self.assertEqual(_pending_assignable_roles(), ("TEACHER", "STAFF"))


if __name__ == "__main__":
    unittest.main()
