import json
from typing import Any, Optional
from uuid import UUID

from sqlmodel import Session

from app.db.models import AuditLog


def write_audit(
    db: Session,
    *,
    action: str,
    org_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    meta: Any = None,
) -> None:
    log = AuditLog(
        action=action,
        org_id=org_id,
        user_id=user_id,
        meta_json=json.dumps(meta or {}, ensure_ascii=False),
    )
    db.add(log)
    db.commit()

