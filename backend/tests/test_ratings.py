"""M8 tests: thumbs up / thumbs down.

Two properties carry this milestone, and neither is visible by hand:

1. **Isolation.** A verdict is scoped to a list item, so it belongs to the list
   it was made in. The same film in a different list carries its own, separate
   verdicts, and nothing recorded in one list can surface in another.

2. **Decoupling.** A verdict and a watch status are independent facts with
   different owners (docs/design.md §12). Marking watched or un-watching must
   leave every verdict alone. Asserted directly rather than assumed, because the
   earlier designs of this feature all coupled them.

TMDB is mocked; each tmdb_id yields its own distinct film so a list can hold
several.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ItemRating, User
from app.tmdb import Movie

DUNE = 693134
BLADE_RUNNER = 335984


def _movie(tmdb_id: int) -> Movie:
    return Movie(
        tmdb_id=tmdb_id,
        title=f"Film {tmdb_id}",
        release_year=2024,
        poster_path=None,
        overview=None,
    )


@pytest.fixture
def mock_tmdb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.routers.items.get_movie", lambda key, tmdb_id: _movie(tmdb_id)
    )


@pytest.fixture
def alice(make_user: Callable[..., User]) -> User:
    return make_user("alice@example.com", "Alice")


@pytest.fixture
def bob(make_user: Callable[..., User]) -> User:
    return make_user("bob@example.com", "Bob")


@pytest.fixture
def carol(make_user: Callable[..., User]) -> User:
    return make_user("carol@example.com", "Carol")


def _new_list(client: TestClient, name: str = "Date night") -> str:
    return client.post("/api/lists", json={"name": name}).json()["id"]


def _add(client: TestClient, list_id: str, tmdb_id: int = DUNE) -> str:
    resp = client.post(f"/api/lists/{list_id}/items", json={"tmdb_id": tmdb_id})
    assert resp.status_code in (200, 201), resp.text
    return resp.json()["id"]


def _join(
    owner: TestClient, joiner: TestClient, list_id: str
) -> None:
    code = owner.post(f"/api/lists/{list_id}/invites", json={}).json()["code"]
    assert joiner.post(f"/api/invites/{code}/accept").status_code == 200


def _ratings(client: TestClient, list_id: str, item_id: str) -> list[dict]:
    resp = client.get(f"/api/lists/{list_id}/items/{item_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()["ratings"]


# --- The write path ------------------------------------------------------
def test_put_records_a_verdict_and_flipping_keeps_one_row(
    client_factory: Callable[..., TestClient],
    db_session: Session,
    alice: User,
    mock_tmdb: None,
) -> None:
    """Up, then down, is an update — never a second row."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    item = _add(ca, lid)

    up = ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": 1})
    assert up.status_code == 200
    assert up.json() == {"item_id": item, "value": 1}

    down = ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": -1})
    assert down.status_code == 200
    assert down.json()["value"] == -1

    rows = db_session.execute(select(ItemRating)).scalars().all()
    assert len(rows) == 1
    assert rows[0].value == -1
    assert _ratings(ca, lid, item) == [{"user_id": str(alice.id), "value": -1}]


