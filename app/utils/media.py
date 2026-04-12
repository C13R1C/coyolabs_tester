import os
import re
from urllib.parse import urlsplit, urlunsplit

from flask import current_app, url_for


def normalize_media_ref(raw_ref: str | None) -> str:
    value = (raw_ref or "").strip()
    if not value:
        return ""

    value = value.replace("\\", "/")

    if value.startswith(("http://", "https://")):
        parts = urlsplit(value)
        normalized_path = re.sub(r"/{2,}", "/", parts.path or "")
        return urlunsplit((parts.scheme, parts.netloc, normalized_path, parts.query, parts.fragment))

    value = re.sub(r"/{2,}", "/", value)
    value = re.sub(r"^\./+", "", value)
    return value


def resolve_media_url(raw_ref: str | None, *, ensure_static_file: bool = True) -> str | None:
    normalized = normalize_media_ref(raw_ref)
    if not normalized:
        return None

    if normalized.startswith(("http://", "https://")):
        return normalized

    if normalized.startswith("/uploads/"):
        normalized = f"/static{normalized}"

    if normalized.startswith("/static/"):
        relative = normalized.replace("/static/", "", 1)
        if ensure_static_file:
            abs_path = os.path.join(current_app.root_path, "static", relative)
            if not os.path.exists(abs_path):
                return None
        return f"/static/{relative}"

    if normalized.startswith("static/"):
        relative = normalized.replace("static/", "", 1)
        if ensure_static_file:
            abs_path = os.path.join(current_app.root_path, "static", relative)
            if not os.path.exists(abs_path):
                return None
        return url_for("static", filename=relative)

    if normalized.startswith("/"):
        return normalized

    relative = normalized.lstrip("/")
    if ensure_static_file:
        abs_path = os.path.join(current_app.root_path, "static", relative)
        if not os.path.exists(abs_path):
            return None
    return url_for("static", filename=relative)
