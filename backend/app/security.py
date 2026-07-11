"""Session cookie: a signed token carrying the user id.

We issue our OWN session (not the Google token) as a signed, timed cookie via
itsdangerous. httponly keeps it away from JS; the signature prevents tampering.
"""

from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import Settings

_SALT = "wt-session-v1"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=_SALT)


def issue_session(settings: Settings, user_id: str) -> str:
    """Return a signed session token for the given user id."""
    return _serializer(settings).dumps(user_id)


def read_session(settings: Settings, token: str) -> str | None:
    """Return the user id from a valid token, or None if invalid/expired."""
    try:
        return _serializer(settings).loads(
            token, max_age=settings.session_max_age_seconds
        )
    except (BadSignature, SignatureExpired):
        return None
