from datetime import datetime
from typing import Annotated, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from pydantic import ConfigDict
from sqlmodel import Session, select

from app.db.engine import get_session
from app.db.models import NotificationType, Trade, TradeStatus
from app.services.audit import write_audit
from app.services.deps import CurrentUser
from app.api.routes.notifications import create_notification

router = APIRouter()


class TradeCreateIn(BaseModel):
    source: str = "manual"
    account: Optional[str] = None
    symbol: str
    side: str
    qty: float
    contract_size: float = 1.0
    price: float
    exit_price: Optional[float] = None
    fee: float = 0.0
    fee_asset: Optional[str] = None
    executed_at: str
    exit_at: Optional[str] = None
    notes: str = ""


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: str
    account: Optional[str]
    symbol: str
    side: str
    qty: float
    contract_size: float = 1.0
    price: float
    exit_price: Optional[float] = None
    fee: float
    fee_asset: Optional[str]
    executed_at: datetime
    exit_at: Optional[datetime] = None
    notes: str
    status: str = "active"
    cancelled_at: Optional[datetime] = None
    cancelled_reason: Optional[str] = None


@router.post("", response_model=TradeOut)
def create_trade(
    payload: TradeCreateIn,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    from datetime import datetime as dt
    
    trade = Trade(
        org_id=user.org_id,
        user_id=user.id,
        source=payload.source,
        account=payload.account,
        symbol=payload.symbol,
        side=payload.side,
        qty=payload.qty,
        contract_size=payload.contract_size,
        price=payload.price,
        exit_price=payload.exit_price,
        fee=payload.fee,
        fee_asset=payload.fee_asset,
        executed_at=dt.fromisoformat(payload.executed_at.replace('Z', '+00:00')),
        exit_at=dt.fromisoformat(payload.exit_at.replace('Z', '+00:00')) if payload.exit_at else None,
        notes=payload.notes,
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    
    if trade.exit_price:
        entry_value = trade.qty * trade.contract_size * trade.price
        exit_value = trade.qty * trade.contract_size * trade.exit_price
        pnl = exit_value - entry_value if trade.side.lower() == "buy" else entry_value - exit_value
        pnl_text = f"+${pnl:.2f}" if pnl >= 0 else f"-${abs(pnl):.2f}"
        
        create_notification(
            db=db,
            user_id=user.id,
            org_id=user.org_id,
            notif_type=NotificationType.trade,
            title=f"Trade {trade.side.upper()} yopildi",
            message=f"{trade.symbol} {trade.side} pozitsiya ${trade.exit_price} da yopildi. PnL: {pnl_text}",
            trade_id=trade.id,
        )
    
    if not payload.notes.strip():
        create_notification(
            db=db,
            user_id=user.id,
            org_id=user.org_id,
            notif_type=NotificationType.warning,
            title="Izoh talab qilinadi",
            message=f"{trade.symbol} trade uchun izoh yozilmagan. 24 soat ichida hujjatlashtiring.",
            trade_id=trade.id,
        )
    
    write_audit(db, action="trade.create", org_id=user.org_id, user_id=user.id, meta={"trade_id": str(trade.id)})
    return TradeOut.model_validate(trade)


@router.get("", response_model=List[TradeOut])
def list_trades(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
    limit: int = 100,
):
    rows = db.exec(
        select(Trade)
        .where(
            Trade.org_id == user.org_id,
            Trade.user_id == user.id,
            Trade.status == TradeStatus.active,
        )
        .order_by(Trade.executed_at.desc())
        .limit(limit)
    ).all()
    return [TradeOut.model_validate(r) for r in rows]


@router.get("/archive", response_model=List[TradeOut])
def list_archived_trades(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
    limit: int = 100,
):
    rows = db.exec(
        select(Trade)
        .where(
            Trade.org_id == user.org_id,
            Trade.user_id == user.id,
            Trade.status == TradeStatus.cancelled,
        )
        .order_by(Trade.cancelled_at.desc())
        .limit(limit)
    ).all()
    return [TradeOut.model_validate(r) for r in rows]


class TradeCancelIn(BaseModel):
    reason: str = ""


@router.patch("/{trade_id}/cancel", response_model=TradeOut)
def cancel_trade(
    trade_id: UUID,
    payload: TradeCancelIn,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    trade = db.get(Trade, trade_id)
    if not trade or trade.org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    if trade.status != TradeStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Trade is already cancelled")

    trade.status = TradeStatus.cancelled
    trade.cancelled_at = datetime.utcnow()
    trade.cancelled_reason = payload.reason or None

    db.add(trade)
    db.commit()
    db.refresh(trade)

    write_audit(db, action="trade.cancel", org_id=user.org_id, user_id=user.id, meta={"trade_id": str(trade.id), "reason": payload.reason})
    return TradeOut.model_validate(trade)


@router.get("/{trade_id}", response_model=TradeOut)
def get_trade(
    trade_id: UUID,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    trade = db.get(Trade, trade_id)
    if not trade or trade.org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    return TradeOut.model_validate(trade)


class TradeUpdateIn(BaseModel):
    notes: Optional[str] = None
    exit_price: Optional[float] = None
    exit_at: Optional[datetime] = None


@router.patch("/{trade_id}", response_model=TradeOut)
def update_trade(
    trade_id: UUID,
    payload: TradeUpdateIn,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    trade = db.get(Trade, trade_id)
    if not trade or trade.org_id != user.org_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")
    
    if payload.notes is not None:
        trade.notes = payload.notes
    if payload.exit_price is not None:
        trade.exit_price = payload.exit_price
    if payload.exit_at is not None:
        trade.exit_at = payload.exit_at
    
    db.add(trade)
    db.commit()
    db.refresh(trade)
    
    write_audit(db, action="trade.update", org_id=user.org_id, user_id=user.id, meta={"trade_id": str(trade.id)})
    return TradeOut.model_validate(trade)

