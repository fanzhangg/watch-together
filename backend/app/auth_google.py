"""Google ID token verification.

Isolated in its own module so tests can monkeypatch ``verify_google_token``
without hitting the network. Verifies the token against Google's public keys
and checks the audience matches our OAuth client id.
"""

from __future__ import annotations

from dataclasses import dataclass

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    name: str | None
    picture: str | None


def verify_google_token(credential: str, client_id: str) -> GoogleIdentity:
    """Verify a Google ID token (the `credential` from Google Identity Services).

    Raises ValueError if the token is invalid or not for our client.
    """
    info = id_token.verify_oauth2_token(
        credential, google_requests.Request(), client_id
    )
    return GoogleIdentity(
        sub=info["sub"],
        email=info["email"],
        name=info.get("name"),
        picture=info.get("picture"),
    )
