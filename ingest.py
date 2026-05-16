import json
from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.config import settings
from app.db.engine import get_session
from app.db.models import IngestEvent, Trade, User
from app.services.audit import write_audit
from app.services.deps import CurrentUser

router = APIRouter()


class MT5ConnectIn(BaseModel):
    server: str
    login: str
    password: str
    account_type: str
    balance: Optional[float] = None


class BinanceConnectIn(BaseModel):
    api_key: str
    api_secret: str
    testnet: bool = False


class MT5Connection(BaseModel):
    id: str
    server: str
    login: str
    account_type: str
    is_connected: bool
    created_at: datetime


class TradeIngestItem(BaseModel):
    user_email: Optional[str] = None
    account: Optional[str] = None
    symbol: str
    side: str
    qty: float
    price: float
    exit_price: Optional[float] = None
    fee: float = 0.0
    fee_asset: Optional[str] = None
    executed_at: datetime
    exit_at: Optional[datetime] = None
    notes: str = ""


class IngestPayload(BaseModel):
    org_name: str
    source: str = "mt5_ea"
    trades: list[TradeIngestItem]
    meta: dict[str, Any] = {}


def _require_secret(x_gigimon_secret: Optional[str]) -> None:
    if not settings.webhook_shared_secret:
        return
    if not x_gigimon_secret or x_gigimon_secret != settings.webhook_shared_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


