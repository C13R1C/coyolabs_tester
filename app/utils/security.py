from functools import wraps
from collections import defaultdict, deque
from threading import Lock
from time import time

from flask import request, current_app, jsonify
from flask_login import current_user


_API_RATE_BUCKETS: dict[str, deque] = defaultdict(deque)
_API_RATE_LOCK = Lock()


def _rate_limit_exceeded() -> bool:
    limit = int(current_app.config.get("API_RATE_LIMIT_PER_MINUTE", 120))
    window_seconds = int(current_app.config.get("API_RATE_LIMIT_WINDOW_SECONDS", 60))
    if limit <= 0 or window_seconds <= 0:
        return False

    actor = f"user:{getattr(current_user, 'id', 'anonymous')}" if current_user.is_authenticated else "anonymous"
    source = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
    bucket_key = f"{actor}:{source}"
    now = time()

    with _API_RATE_LOCK:
        bucket = _API_RATE_BUCKETS[bucket_key]
        cutoff = now - window_seconds
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            return True

        bucket.append(now)
    return False


def api_key_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return jsonify({"error": "Unauthorized"}), 401

        if _rate_limit_exceeded():
            return jsonify({"error": "Too Many Requests"}), 429

        return fn(*args, **kwargs)

    return wrapper
