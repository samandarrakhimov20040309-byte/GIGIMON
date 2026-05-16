from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlmodel import Session, select

from app.db.engine import get_session
from app.db.models import Organization, User
from app.services.audit import write_audit
from app.services.passwords import hash_password, verify_password
from app.services.security import create_access_token, get_current_user_id

router = APIRouter()


async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Annotated[Session, Depends(get_session)] = None
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = authorization[7:]
    user_id = get_current_user_id(token)
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


class DevLoginIn(BaseModel):
    org_name: str = "Default Org"
    email: EmailStr
    display_name: str = "Trader"
    tz: str = "UTC"


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    org_id: UUID


class RegisterIn(BaseModel):
    org_name: Optional[str] = None
    full_name: str
    email: EmailStr
    password: str
    tz: str = "UTC"
    terms_accepted: bool = False


@router.post("/register", response_model=TokenOut)
def register(payload: RegisterIn, db: Annotated[Session, Depends(get_session)]):
    if not payload.terms_accepted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Terms must be accepted")
    if len(payload.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    org_name = payload.org_name or "Personal"
    org = db.exec(select(Organization).where(Organization.name == org_name)).first()
    if org is None:
        org = Organization(name=org_name)
        db.add(org)
        db.commit()
        db.refresh(org)

    existing = db.exec(select(User).where(User.org_id == org.id, User.email == str(payload.email))).first()
    if existing is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    user = User(
        org_id=org.id,
        email=str(payload.email),
        display_name=payload.full_name,
        tz=payload.tz,
        password_hash=hash_password(payload.password),
        terms_accepted_at=datetime.utcnow(),
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), org_id=str(org.id))
    write_audit(db, action="auth.register", org_id=org.id, user_id=user.id, meta={"email": user.email})
    return TokenOut(access_token=token, user_id=user.id, org_id=org.id)


class LoginIn(BaseModel):
    org_name: Optional[str] = None
    email: EmailStr
    password: str


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Annotated[Session, Depends(get_session)]):
    if payload.org_name:
        org = db.exec(select(Organization).where(Organization.name == payload.org_name)).first()
        if org is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
        user = db.exec(select(User).where(User.org_id == org.id, User.email == str(payload.email))).first()
    else:
        users = db.exec(select(User).where(User.email == str(payload.email))).all()
        user = users[0] if len(users) == 1 else None

    if user is None or not user.is_active or not user.password_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    user.last_login_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=str(user.id), org_id=str(user.org_id))
    write_audit(db, action="auth.login", org_id=user.org_id, user_id=user.id, meta={"email": user.email})
    return TokenOut(access_token=token, user_id=user.id, org_id=user.org_id)


@router.post("/dev/login", response_model=TokenOut)
def dev_login(payload: DevLoginIn, db: Annotated[Session, Depends(get_session)]):
    org = db.exec(select(Organization).where(Organization.name == payload.org_name)).first()
    if org is None:
        org = Organization(name=payload.org_name)
        db.add(org)
        db.commit()
        db.refresh(org)

    user = db.exec(select(User).where(User.org_id == org.id, User.email == payload.email)).first()
    if user is None:
        user = User(
            org_id=org.id,
            email=str(payload.email),
            display_name=payload.display_name,
            tz=payload.tz,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(subject=str(user.id), org_id=str(org.id))
    write_audit(db, action="auth.dev_login", org_id=org.id, user_id=user.id, meta={"email": user.email})
    return TokenOut(access_token=token, user_id=user.id, org_id=org.id)


class GoogleStartOut(BaseModel):
    detail: str
    auth_url: Optional[str] = None


@router.get("/google/start", response_model=GoogleStartOut)
def google_start():
    # Skeleton: you will later implement OAuth redirect URL generation and PKCE/state handling.
    return GoogleStartOut(detail="Not implemented (skeleton)")


@router.get("/google/callback", response_model=GoogleStartOut)
def google_callback(code: str, state: str):
    # Skeleton: exchange code for tokens, fetch profile, map/create user, issue JWT.
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Not implemented (skeleton)")


class PhoneStartIn(BaseModel):
    phone: str


class PhoneVerifyIn(BaseModel):
    phone: str
    code: str


@router.post("/phone/start")
def phone_start(_: PhoneStartIn):
    # Skeleton: send SMS code.
    return {"detail": "Not implemented (skeleton)"}


@router.post("/phone/verify")
def phone_verify(_: PhoneVerifyIn):
    # Skeleton: verify code, mark user phone_verified, issue JWT.
    return {"detail": "Not implemented (skeleton)"}


class UserOut(BaseModel):
    id: UUID
    username: Optional[str] = None
    email: str
    display_name: Optional[str] = None

    class Config:
        from_attributes = True


class ProfileUpdateIn(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None


@router.get("/me", response_model=UserOut)
def get_me(current_user: Annotated[User, Depends(get_current_user)]):
    return UserOut(
        id=current_user.id,
        username=current_user.display_name,
        email=current_user.email,
        display_name=current_user.display_name
    )


@router.put("/profile")
def update_profile(
    payload: ProfileUpdateIn,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)]
):
    if payload.username is not None:
        current_user.display_name = payload.username
    if payload.email is not None:
        current_user.email = payload.email
    db.add(current_user)
    db.commit()
    return {"detail": "Profile updated"}


@router.delete("/account")
def delete_account(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_session)]
):
    user_id = current_user.id
    user_org_id = current_user.org_id
    db.delete(current_user)
    db.commit()
    write_audit(db, action="auth.account_deleted", org_id=user_org_id, user_id=user_id)
    return {"detail": "Account deleted"}

