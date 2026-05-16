# MT5 EA → GIGIMON webhook (skeleton)

Endpoint:
- `POST /ingest/webhook`

Headers:
- `Content-Type: application/json`
- `X-Gigimon-Secret: <GIGIMON_WEBHOOK_SHARED_SECRET>`

Payload (example):

```json
{
  "org_name": "GIGIMON",
  "source": "mt5_ea",
  "meta": {
    "mt5_server": "YourBroker-Demo",
    "ea_version": "1.0.0"
  },
  "trades": [
    {
      "user_email": "trader@example.com",
      "account": "MT5-ACC-1",
      "symbol": "EURUSD",
      "side": "buy",
      "qty": 0.10,
      "price": 1.095,
      "fee": 0.0,
      "fee_asset": "USD",
      "executed_at": "2026-04-16T10:00:00Z",
      "notes": "EA trade"
    }
  ]
}
```

Notes:
- `user_email` bo‘yicha user topilmasa, skeleton rejimida user avtomatik yaratiladi (prod’da o‘zgartiriladi).
- Dublikatlar hozircha **best-effort**; keyin `client_trade_id` qo‘shib idempotency qilamiz.

