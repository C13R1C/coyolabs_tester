import unittest

from app.services import email_service


class EmailServiceResilienceTests(unittest.TestCase):
    def test_send_verification_email_degrades_when_provider_missing(self):
        self.assertIsNone(email_service.resend)

        with self.assertRaises(RuntimeError) as ctx:
            email_service.send_verification_email("demo@utpn.edu.mx", "https://example.test/verify")

        self.assertIn("Proveedor de correo no disponible", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
