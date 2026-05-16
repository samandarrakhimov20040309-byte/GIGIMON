from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.db.engine import get_session
from app.db.models import User
from app.services.deps import CurrentUser
from app.services.audit import write_audit

router = APIRouter()


class MeOut(BaseModel):
    id: str
    org_id: str
    email: str
    phone: Optional[str]
    display_name: str
    tz: str
    phone_verified: bool


@router.get("/me", response_model=MeOut)
def me(user: CurrentUser):
    return MeOut(
        id=str(user.id),
        org_id=str(user.org_id),
        email=user.email,
        phone=user.phone,
        display_name=user.display_name,
        tz=user.tz,
        phone_verified=user.phone_verified,
    )


class UpdateMeIn(BaseModel):
    display_name: Optional[str] = None
    tz: Optional[str] = None


@router.patch("/me", response_model=MeOut)
def update_me(
    payload: UpdateMeIn,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    changed = {}
    if payload.display_name is not None:
        user.display_name = payload.display_name
        changed["display_name"] = payload.display_name
    if payload.tz is not None:
        user.tz = payload.tz
        changed["tz"] = payload.tz
    db.add(user)
    db.commit()
    db.refresh(user)
    write_audit(db, action="user.update_me", org_id=user.org_id, user_id=user.id, meta=changed)
    return me(user)

