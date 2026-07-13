"""Invite routes — the flow that lets a second person join a list.

Two routers:
- create: POST /api/lists/{list_id}/invites   (any member of the list)
- use:    GET  /api/invites/{code}            (public preview, no login needed)
          POST /api/invites/{code}/accept     (login required)

The preview is intentionally unauthenticated so someone can see what they've
been invited to *before* signing in. The code itself is the secret, so knowing
it is the authorization to see the list's name.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import crud
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import ListContext, get_current_user, require_list_member
from app.models import Invite, List, User
from app.schemas import InviteCreate, InviteOut, InvitePreview, ListOut

# Creating an invite lives under the list it belongs to.
list_invites_router = APIRouter(
    prefix="/api/lists/{list_id}/invites", tags=["invites"]
)
# Using an invite is addressed by code alone — the recipient has no list id.
router = APIRouter(prefix="/api/invites", tags=["invites"])


def _invite_url(request: Request, settings: Settings, code: str) -> str:
    """Build the share link.

    Prefers an explicitly configured base URL — needed in dev (SPA on :5173,
    API on :8000) and on Render (which injects RENDER_EXTERNAL_URL). Falls back
    to the request's own origin, which is right when the SPA and API share one.

    The fallback relies on uvicorn running with --proxy-headers so that
    X-Forwarded-Proto is honoured; without it, a TLS-terminating proxy would
    make us emit http:// links for an https:// site.
    """
    base = settings.public_base_url or str(request.base_url)
    return f"{base.rstrip('/')}/invite/{code}"


def _to_invite_out(request: Request, settings: Settings, invite: Invite) -> InviteOut:
    return InviteOut(
        code=invite.code,
        url=_invite_url(request, settings, invite.code),
        list_id=invite.list_id,
        expires_at=invite.expires_at,
    )


@list_invites_router.post(
    "",
    response_model=InviteOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a share link for this list",
    responses={
        201: {"description": "Invite created; share the returned url"},
        403: {"description": "Not a member of this list"},
    },
)
def create_invite(
    request: Request,
    payload: InviteCreate | None = None,
    ctx: ListContext = Depends(require_list_member),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    settings: Settings = Depends(get_settings),
) -> InviteOut:
    invite = crud.create_invite(
        db,
        list_id=ctx.list.id,
        created_by=user,
        expires_in_days=payload.expires_in_days if payload else None,
    )
    return _to_invite_out(request, settings, invite)


def _load_usable_invite(db: Session, code: str) -> Invite:
    invite = crud.get_invite_by_code(db, code)
    if invite is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    if crud.invite_is_expired(invite):
        raise HTTPException(
            status_code=status.HTTP_410_GONE, detail="This invite has expired"
        )
    return invite


@router.get(
    "/{code}",
    response_model=InvitePreview,
    summary="Preview an invite before accepting (no login required)",
    responses={
        200: {"description": "What you'd be joining"},
        404: {"description": "Invite not found"},
        410: {"description": "Invite has expired"},
    },
)
def preview_invite(
    code: str,
    db: Session = Depends(get_db),
) -> InvitePreview:
    invite = _load_usable_invite(db, code)
    lst = db.get(List, invite.list_id)
    if lst is None:  # list was deleted after the invite was made
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )
    inviter = db.get(User, invite.created_by)
    return InvitePreview(
        code=invite.code,
        list_name=lst.name,
        invited_by=(inviter.display_name or inviter.email) if inviter else "Someone",
        expires_at=invite.expires_at,
    )


@router.post(
    "/{code}/accept",
    response_model=ListOut,
    summary="Join the list this invite points to",
    responses={
        200: {"description": "You are now a member (idempotent if already one)"},
        401: {"description": "Sign in first, then accept"},
        404: {"description": "Invite not found"},
        410: {"description": "Invite has expired"},
    },
)
def accept_invite(
    code: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ListOut:
    invite = _load_usable_invite(db, code)
    lst = db.get(List, invite.list_id)
    if lst is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Invite not found"
        )

    membership = crud.accept_invite(db, invite, user)
    return ListOut(
        id=lst.id,
        name=lst.name,
        owner_id=lst.owner_id,
        created_at=lst.created_at,
        role=membership.role,
    )
