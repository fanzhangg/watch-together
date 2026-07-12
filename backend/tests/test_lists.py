"""M2 tests: list CRUD, "my lists" scoping, and membership access control.

The central guarantee: a non-member gets 403 on every /lists/{id} route, and
owner-only actions (rename, delete) reject non-owner members.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ROLE_MEMBER, ListMember, User


@pytest.fixture
def alice(make_user: Callable[..., User]) -> User:
    return make_user("alice@example.com", "Alice")


@pytest.fixture
def bob(make_user: Callable[..., User]) -> User:
    return make_user("bob@example.com", "Bob")


def _add_member(db: Session, list_id: str, user: User, role: str = ROLE_MEMBER) -> None:
    db.add(ListMember(list_id=uuid.UUID(list_id), user_id=user.id, role=role))
    db.commit()


def test_lists_requires_auth(client_factory: Callable[..., TestClient]) -> None:
    assert client_factory().get("/api/lists").status_code == 401


def test_create_list_and_scoping(
    client_factory: Callable[..., TestClient], alice: User, bob: User
) -> None:
    ca, cb = client_factory(alice), client_factory(bob)

    created = ca.post("/api/lists", json={"name": "Date night"})
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "Date night"
    assert body["role"] == "owner"
    assert body["owner_id"] == str(alice.id)

    # Alice sees her list; Bob (not a member) does not.
    assert [x["id"] for x in ca.get("/api/lists").json()] == [body["id"]]
    assert cb.get("/api/lists").json() == []


def test_stranger_gets_403_everywhere(
    client_factory: Callable[..., TestClient], alice: User, bob: User
) -> None:
    ca, cb = client_factory(alice), client_factory(bob)
    lid = ca.post("/api/lists", json={"name": "Horror"}).json()["id"]

    assert cb.get(f"/api/lists/{lid}").status_code == 403
    assert cb.patch(f"/api/lists/{lid}", json={"name": "hax"}).status_code == 403
    assert cb.delete(f"/api/lists/{lid}").status_code == 403


def test_non_owner_member_can_view_but_not_mutate(
    client_factory: Callable[..., TestClient],
    db_session: Session,
    alice: User,
    bob: User,
) -> None:
    ca, cb = client_factory(alice), client_factory(bob)
    lid = ca.post("/api/lists", json={"name": "Shared"}).json()["id"]
    _add_member(db_session, lid, bob)

    # Bob is a member now: he can view and appears in the member list.
    detail = cb.get(f"/api/lists/{lid}")
    assert detail.status_code == 200
    roles = {m["user"]["email"]: m["role"] for m in detail.json()["members"]}
    assert roles == {"alice@example.com": "owner", "bob@example.com": "member"}

    # But owner-only actions are forbidden for a plain member.
    assert cb.patch(f"/api/lists/{lid}", json={"name": "x"}).status_code == 403
    assert cb.delete(f"/api/lists/{lid}").status_code == 403


def test_owner_can_rename_and_delete(
    client_factory: Callable[..., TestClient], alice: User
) -> None:
    ca = client_factory(alice)
    lid = ca.post("/api/lists", json={"name": "Old"}).json()["id"]

    renamed = ca.patch(f"/api/lists/{lid}", json={"name": "New"})
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "New"

    assert ca.delete(f"/api/lists/{lid}").status_code == 204
    # Gone -> membership no longer resolves -> 403.
    assert ca.get(f"/api/lists/{lid}").status_code == 403
