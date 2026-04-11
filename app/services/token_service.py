from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import current_app


def _serializer() -> URLSafeTimedSerializer:
    secret = current_app.config["SECRET_KEY"]
    salt = current_app.config["SECURITY_PASSWORD_SALT"]
    return URLSafeTimedSerializer(secret_key=secret, salt=salt)


def generate_verify_token(email: str, token_version: int = 0) -> str:
    s = _serializer()
    return s.dumps({"email": email, "token_version": int(token_version)})


def confirm_verify_token(token: str, max_age_seconds: int = 3600) -> dict[str, str | int] | None:
    s = _serializer()
    try:
        data = s.loads(token, max_age=max_age_seconds)
        email = data.get("email")
        if not email:
            return None
        return {
            "email": email,
            "token_version": int(data.get("token_version", 0)),
        }
    except (SignatureExpired, BadSignature):
        return None


def peek_verify_token(token: str) -> dict[str, str | int] | None:
    """Decode verify token payload without max-age validation."""
    s = _serializer()
    try:
        data = s.loads(token)
        email = str(data.get("email") or "").strip().lower()
        if not email:
            return None
        return {
            "email": email,
            "token_version": int(data.get("token_version", 0)),
        }
    except BadSignature:
        return None


def generate_password_reset_token(email: str, password_fingerprint: str) -> str:
    s = _serializer()
    return s.dumps(
        {
            "email": email,
            "password_fingerprint": password_fingerprint,
            "purpose": "password_reset",
        }
    )


def confirm_password_reset_token(token: str, max_age_seconds: int = 3600) -> dict[str, str] | None:
    s = _serializer()
    try:
        data = s.loads(token, max_age=max_age_seconds)
        email = str(data.get("email") or "").strip().lower()
        password_fingerprint = str(data.get("password_fingerprint") or "")
        purpose = str(data.get("purpose") or "")
        if not email or not password_fingerprint or purpose != "password_reset":
            return None
        return {
            "email": email,
            "password_fingerprint": password_fingerprint,
        }
    except (SignatureExpired, BadSignature):
        return None
