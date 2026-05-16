from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.engine import get_session
from app.db.models import Notification, NotificationType, User
from app.services.deps import CurrentUser

router = APIRouter()


class NotificationOut(BaseModel):
    id: str
    type: str
    title: str
    message: str
    is_read: bool
    trade_id: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    type: NotificationType
    title: str
    message: str
    trade_id: Optional[str] = None


class NotificationUpdate(BaseModel):
    is_read: Optional[bool] = None


@router.get("", response_model=list[NotificationOut])
def list_notifications(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
    limit: int = 50,
    unread_only: bool = False,
):
    query = select(Notification).where(
        Notification.user_id == user.id
    ).order_by(Notification.created_at.desc()).limit(limit)
    
    if unread_only:
        query = query.where(Notification.is_read == False)
    
    notifications = db.exec(query).all()
    return [
        NotificationOut(
            id=str(n.id),
            type=n.type.value,
            title=n.title,
            message=n.message,
            is_read=n.is_read,
            trade_id=str(n.trade_id) if n.trade_id else None,
            created_at=n.created_at,
        )
        for n in notifications
    ]


@router.get("/unread-count")
def unread_count(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    count = db.exec(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read == False
        )
    ).all()
    return {"count": len(count)}


@router.patch("/{notification_id}", response_model=NotificationOut)
def mark_read(
    notification_id: UUID,
    payload: NotificationUpdate,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        return {"error": "Not found"}, 404
    
    if payload.is_read is not None:
        notification.is_read = payload.is_read
        db.add(notification)
        db.commit()
        db.refresh(notification)
    
    return NotificationOut(
        id=str(notification.id),
        type=notification.type.value,
        title=notification.title,
        message=notification.message,
        is_read=notification.is_read,
        trade_id=str(notification.trade_id) if notification.trade_id else None,
        created_at=notification.created_at,
    )


@router.post("/mark-all-read")
def mark_all_read(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    notifications = db.exec(
        select(Notification).where(
            Notification.user_id == user.id,
            Notification.is_read == False
        )
    ).all()
    
    for n in notifications:
        n.is_read = True
        db.add(n)
    
    db.commit()
    return {"count": len(notifications)}


def create_notification(
    db: Session,
    user_id: UUID,
    org_id: UUID,
    notif_type: NotificationType,
    title: str,
    message: str,
    trade_id: Optional[UUID] = None,
):
    notification = Notification(
        user_id=user_id,
        org_id=org_id,
        type=notif_type,
        title=title,
        message=message,
        trade_id=trade_id,
    )
    db.add(notification)
    db.commit()
    return notification
