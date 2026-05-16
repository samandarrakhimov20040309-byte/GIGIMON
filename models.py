from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel, UniqueConstraint


class ReportPeriod(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    yearly = "yearly"


class Organization(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    email: str = Field(index=True)
    phone: Optional[str] = Field(default=None, index=True)
    display_name: str = ""
    tz: str = "UTC"

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    last_login_at: Optional[datetime] = Field(default=None, index=True)

    # auth
    password_hash: Optional[str] = None
    terms_accepted_at: Optional[datetime] = None

    # oauth / phone (skeleton for now)
    google_sub: Optional[str] = Field(default=None, index=True)
    phone_verified: bool = False


class TradeStatus(str, Enum):
    active = "active"
    cancelled = "cancelled"


class Trade(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")

    source: str = Field(index=True)  # mt5_ea, binance, manual, etc.
    account: Optional[str] = Field(default=None, index=True)
    symbol: str = Field(index=True)
    side: str  # buy/sell

    qty: float
    contract_size: float = Field(default=1.0, alias="contractSize")
    price: float
    exit_price: Optional[float] = None
    fee: float = 0.0
    fee_asset: Optional[str] = None

    executed_at: datetime = Field(index=True)
    exit_at: Optional[datetime] = None
    notes: str = ""

    status: TradeStatus = Field(default=TradeStatus.active, index=True)
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class IngestEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    user_id: Optional[UUID] = Field(default=None, index=True, foreign_key="user.id")
    source: str = Field(index=True)  # mt5_ea, exchange_poll, etc.
    received_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    raw_json: str
    status: str = Field(default="received", index=True)  # received/processed/failed
    error: Optional[str] = None


class MT5Connection(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    server: str
    login: str
    password_hash: str
    account_type: str  # real or demo
    is_connected: bool = Field(default=False)
    balance: float = Field(default=0)
    equity: float = Field(default=0)
    last_sync: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Report(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    period: ReportPeriod = Field(index=True)
    period_start: datetime = Field(index=True)
    period_end: datetime = Field(index=True)
    generated_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    payload_json: str = ""  # metrics + notes (non-AI)


class Insight(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    report_id: UUID = Field(index=True, foreign_key="report.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    model: str
    advice_markdown: str
    score_json: str = ""  # structured scores
    actions_json: str = ""  # action plan checklist


class AuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: Optional[UUID] = Field(default=None, index=True)
    user_id: Optional[UUID] = Field(default=None, index=True)
    action: str = Field(index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    meta_json: str = ""


class NotificationType(str, Enum):
    trade = "trade"
    ai_insight = "ai_insight"
    warning = "warning"
    system = "system"


class Notification(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    org_id: UUID = Field(index=True, foreign_key="organization.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    
    type: NotificationType = Field(index=True)
    title: str
    message: str
    is_read: bool = False
    
    trade_id: Optional[UUID] = Field(default=None, foreign_key="trade.id")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)


class UserSetting(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(index=True, foreign_key="user.id")
    key: str = Field(index=True)
    value: str = Field(default="")
    
    __table_args__ = (UniqueConstraint("user_id", "key", name="uq_user_setting"),)

