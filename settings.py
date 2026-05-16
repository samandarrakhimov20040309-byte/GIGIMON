from typing import Annotated, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.engine import get_session
from app.db.models import UserSetting
from app.services.deps import CurrentUser

router = APIRouter()


class SettingsIn(BaseModel):
    key: str
    value: str


@router.get("")
def get_settings(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    settings = db.exec(
        select(UserSetting).where(UserSetting.user_id == user.id)
    ).all()
    
    return {s.key: s.value for s in settings}


@router.put("")
def update_settings(
    payload: SettingsIn,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    existing = db.exec(
        select(UserSetting).where(
            UserSetting.user_id == user.id,
            UserSetting.key == payload.key
        )
    ).first()
    
    if existing:
        existing.value = payload.value
        db.add(existing)
    else:
        setting = UserSetting(
            user_id=user.id,
            key=payload.key,
            value=payload.value,
        )
        db.add(setting)
    
    db.commit()
    
    return {"success": True, "key": payload.key, "value": payload.value}


@router.put("/batch")
def update_settings_batch(
    payload: Dict[str, str],
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    for key, value in payload.items():
        existing = db.exec(
            select(UserSetting).where(
                UserSetting.user_id == user.id,
                UserSetting.key == key
            )
        ).first()
        
        if existing:
            existing.value = value
            db.add(existing)
        else:
            setting = UserSetting(
                user_id=user.id,
                key=key,
                value=value,
            )
            db.add(setting)
    
    db.commit()
    
    return {"success": True}