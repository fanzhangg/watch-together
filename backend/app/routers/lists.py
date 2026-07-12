"""List routes. Every /{list_id} route is gated by membership (see deps)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app import crud
from app.db import get_db
from app.deps import ListContext, get_current_user, require_list_member, require_list_owner
from app.models import List, User
from app.schemas import ListCreate, ListDetail, ListOut, ListUpdate, MemberOut, UserOut

router = APIRouter(prefix="/api/lists", tags=["lists"])


def _to_list_out(lst: List, role: str) -> ListOut:
    return ListOut(
        id=lst.id,
        name=lst.name,
        owner_id=lst.owner_id,
        created_at=lst.created_at,
        role=role,
    )


@router.get("", response_model=list[ListOut])
def get_my_lists(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ListOut]:
    return [_to_list_out(lst, role) for lst, role in crud.lists_for_user(db, user.id)]


@router.post("", response_model=ListOut, status_code=status.HTTP_201_CREATED)
def create_list(
    payload: ListCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ListOut:
    lst = crud.create_list(db, owner=user, name=payload.name)
    return _to_list_out(lst, "owner")


@router.get("/{list_id}", response_model=ListDetail)
def get_list(
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
) -> ListDetail:
    members = [
        MemberOut(user=UserOut.model_validate(u), role=role)
        for u, role in crud.get_members(db, ctx.list.id)
    ]
    base = _to_list_out(ctx.list, ctx.membership.role)
    return ListDetail(**base.model_dump(), members=members)


@router.patch("/{list_id}", response_model=ListOut)
def rename_list(
    payload: ListUpdate,
    ctx: ListContext = Depends(require_list_owner),
    db: Session = Depends(get_db),
) -> ListOut:
    lst = crud.rename_list(db, ctx.list, payload.name)
    return _to_list_out(lst, ctx.membership.role)


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(
    ctx: ListContext = Depends(require_list_owner),
    db: Session = Depends(get_db),
) -> Response:
    crud.delete_list(db, ctx.list)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
