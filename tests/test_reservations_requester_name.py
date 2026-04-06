import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.controllers.reservations_controller import _build_requester_name


class RequesterNameTests(unittest.TestCase):
    def test_uses_full_name_first(self):
        user = SimpleNamespace(full_name="  Ada Lovelace  ", email="ada@example.com", id=7)
        with patch("app.controllers.reservations_controller.current_user", user):
            self.assertEqual(_build_requester_name(), "Ada Lovelace")

    def test_falls_back_to_email(self):
        user = SimpleNamespace(full_name="", email="  ada@example.com  ", id=7)
        with patch("app.controllers.reservations_controller.current_user", user):
            self.assertEqual(_build_requester_name(), "ada@example.com")

    def test_falls_back_to_identifier(self):
        user = SimpleNamespace(full_name=None, email=None, id=42)
        with patch("app.controllers.reservations_controller.current_user", user):
            self.assertEqual(_build_requester_name(), "Usuario #42")


if __name__ == "__main__":
    unittest.main()
