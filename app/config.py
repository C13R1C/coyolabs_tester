import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    ENV = (os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development")) or "development").strip().lower()

    SECRET_KEY = (os.getenv("SECRET_KEY") or "dev-secret").strip()
    SECURITY_PASSWORD_SALT = (os.getenv("SECURITY_PASSWORD_SALT") or "dev-salt").strip()

    DB_USER = (os.getenv("DB_USER") or "postgres").strip()
    DB_PASSWORD = (os.getenv("DB_PASSWORD") or "raspi").strip()
    DB_HOST = (os.getenv("DB_HOST") or "localhost").strip()
    DB_PORT = (os.getenv("DB_PORT") or "5432").strip()
    DB_NAME = (os.getenv("DB_NAME") or "lab_system").strip()

    SQLALCHEMY_DATABASE_URI = (
        f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    RESEND_API_KEY = (os.getenv("RESEND_API_KEY") or "").strip()
    MAIL_DEFAULT_SENDER = (os.getenv("MAIL_DEFAULT_SENDER") or "").strip()

    APP_BASE_URL = (
        os.getenv("APP_BASE_URL") or "http://127.0.0.1:5000"
    ).strip().rstrip("/")

    RA_API_KEY = (os.getenv("RA_API_KEY") or "dev-ra-key-cambia-esto").strip()
    VAPID_PUBLIC_KEY = (os.getenv("VAPID_PUBLIC_KEY") or "").strip()
    VAPID_PRIVATE_KEY = (os.getenv("VAPID_PRIVATE_KEY") or "").strip()
    VAPID_CLAIMS_SUBJECT = (os.getenv("VAPID_CLAIMS_SUBJECT") or "mailto:admin@coyolabs.local").strip()

    _INSECURE_DEFAULTS = {
        "SECRET_KEY": "dev-secret",
        "SECURITY_PASSWORD_SALT": "dev-salt",
        "RA_API_KEY": "dev-ra-key-cambia-esto",
    }

    if ENV not in {"development", "dev", "local", "test", "testing"}:
        for _name, _default in _INSECURE_DEFAULTS.items():
            if (os.getenv(_name) or _default).strip() == _default:
                raise RuntimeError(
                    f"Configuración insegura: {_name} usa valor por defecto en entorno '{ENV}'."
                )

    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
