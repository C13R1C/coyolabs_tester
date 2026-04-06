import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.controllers.auth_controller import auth_bp
from app.extensions import login_manager


class ChangeEmailTests(unittest.TestCase):
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

    @patch("app.controllers.auth_controller._get_pending_verify_user")
    def test_change_email_requires_pending_user(self, pending_user_mock):
        pending_user_mock.return_value = None

        response = self.client.post("/auth/change-email", json={"email": "24310116@utpn.edu.mx"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json(), {"error": "No hay una cuenta pendiente de verificación en esta sesión."})

    @patch("app.controllers.auth_controller.db")
    @patch("app.controllers.auth_controller.send_verification_email")
    @patch("app.controllers.auth_controller.generate_verify_token", return_value="tok123")
    @patch("app.controllers.auth_controller.User")
    @patch("app.controllers.auth_controller._get_pending_verify_user")
    def test_change_email_updates_and_resends_token(
        self,
        pending_user_mock,
        user_cls,
        token_mock,
        email_mock,
        db_mock,
    ):
        user = MagicMock()
        user.id = 1
        user.email = "old@utpn.edu.mx"
        user.role = "STUDENT"
        user.is_verified = False
        user.verify_token_version = 2
        user.email_change_count = 0
        user.email_change_window_started_at = None
        pending_user_mock.return_value = user

        existing_q = MagicMock()
        existing_q.first.return_value = None
        user_cls.query.filter.return_value = existing_q

        response = self.client.post("/auth/change-email", json={"email": "24310116@utpn.edu.mx"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"message": "Correo actualizado y verificación reenviada."})
        self.assertEqual(user.email, "24310116@utpn.edu.mx")
        self.assertEqual(user.verify_token_version, 3)
        token_mock.assert_called_once_with("24310116@utpn.edu.mx", 3)
        email_mock.assert_called_once()
        db_mock.session.commit.assert_called_once()

    @patch("app.controllers.auth_controller.User")
    @patch("app.controllers.auth_controller._get_pending_verify_user")
    def test_change_email_rate_limit(self, pending_user_mock, user_cls):
        user = MagicMock()
        user.id = 1
        user.email = "old@utpn.edu.mx"
        user.is_verified = False
        user.verify_token_version = 0
        user.email_change_count = 3
        user.email_change_window_started_at = __import__("datetime").datetime.utcnow()
        pending_user_mock.return_value = user

        existing_q = MagicMock()
        existing_q.first.return_value = None
        user_cls.query.filter.return_value = existing_q

        response = self.client.post("/auth/change-email", json={"email": "24310116@utpn.edu.mx"})

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json(), {"error": "Límite alcanzado: máximo 3 cambios de correo por hora."})


if __name__ == "__main__":
    unittest.main()
