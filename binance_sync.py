from typing import Optional, Dict, Any, List


try:
    import ccxt
except ImportError:
    ccxt = None


class BinanceSync:
    def __init__(self):
        self.exchange = None
        self.connected = False
    
    def connect(self, api_key: str, api_secret: str, testnet: bool = False) -> Dict[str, Any]:
        if ccxt is None:
            return {"success": False, "error": "ccxt kutubxonasi o'rnatilmagan. Run: pip install ccxt"}
        
        try:
            if testnet:
                self.exchange = ccxt.binance({
                    'apiKey': api_key,
                    'secret': api_secret,
                    'testnet': True,
                    'enableRateLimit': True,
                })
            else:
                self.exchange = ccxt.binance({
                    'apiKey': api_key,
                    'secret': api_secret,
                    'enableRateLimit': True,
                })
            
            balance = self.exchange.fetch_balance()
            self.connected = True
            
            return {"success": True, "balance": balance}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_account_info(self) -> Optional[Dict[str, Any]]:
        if not self.connected or not self.exchange:
            return None
        
        try:
            balance = self.exchange.fetch_balance()
            info = balance.get('info', {})
            
            return {
                "balance": float(info.get('balance', 0)),
                "equity": float(info.get('totalAssetBtc', 0)),
            }
        except:
            return None
    
    def get_positions(self) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        try:
            positions = self.exchange.fetch_balance()
            result = []
            
            for symbol, data in positions.get('free', {}).items():
                if float(data) > 0:
                    result.append({
                        "symbol": symbol,
                        "free": float(data),
                        "locked": float(positions.get('used', {}).get(symbol, 0)),
                    })
            
            return result
        except:
            return []
    
    def get_trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.connected:
            return []
        
        return []
    
    def close(self):
        self.connected = False
        self.exchange = None


def get_binance_account_info(api_key: str, api_secret: str, testnet: bool = False) -> Dict[str, Any]:
    sync = BinanceSync()
    
    result = sync.connect(api_key, api_secret, testnet)
    if not result.get("success"):
        return result
    
    positions = sync.get_positions()
    trades = sync.get_trades()
    
    sync.close()
    
    return {
        "success": True,
        "positions": positions,
        "total_trades": len(trades),
    }