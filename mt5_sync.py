try:
    import MetaTrader5 as MT5
except ImportError:
    MT5 = None

from typing import Optional, Dict, Any, List
from datetime import datetime


class MT5Sync:
    def __init__(self):
        self.connected = False
    
    def connect(self, server: str, login: str, password: str) -> Dict[str, Any]:
        if MT5 is None:
            return {"success": False, "error": "MetaTrader5 kutubxonasi o'rnatilmagan"}
        
        if not MT5.initialize():
            return {"success": False, "error": str(MT5.last_error())}
        
        if not MT5.login(int(login), password=password, server=server):
            error = str(MT5.last_error())
            MT5.shutdown()
            return {"success": False, "error": error}
        
        self.connected = True
        return {"success": True}
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self.connected:
            return None
        
        account_info = MT5.account_info()
        if account_info is None:
            return None
        
        return {
            "balance": float(account_info.balance),
            "equity": float(account_info.equity),
            "profit": float(account_info.profit),
            "margin": float(account_info.margin),
            "free_margin": float(account_info.margin_free),
            "leverage": account_info.leverage,
            "currency": account_info.currency,
            "server": account_info.server,
            "login": account_info.login,
        }
    
    def get_open_positions(self) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        positions = MT5.positions_get()
        if positions is None:
            return []
        
        result = []
        for pos in positions:
            result.append({
                "ticket": int(pos.ticket),
                "symbol": pos.symbol,
                "type": "buy" if pos.type == 0 else "sell",
                "volume": float(pos.volume),
                "price": float(pos.price_open),
                "current_price": float(pos.price_current),
                "profit": float(pos.profit),
                "swap": float(pos.swap),
                "magic": pos.magic,
                "time": pos.time,
                "comment": pos.comment,
            })
        
        return result
    
    def get_closed_positions(self, from_date: Optional[datetime] = None, to_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        if from_date is None:
            from_date = datetime(2020, 1, 1)
        
        deals = MT5.history_deals_get(from_date, to_date or datetime.now())
        if deals is None:
            return []
        
        result = []
        for deal in deals:
            result.append({
                "ticket": int(deal.ticket),
                "order": int(deal.order),
                "symbol": deal.symbol,
                "type": "buy" if deal.entry == 0 else "sell",
                "volume": float(deal.volume),
                "price": float(deal.price),
                "profit": float(deal.profit),
                "fee": float(deal.fee),
                "swap": float(deal.swap),
                "commission": float(deal.commission),
                "time": deal.time,
                "comment": deal.comment,
            })
        
        return result
    
    def get_total_deposit(self) -> float:
        if not self.connected:
            return 0.0
        
        deposits = MT5.history_deals_get(datetime(2020, 1, 1), datetime.now())
        if deposits is None:
            return 0.0
        
        total = 0.0
        for deal in deposits:
            if deal.entry == 1 and deal.profit > 0:
                total += deal.profit
            elif deal.entry == 0:
                total += deal.volume * deal.price
        
        return total
    
    def shutdown(self):
        self.connected = False
        MT5.shutdown()


def sync_mt5_account(mt5_connection, db) -> Dict[str, Any]:
    from app.db.models import MT5Connection
    from sqlmodel import select
    
    conn = db.exec(
        select(MT5Connection).where(MT5Connection.id == mt5_connection.id)
    ).first()
    
    if not conn:
        return {"success": False, "error": "Connection not found"}
    
    sync = MT5Sync()
    
    result = sync.connect(conn.server, conn.login, conn.password_hash)
    if not result["success"]:
        return result
    
    account_info = sync.get_account_info()
    if account_info:
        conn.balance = account_info["balance"]
        conn.equity = account_info["equity"]
        conn.is_connected = True
        conn.last_sync = datetime.utcnow()
        db.add(conn)
        db.commit()
    
    positions = sync.get_open_positions()
    closed_positions = sync.get_closed_positions()
    
    sync.shutdown()
    
    return {
        "success": True,
        "account_info": account_info,
        "open_positions": positions,
        "closed_positions": closed_positions,
    }


def get_mt5_account_info(server: str, login: str, password: str) -> Dict[str, Any]:
    sync = MT5Sync()
    
    result = sync.connect(server, login, password)
    if not result["success"]:
        return result
    
    account_info = sync.get_account_info()
    if not account_info:
        sync.shutdown()
        return {"success": False, "error": "Account ma'lumotlarini olish mumkin emas"}
    
    positions = sync.get_open_positions()
    closed_positions = sync.get_closed_positions()
    
    sync.shutdown()
    
    return {
        "success": True,
        "account_info": account_info,
        "open_positions": positions,
        "closed_positions": closed_positions,
        "total_trades": len(closed_positions),
    }