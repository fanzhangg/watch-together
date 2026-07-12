"""M4 tests: invite creation, preview, and accept.

The headline test is the full join flow: Alice invites, Bob accepts, and Bob —
who was previously getting 403 everywhere — can now read and edit the list.
That's the whole point of the app, so it's asserted end to end.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import crud
from app.models import Invite, User


@pytest.fixture
def alice(make_user: Callable[..., User]) -> User:
    return make_user("alice@example.com", "Alice")


@pytest.fixture
def bob(make_user: Callable[..., User]) -> User:
    return make_user("bob@example.com", "Bob")


def _new_list(client: TestClient, name: str = "Date night") -> str:
    return client.post("/api/lists", json={"name": name}).json()["id"]


def test_full_join_flow(
    client_factory: Callable[..., TestClient], alice: User, bob: User
) -> None:
    """Alice invites Bob; Bob joins and can then edit the list."""
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)

    # Before the invite, Bob is a stranger.
    assert cb.get(f"/api/lists/{lid}").status_code == 403

    invite = ca.post(f"/api/lists/{lid}/invites", json={})
    assert invite.status_code == 201
    code = invite.json()["code"]
    assert invite.json()["url"].endswith(f"/invite/{code}")

    # Bob previews it without being a member (and without even being logged in).
    preview = client_factory().get(f"/api/invites/{code}")
    assert preview.status_code == 200
    assert preview.json()["list_name"] == "Date night"
    assert preview.json()["invited_by"] == "Alice"

    accepted = cb.post(f"/api/invites/{code}/accept")
    assert accepted.status_code == 200
    assert accepted.json()["id"] == lid
    assert accepted.json()["role"] == "member"

    # Bob is now a real member: the list shows up and he can edit its movies.
    assert [x["id"] for x in cb.get("/api/lists").json()] == [lid]
    assert cb.get(f"/api/lists/{lid}").status_code == 200
    assert cb.get(f"/api/lists/{lid}/items").status_code == 200

    members = {m["user"]["email"]: m["role"] for m in cb.get(f"/api/lists/{lid}").json()["members"]}
    assert members == {"alice@example.com": "owner", "bob@example.com": "member"}


def test_accept_is_idempotent_and_never_demotes_owner(
    client_factory: Callable[..., TestClient], alice: User, bob: User
) -> None:
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    code = ca.post(f"/api/lists/{lid}/invites", json={}).json()["code"]

    assert cb.post(f"/api/invites/{code}/accept").json()["role"] == "member"
    # Accepting twice is a no-op, not a duplicate membership / 500.
    assert cb.post(f"/api/invites/{code}/accept").json()["role"] == "member"
    assert len(cb.get(f"/api/lists/{lid}").json()["members"]) == 2

    # The owner clicking her own link must NOT demote her to a plain member.
    assert ca.post(f"/api/invites/{code}/accept").json()["role"] == "owner"
    assert len(ca.get(f"/api/lists/{lid}").json()["members"]) == 2


def test_accept_requires_login(
    client_factory: Callable[..., TestClient], alice: User
) -> None:
    ca = client_factory(alice)
    lid = _new_list(ca)
    code = ca.post(f"/api/lists/{lid}/invites", json={}).json()["code"]

    assert client_factory().post(f"/api/invites/{code}/accept").status_code == 401


def test_stranger_cannot_create_invite(
    client_factory: Callable[..., TestClient], alice: User, bob: User
) -> None:
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    # Bob isn't a member, so he can't mint links to Alice's list.
    assert cb.post(f"/api/lists/{lid}/invites", json={}).status_code == 403


def test_unknown_code_is_404(
    client_factory: Callable[..., TestClient], alice: User
) -> None:
    cb = client_factory(alice)
    assert cb.get("/api/invites/not-a-real-code").status_code == 404
    assert cb.post("/api/invites/not-a-real-code/accept").status_code == 404


def test_expired_invite_is_410(
    client_factory: Callable[..., TestClient],
    db_session: Session,
    alice: User,
    bob: User,
) -> None:
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    code = ca.post(f"/api/lists/{lid}/invites", json={"expires_in_days": 1}).json()[
        "code"
    ]

    # Backdate it past expiry.
    invite = crud.get_invite_by_code(db_session, code)
    assert invite is not None
    invite.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()

    assert cb.get(f"/api/invites/{code}").status_code == 410
    assert cb.post(f"/api/invites/{code}/accept").status_code == 410
    # And it did not sneak Bob in.
    assert cb.get(f"/api/lists/{lid}").status_code == 403


def test_invite_codes_are_unguessable(
    client_factory: Callable[..., TestClient], alice: User
) -> None:
    """The code is the only thing protecting the list — it must be long and
    random, not sequential."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    codes = {
        ca.post(f"/api/lists/{lid}/invites", json={}).json()["code"] for _ in range(5)
    }
    assert len(codes) == 5  # all distinct
    assert all(len(c) >= 20 for c in codes)


def test_invite_dies_with_its_list(
    client_factory: Callable[..., TestClient],
    db_session: Session,
    alice: User,
    bob: User,
) -> None:
    """Deleting a list must not leave a live invite pointing at nothing."""
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    code = ca.post(f"/api/lists/{lid}/invites", json={}).json()["code"]

    assert ca.delete(f"/api/lists/{lid}").status_code == 204

    assert cb.get(f"/api/invites/{code}").status_code == 404
    assert cb.post(f"/api/invites/{code}/accept").status_code == 404
    assert db_session.query(Invite).count() == 0  # cascaded away
