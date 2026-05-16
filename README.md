# GIGIMON (backend skeleton)

Smart trading journal backend (MVP skeleton).

## Features (skeleton)
- Multi-user + Organization (tenant) model
- Trade journal ingestion:
  - MT5 EA / external bots via webhook (JSON)
  - Exchange polling adapter skeleton (Binance placeholder)
- AI analysis pipeline (cloud AI, OpenAI-compatible endpoint)
- Periodic reports: daily/weekly/monthly/quarterly/yearly (scheduler)
- Delivery channels: API + Email/Telegram (placeholders)
- Export: Excel (`.xlsx`)

## Quickstart (local)

```bash
cd /Applications/gigimon
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Open API docs: `http://127.0.0.1:8000/docs`

## Notes
- Auth is skeleton: Google OAuth + phone verification endpoints are stubbed.
- SQLite is used for fast local start; schema is designed to migrate to Postgres later.

