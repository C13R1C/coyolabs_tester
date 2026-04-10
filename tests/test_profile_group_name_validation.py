import unittest

from app.controllers.profile_controller import _normalize_group_name


class ProfileGroupNameValidationTests(unittest.TestCase):
    def test_empty_group_is_optional(self):
        self.assertEqual(_normalize_group_name("   "), (None, None))

    def test_valid_group_is_trimmed(self):
        self.assertEqual(_normalize_group_name("  3A  "), ("3A", None))

    def test_group_length_limit(self):
        value = "A" * 81
        normalized, error = _normalize_group_name(value)
        self.assertIsNone(normalized)
        self.assertEqual(error, "El grupo no puede exceder 80 caracteres.")


if __name__ == "__main__":
    unittest.main()