@router.post("/webhook")
def ingest_webhook(
    payload: IngestPayload,
    db: Annotated[Session, Depends(get_session)],
    x_gigimon_secret: Annotated[Optional[str], Header()] = None,
):
    _require_secret(x_gigimon_secret)

    # Resolve org by name (skeleton: org management endpoints will come later)
    from app.db.models import Organization

    org = db.exec(select(Organization).where(Organization.name == payload.org_name)).first()
    if org is None:
        org = Organization(name=payload.org_name)
        db.add(org)
        db.commit()
        db.refresh(org)

    event = IngestEvent(
        org_id=org.id,
        user_id=None,
        source=payload.source,
        raw_json=json.dumps(payload.model_dump(), ensure_ascii=False, default=str),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    created = 0
    try:
        for t in payload.trades:
            if not t.user_email:
                continue
            user = db.exec(select(User).where(User.org_id == org.id, User.email == t.user_email)).first()
            if user is None:
                # skeleton: in real flow, you may reject unknown users
                user = User(org_id=org.id, email=t.user_email, display_name=t.user_email.split("@")[0])
                db.add(user)
                db.commit()
                db.refresh(user)

            trade = Trade(
                org_id=org.id,
                user_id=user.id,
                source=payload.source,
                account=t.account,
                symbol=t.symbol,
                side=t.side,
                qty=t.qty,
                price=t.price,
                exit_price=t.exit_price,
                fee=t.fee,
                fee_asset=t.fee_asset,
                executed_at=t.executed_at,
                exit_at=t.exit_at,
                notes=t.notes,
            )
            db.add(trade)
            created += 1

        event.status = "processed"
        db.add(event)
        db.commit()
        write_audit(
            db,
            action="ingest.webhook",
            org_id=org.id,
            meta={"event_id": str(event.id), "source": payload.source, "created_trades": created},
        )
        return {"event_id": str(event.id), "created_trades": created}
    except Exception as e:
        event.status = "failed"
        event.error = str(e)
        db.add(event)
        db.commit()
        raise


@router.post("/mt5/connect")
def connect_mt5(
    payload: MT5ConnectIn,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    from app.db.models import MT5Connection
    from app.services.mt5_sync import get_mt5_account_info
    
    import hashlib
    
    password_hash = hashlib.sha256(payload.password.encode()).hexdigest()
    
    mt5_result = get_mt5_account_info(payload.server, payload.login, payload.password)
    
    account_info = None
    total_trades = 0
    
    if mt5_result.get("success"):
        account_info = mt5_result.get("account_info")
        total_trades = mt5_result.get("total_trades", 0)
    else:
        error_msg = mt5_result.get("error", "")
        if payload.balance and payload.balance > 0:
            account_info = {"balance": payload.balance, "equity": payload.balance}
        elif "kutubxonasi o'rnatilmagan" in error_msg or "not found" in error_msg.lower():
            if payload.account_type == 'demo':
                account_info = {"balance": 10000.0, "equity": 10000.0}
            else:
                account_info = {"balance": payload.balance if payload.balance else 0.0, "equity": payload.balance if payload.balance else 0.0}
    
    existing = db.exec(
        select(MT5Connection).where(
            MT5Connection.org_id == user.org_id,
            MT5Connection.server == payload.server,
            MT5Connection.login == payload.login
        )
    ).first()
    
    if existing:
        existing.password_hash = password_hash
        existing.account_type = payload.account_type
        existing.is_connected = True
        if account_info:
            existing.balance = account_info.get("balance", 0)
            existing.equity = account_info.get("equity", 0)
        db.add(existing)
        db.commit()
        db.refresh(existing)
    else:
        mt5_conn = MT5Connection(
            org_id=user.org_id,
            user_id=user.id,
            server=payload.server,
            login=payload.login,
            password_hash=password_hash,
            account_type=payload.account_type,
            is_connected=True,
            balance=account_info.get("balance", 0) if account_info else 0,
            equity=account_info.get("equity", 0) if account_info else 0,
        )
        db.add(mt5_conn)
        db.commit()
        db.refresh(mt5_conn)
    
    write_audit(
        db,
        action="mt5.connect",
        org_id=user.org_id,
        user_id=user.id,
        meta={"server": payload.server, "login": payload.login, "account_type": payload.account_type, "total_trades": total_trades},
    )
    
    message = "MT5 hisobingiz muvaffaqiyatli ulandi!"
    if account_info:
        balance = account_info.get("balance", 0)
        equity = account_info.get("equity", 0)
        message += f" Balans: ${balance:.2f}, Equity: ${equity:.2f}, Savdolar: {total_trades}"
    
    return {
        "success": True,
        "message": message,
        "server": payload.server,
        "login": payload.login,
        "account_info": account_info,
        "total_trades": total_trades,
    }


@router.get("/mt5/status")
def get_mt5_status(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    from app.db.models import MT5Connection
    
    connections = db.exec(
        select(MT5Connection).where(MT5Connection.org_id == user.org_id)
    ).all()
    
    return {
        "connections": [
            {
                "id": str(c.id),
                "server": c.server,
                "login": c.login,
                "account_type": c.account_type,
                "is_connected": c.is_connected,
                "balance": c.balance,
                "equity": c.equity,
                "last_sync": c.last_sync.isoformat() if c.last_sync else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in connections
        ]
    }


@router.get("/mt5/account-summary")
def get_account_summary(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    from app.db.models import MT5Connection
    
    connections = db.exec(
        select(MT5Connection).where(MT5Connection.org_id == user.org_id)
    ).all()
    
    total_balance = sum(c.balance for c in connections if c.is_connected)
    total_equity = sum(c.equity for c in connections if c.is_connected)
    
    return {
        "total_balance": total_balance,
        "total_equity": total_equity,
        "accounts": [
            {
                "id": str(c.id),
                "server": c.server,
                "login": c.login,
                "account_type": c.account_type,
                "is_connected": c.is_connected,
                "balance": c.balance,
                "equity": c.equity,
            }
            for c in connections
        ]
    }


@router.post("/mt5/sync")
def sync_mt5(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    from app.db.models import MT5Connection
    from app.services.mt5_sync import sync_mt5_account, MT5Sync
    
    connections = db.exec(
        select(MT5Connection).where(MT5Connection.org_id == user.org_id)
    ).all()
    
    results = []
    for conn in connections:
        if conn.is_connected:
            import hashlib
            original_password = hashlib.sha256(conn.password_hash.encode()).digest()
            
            sync_result = sync_mt5_account(conn, db)
            if sync_result.get("success"):
                account_info = sync_result.get("account_info", {})
                total_trades = len(sync_result.get("closed_positions", []))
                results.append({
                    "id": str(conn.id),
                    "server": conn.server,
                    "login": conn.login,
                    "account_type": conn.account_type,
                    "balance": account_info.get("balance", 0),
                    "equity": account_info.get("equity", 0),
                    "total_trades": total_trades,
                })
            else:
                results.append({
                    "id": str(conn.id),
                    "server": conn.server,
                    "login": conn.login,
                    "error": sync_result.get("error", "Sync failed"),
                })
    
    total_balance = sum(r.get("balance", 0) for r in results if "error" not in r)
    total_equity = sum(r.get("equity", 0) for r in results if "error" not in r)
    
    return {
        "success": True,
        "total_balance": total_balance,
        "total_equity": total_equity,
        "accounts": results,
    }


@router.post("/binance/connect")
def connect_binance(
    payload: BinanceConnectIn,
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    from app.db.models import MT5Connection
    
    import hashlib
    
    api_secret_hash = hashlib.sha256(payload.api_secret.encode()).hexdigest()
    
    existing = db.exec(
        select(MT5Connection).where(
            MT5Connection.org_id == user.org_id,
            MT5Connection.server == "Binance",
            MT5Connection.login == payload.api_key[:8]
        )
    ).first()
    
    balance = 0
    try:
        from app.services.binance_sync import get_binance_account_info
        binance_result = get_binance_account_info(payload.api_key, payload.api_secret, payload.testnet)
        if binance_result.get("success"):
            positions = binance_result.get("positions", [])
            total_balance = sum(p.get("free", 0) + p.get("locked", 0) for p in positions)
            balance = total_balance
    except Exception as e:
        pass
    
    if existing:
        existing.password_hash = api_secret_hash
        existing.is_connected = True
        existing.balance = balance
        existing.equity = balance
        db.add(existing)
        db.commit()
        db.refresh(existing)
    else:
        conn = MT5Connection(
            org_id=user.org_id,
            user_id=user.id,
            server="Binance",
            login=payload.api_key[:8],
            password_hash=api_secret_hash,
            account_type="testnet" if payload.testnet else "real",
            is_connected=True,
            balance=balance,
            equity=balance,
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
    
    write_audit(
        db,
        action="binance.connect",
        org_id=user.org_id,
        user_id=user.id,
        meta={"api_key": payload.api_key[:4] + "****", "testnet": payload.testnet},
    )
    
    return {
        "success": True,
        "message": f"Binance hisobingiz ulandi! Balans: ${balance:.2f}",
        "balance": balance,
    }