def test_delete_clears_and_is_idempotent(
    client_factory: Callable[..., TestClient],
    alice: User,
    mock_tmdb: None,
) -> None:
    """Tapping your own thumb again takes it back; doing it twice is fine."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    item = _add(ca, lid)
    ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": 1})

    assert ca.delete(f"/api/lists/{lid}/items/{item}/rating").status_code == 204
    assert _ratings(ca, lid, item) == []

    # Nothing to clear is the requested end state either way.
    assert ca.delete(f"/api/lists/{lid}/items/{item}/rating").status_code == 204


@pytest.mark.parametrize("value", [0, 2, -2, "up", None])
def test_only_plus_and_minus_one_are_accepted(
    client_factory: Callable[..., TestClient],
    alice: User,
    mock_tmdb: None,
    value: object,
) -> None:
    """"No opinion" is the absence of a row, never a third value."""
    ca = client_factory(alice)
    lid = _new_list(ca)
    item = _add(ca, lid)

    resp = ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": value})
    assert resp.status_code == 422


def test_rating_requires_membership_and_a_session(
    client_factory: Callable[..., TestClient],
    alice: User,
    carol: User,
    mock_tmdb: None,
) -> None:
    ca = client_factory(alice)
    lid = _new_list(ca)
    item = _add(ca, lid)
    path = f"/api/lists/{lid}/items/{item}/rating"

    assert client_factory(carol).put(path, json={"value": 1}).status_code == 403
    assert client_factory(carol).delete(path).status_code == 403
    assert client_factory().put(path, json={"value": 1}).status_code == 401


def test_unknown_item_is_404(
    client_factory: Callable[..., TestClient], alice: User
) -> None:
    ca = client_factory(alice)
    lid = _new_list(ca)
    missing = "00000000-0000-0000-0000-000000000000"
    resp = ca.put(f"/api/lists/{lid}/items/{missing}/rating", json={"value": 1})
    assert resp.status_code == 404


# --- Privacy: the highest-value test in the milestone --------------------
def test_a_verdict_never_reaches_someone_you_share_no_list_with(
    client_factory: Callable[..., TestClient],
    alice: User,
    bob: User,
    carol: User,
    mock_tmdb: None,
) -> None:
    """Alice and Bob share a list; Carol has the same film in her own.

    Scoping a verdict to the list item is what keeps Alice's opinion away from
    Carol — it's the foreign key, not a filter someone has to remember. This
    test is the regression guard on that being true end to end.
    """
    ca, cb, cc = client_factory(alice), client_factory(bob), client_factory(carol)

    shared = _new_list(ca, "Date night")
    _join(ca, cb, shared)
    shared_item = _add(ca, shared, DUNE)
    ca.put(f"/api/lists/{shared}/items/{shared_item}/rating", json={"value": 1})
    cb.put(f"/api/lists/{shared}/items/{shared_item}/rating", json={"value": -1})

    solo = _new_list(cc, "Carol's list")
    solo_item = _add(cc, solo, DUNE)
    cc.put(f"/api/lists/{solo}/items/{solo_item}/rating", json={"value": 1})

    # Carol sees her own verdict on Dune and nobody else's.
    assert _ratings(cc, solo, solo_item) == [{"user_id": str(carol.id), "value": 1}]

    # Alice sees hers and Bob's — the two of them are co-members — but not
    # Carol's, even though it's the same film.
    on_shared = _ratings(ca, shared, shared_item)
    assert {r["user_id"] for r in on_shared} == {str(alice.id), str(bob.id)}


def test_verdict_order_is_stable_between_requests(
    client_factory: Callable[..., TestClient],
    alice: User,
    bob: User,
    mock_tmdb: None,
) -> None:
    """Avatars must not shuffle between renders.

    `joined_at` alone doesn't guarantee it: SQLite stamps CURRENT_TIMESTAMP to
    the second, so two people who join in the same second tie and the database
    picks. The user_id tiebreak is what makes the order total — and this asserts
    the property (stability) rather than a particular order.
    """
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    _join(ca, cb, lid)
    item = _add(ca, lid)
    ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": 1})
    cb.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": -1})

    order = [r["user_id"] for r in _ratings(ca, lid, item)]
    assert len(order) == 2
    for _ in range(3):
        assert [r["user_id"] for r in _ratings(ca, lid, item)] == order
    # The board must agree with the detail page, or the same two faces would
    # appear in one order on one screen and the other order on the next.
    board = ca.get(f"/api/lists/{lid}/items").json()
    assert [r["user_id"] for r in board[0]["ratings"]] == order


def test_the_board_carries_every_item_s_verdicts(
    client_factory: Callable[..., TestClient],
    alice: User,
    bob: User,
    mock_tmdb: None,
) -> None:
    """GET /items is the board load — verdicts come with it, not per card."""
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    _join(ca, cb, lid)

    dune = _add(ca, lid, DUNE)
    blade = _add(ca, lid, BLADE_RUNNER)
    ca.put(f"/api/lists/{lid}/items/{dune}/rating", json={"value": 1})
    cb.put(f"/api/lists/{lid}/items/{dune}/rating", json={"value": -1})
    cb.put(f"/api/lists/{lid}/items/{blade}/rating", json={"value": 1})

    board = {i["id"]: i["ratings"] for i in ca.get(f"/api/lists/{lid}/items").json()}
    assert len(board[dune]) == 2
    assert board[blade] == [{"user_id": str(bob.id), "value": 1}]


def test_the_same_film_is_rated_separately_in_each_list(
    client_factory: Callable[..., TestClient],
    db_session: Session,
    alice: User,
    mock_tmdb: None,
) -> None:
    """A verdict belongs to the list it was given in, not to the film.

    The same person can say different things about the same movie in two lists —
    two remarks in two rooms, not one contradicting itself.
    """
    ca = client_factory(alice)
    first, second = _new_list(ca, "Date night"), _new_list(ca, "Sci-fi")
    in_first, in_second = _add(ca, first, DUNE), _add(ca, second, DUNE)

    ca.put(f"/api/lists/{first}/items/{in_first}/rating", json={"value": 1})

    # Rating it in one list says nothing about it in the other.
    assert _ratings(ca, first, in_first) == [{"user_id": str(alice.id), "value": 1}]
    assert _ratings(ca, second, in_second) == []

    ca.put(f"/api/lists/{second}/items/{in_second}/rating", json={"value": -1})
    assert len(db_session.execute(select(ItemRating)).scalars().all()) == 2
    assert _ratings(ca, first, in_first) == [{"user_id": str(alice.id), "value": 1}]
    assert _ratings(ca, second, in_second) == [{"user_id": str(alice.id), "value": -1}]


# --- Decoupling ----------------------------------------------------------
def test_verdicts_and_watch_status_do_not_touch_each_other(
    client_factory: Callable[..., TestClient],
    alice: User,
    bob: User,
    mock_tmdb: None,
) -> None:
    """The whole point of §12: no rule spans the two tables.

    An unwatched film can be rated (it reads as "I'm keen"), and neither
    watching nor un-watching disturbs anyone's verdict — least of all the other
    member's, which no toggle of yours may ever destroy.
    """
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    _join(ca, cb, lid)
    item = _add(ca, lid)

    # Rating something nobody has watched yet: allowed, no 422.
    assert (
        ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": 1}).status_code
        == 200
    )
    cb.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": 1})

    watched = ca.patch(
        f"/api/lists/{lid}/items/{item}", json={"status": "watched"}
    )
    assert watched.status_code == 200
    assert len(watched.json()["ratings"]) == 2

    # Alice changes her mind after seeing it; Bob's verdict is untouched.
    ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": -1})
    after = {r["user_id"]: r["value"] for r in _ratings(ca, lid, item)}
    assert after == {str(alice.id): -1, str(bob.id): 1}

    # Un-watching is the undo for a mistap. It must not clear Bob's opinion.
    unwatched = ca.patch(
        f"/api/lists/{lid}/items/{item}", json={"status": "want_to_watch"}
    )
    assert unwatched.status_code == 200
    assert {r["user_id"]: r["value"] for r in unwatched.json()["ratings"]} == after


def test_removing_the_movie_takes_its_verdicts_with_it(
    client_factory: Callable[..., TestClient],
    db_session: Session,
    alice: User,
    bob: User,
    mock_tmdb: None,
) -> None:
    """The FK cascade, and the reason re-adding a film is a clean slate.

    Under a global rating this was the awkward case — a thumb you'd forgotten
    about ambushing you a year later. Scoped to the item, the opinions simply go
    when the movie does.
    """
    ca, cb = client_factory(alice), client_factory(bob)
    lid = _new_list(ca)
    _join(ca, cb, lid)
    item = _add(ca, lid)
    ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": 1})
    cb.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": -1})

    assert ca.delete(f"/api/lists/{lid}/items/{item}").status_code == 204
    assert db_session.execute(select(ItemRating)).scalars().all() == []

    re_added = ca.post(f"/api/lists/{lid}/items", json={"tmdb_id": DUNE})
    assert re_added.status_code == 201
    assert re_added.json()["ratings"] == []


def test_verdicts_die_with_the_list_and_with_the_user(
    client_factory: Callable[..., TestClient],
    db_session: Session,
    alice: User,
    mock_tmdb: None,
) -> None:
    """Both cascades, asserted on a real database.

    SQLite ignores ON DELETE CASCADE unless the pragma is on (it bit M2), so
    this is worth stating rather than trusting.
    """
    ca = client_factory(alice)
    lid = _new_list(ca)
    item = _add(ca, lid)
    ca.put(f"/api/lists/{lid}/items/{item}/rating", json={"value": 1})

    # Through lists -> list_items -> item_ratings.
    assert ca.delete(f"/api/lists/{lid}").status_code == 204
    assert db_session.execute(select(ItemRating)).scalars().all() == []

    second = _new_list(ca, "Again")
    again = _add(ca, second)
    ca.put(f"/api/lists/{second}/items/{again}/rating", json={"value": -1})

    db_session.delete(db_session.get(User, alice.id))
    db_session.commit()
    assert db_session.execute(select(ItemRating)).scalars().all() == []
