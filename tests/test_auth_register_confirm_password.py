import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.controllers.auth_controller import auth_bp
from app.extensions import login_manager
from app.utils.roles import ROLE_PENDING, ROLE_STAFF, ROLE_STUDENT, infer_role_from_email, role_at_least, role_level


class RegisterConfirmPasswordTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config["SECRET_KEY"] = "test-secret"
        self.app.config["TESTING"] = True
        login_manager.init_app(self.app)

        @login_manager.user_loader
        def _load_user(_user_id):
            return None

        self.app.register_blueprint(auth_bp)
        self.client = self.app.test_client()

    @patch("app.controllers.auth_controller.send_verification_email")
    @patch("app.controllers.auth_controller.generate_verify_token", return_value="tok123")
    @patch("app.controllers.auth_controller.db")
    @patch("app.controllers.auth_controller.User")
    def test_register_accepts_legacy_confirm_password_key_when_matches(
        self, user_cls, db_mock, _token_mock, _email_mock
    ):
        user_query = MagicMock()
        user_query.first.return_value = None
        user_cls.query.filter_by.return_value = user_query

        response = self.client.post(
            "/auth/register",
            json={
                "email": "24310116@utpn.edu.mx",
                "password": "secreto123",
                "accept_terms": True,
                "confirmPassword": "secreto123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/?mode=login", response.location)
        user_cls.assert_called_once_with(email="24310116@utpn.edu.mx", role=ROLE_STUDENT, is_verified=False)
        db_mock.session.add.assert_called_once()
        self.assertGreaterEqual(db_mock.session.commit.call_count, 1)

    def test_register_returns_400_when_confirm_password_missing(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": "24310116@utpn.edu.mx",
                "password": "secreto123",
                "accept_terms": True,
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "confirm_password es obligatorio."})

    def test_register_returns_400_when_confirm_password_does_not_match(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": "24310116@utpn.edu.mx",
                "password": "secreto123",
                "accept_terms": True,
                "confirm_password": "otra123",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Las contraseñas no coinciden."})

    def test_infer_role_from_email_assigns_student_for_matricula(self):
        self.assertEqual(infer_role_from_email("24310116@utpn.edu.mx"), ROLE_STUDENT)

    def test_infer_role_from_email_assigns_pending_for_nominal_email(self):
        self.assertEqual(infer_role_from_email("wendy.nevarez@utpn.edu.mx"), ROLE_PENDING)

    @patch("app.controllers.auth_controller.send_verification_email")
    @patch("app.controllers.auth_controller.generate_verify_token", return_value="tok123")
    @patch("app.controllers.auth_controller.db")
    @patch("app.controllers.auth_controller.User")
    def test_register_nominal_email_creates_pending_user(
        self, user_cls, db_mock, _token_mock, _email_mock
    ):
        user_query = MagicMock()
        user_query.first.return_value = None
        user_cls.query.filter_by.return_value = user_query

        response = self.client.post(
            "/auth/register",
            json={
                "email": "wendy.nevarez@utpn.edu.mx",
                "password": "secreto123",
                "accept_terms": True,
                "confirm_password": "secreto123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/?mode=login", response.location)
        user_cls.assert_called_once_with(
            email="wendy.nevarez@utpn.edu.mx",
            role=ROLE_PENDING,
            is_verified=False,
        )
        db_mock.session.add.assert_called_once()
        self.assertGreaterEqual(db_mock.session.commit.call_count, 1)

    def test_role_helpers_support_legacy_aliases(self):
        self.assertEqual(role_level(ROLE_STUDENT), role_level(ROLE_STUDENT))
        self.assertTrue(role_at_least("ADMIN", ROLE_STAFF))
        self.assertTrue(role_at_least("ADMIN", "TEACHER"))
        self.assertFalse(role_at_least(ROLE_STUDENT, ROLE_STAFF))

    def test_register_returns_400_when_accept_terms_missing(self):
        response = self.client.post(
            "/auth/register",
            json={
                "email": "24310116@utpn.edu.mx",
                "password": "secreto123",
                "confirm_password": "secreto123",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": "Debes aceptar el Aviso de privacidad y los Términos y condiciones."},
        )


if __name__ == "__main__":
    unittest.main()
