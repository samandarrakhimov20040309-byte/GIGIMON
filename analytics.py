import json
from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.db.engine import get_session
from app.db.models import Trade, TradeStatus, UserSetting
from app.services.analytics_service import compute_analytics
from app.services.ai import generate_insight
from app.services.audit import write_audit
from app.services.deps import CurrentUser

router = APIRouter()


def _load_saved_ai(db: Session, user_id) -> Optional[dict]:
    row = db.exec(
        select(UserSetting).where(
            UserSetting.user_id == user_id,
            UserSetting.key == "last_ai_data",
        )
    ).first()
    if row and row.value:
        try:
            return json.loads(row.value)
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def _save_ai_result(db: Session, user_id: str, ai_data: dict):
    existing = db.exec(
        select(UserSetting).where(
            UserSetting.user_id == user_id,
            UserSetting.key == "last_ai_data",
        )
    ).first()
    val = json.dumps(ai_data, ensure_ascii=False)
    if existing:
        existing.value = val
        db.add(existing)
    else:
        db.add(UserSetting(user_id=user_id, key="last_ai_data", value=val))


@router.post("/analyze")
async def analyze(
    user: CurrentUser,
    db: Annotated[Session, Depends(get_session)],
):
    rows = db.exec(
        select(Trade)
        .where(
            Trade.org_id == user.org_id,
            Trade.user_id == user.id,
            Trade.status == TradeStatus.active,
            Trade.exit_price.isnot(None),
        )
        .order_by(Trade.executed_at.asc())
    ).all()

    result = compute_analytics(list(rows))

    data = result.to_dict()
    data["initial_balance"] = 0.0

    setting = db.exec(
        select(UserSetting).where(
            UserSetting.user_id == user.id,
            UserSetting.key == "initial_balance",
        )
    ).first()
    if setting:
        try:
            data["initial_balance"] = float(setting.value)
        except (ValueError, TypeError):
            pass

    equity = data["initial_balance"]
    for pnl_entry in result.metrics.pnls:
        equity += pnl_entry
    data["current_equity"] = round(equity, 2)
    data["roi"] = round(
        ((equity - data["initial_balance"]) / data["initial_balance"] * 100) if data["initial_balance"] > 0 else 0,
        2,
    )

    user_ai_key_setting = db.exec(
        select(UserSetting).where(
            UserSetting.user_id == user.id,
            UserSetting.key == "ai_api_key",
        )
    ).first()
    user_ai_key = user_ai_key_setting.value if user_ai_key_setting else ""
    user_ai_provider_setting = db.exec(
        select(UserSetting).where(
            UserSetting.user_id == user.id,
            UserSetting.key == "ai_provider",
        )
    ).first()
    user_ai_provider = user_ai_provider_setting.value if user_ai_provider_setting else ""

    now_dt = datetime.now()
    today = now_dt.strftime("%Y-%m-%d")
    hour = now_dt.hour
    minute = now_dt.minute

    SLOTS = [
        {"label": "14:20", "hour": 14, "minute": 20, "id": "14"},
        {"label": "23:30", "hour": 23, "minute": 30, "id": "23"},
    ]

    def get_current_slot():
        for s in SLOTS:
            if hour == s["hour"] and minute >= s["minute"]:
                return s
            if hour == s["hour"] and s["minute"] - 15 <= minute < s["minute"]:
                return s
        return None

    def get_next_slot_str():
        for s in SLOTS:
            if hour < s["hour"] or (hour == s["hour"] and minute < s["minute"]):
                return s["label"]
        return "ertaga 14:20"

    current_slot = get_current_slot()

    last_slot_setting = db.exec(
        select(UserSetting).where(
            UserSetting.user_id == user.id,
            UserSetting.key == "last_ai_slot",
        )
    ).first()

    slot_already_done = False
    if last_slot_setting and current_slot:
        slot_already_done = last_slot_setting.value == f"{today}-{current_slot['id']}"

    saved = _load_saved_ai(db, user.id)

    if not current_slot or slot_already_done:
        next_time = get_next_slot_str()
        if saved:
            data["ai"] = dict(saved)
            note = "✅ Jadval bo'yicha yangilandi" if slot_already_done else f"📅 Keyingi yangilanish: **{next_time}**"
            data["ai"]["advice_markdown"] = f"<div style='font-size:12px;color:#a3aac4;margin-bottom:8px;'>{note}</div>\n{data['ai']['advice_markdown']}"
        else:
            data["ai"] = {
                "advice_markdown": f"AI tahlil jadval bo'yicha ishlaydi. Birinchi avtomatik tahlil **{next_time}** da boshlanadi. 💬 Chat tugma orqali istalgan vaqtda savol berishingiz mumkin.",
                "scores": {"intizom": 0, "risk_boshqaruvi": 0, "barqarorlik": 0, "pattern_aniqlash": 0, "sizing": 0},
                "actions": [],
                "model": "",
            }
    else:
        condensed = {
            "trade_count": data["trade_count"],
            "total_pnl": data["metrics"]["total_pnl"],
            "win_rate": data["metrics"]["win_rate"],
            "profit_factor": data["metrics"]["profit_factor"],
            "sharpe_ratio": data["metrics"]["sharpe_ratio"],
            "max_drawdown": data["metrics"]["max_drawdown"],
            "avg_win": data["metrics"]["avg_win"],
            "avg_loss": data["metrics"]["avg_loss"],
            "expectancy": data["metrics"]["expectancy"],
            "avg_duration_hours": data["metrics"]["avg_duration_hours"],
            "best_hour": data["patterns"]["best_hour"],
            "worst_hour": data["patterns"]["worst_hour"],
            "best_day": data["patterns"]["best_day"],
            "worst_day": data["patterns"]["worst_day"],
            "best_symbol": data["patterns"]["best_symbol"],
            "worst_symbol": data["patterns"]["worst_symbol"],
            "buy_win_rate": data["patterns"]["buy"]["win_rate"],
            "sell_win_rate": data["patterns"]["sell"]["win_rate"],
            "max_consecutive_wins": data["sequence"]["max_consecutive_wins"],
            "max_consecutive_losses": data["sequence"]["max_consecutive_losses"],
            "recovery_factor": data["sequence"]["recovery_factor"],
            "avg_size": data["sizing"]["avg_size"],
            "size_pnl_correlation": data["sizing"]["size_pnl_correlation"],
            "optimal_size": data["sizing"]["optimal_size"],
            "avg_risk_percent": data["sizing"]["avg_risk_percent"],
            "notes_positive_ratio": data["notes_analysis"]["positive_ratio"],
            "notes_strategies": data["notes_analysis"]["strategies"],
            "notes_emotions": data["notes_analysis"]["emotions"],
            "summary": data["summary"],
            "roi": data["roi"],
        }
        try:
            ai = await generate_insight(report_payload=condensed, api_key=user_ai_key, provider=user_ai_provider)
            ai_data = {
                "advice_markdown": ai.get("advice_markdown", ""),
                "scores": ai.get("scores", {}),
                "actions": ai.get("actions", []),
                "model": ai.get("model", ""),
            }
            data["ai"] = dict(ai_data)
            data["ai"]["advice_markdown"] = f"<div style='font-size:12px;color:#6bff8f;margin-bottom:8px;'>✅ {current_slot['label']} da yangilandi</div>\n{data['ai']['advice_markdown']}"
            slot_val = f"{today}-{current_slot['id']}"
            if last_slot_setting:
                last_slot_setting.value = slot_val
                db.add(last_slot_setting)
            else:
                db.add(UserSetting(user_id=user.id, key="last_ai_slot", value=slot_val))
            _save_ai_result(db, user.id, ai_data)
            db.commit()
        except Exception:
            if saved:
                data["ai"] = dict(saved)
                data["ai"]["advice_markdown"] = f"<div style='font-size:12px;color:#ff716c;margin-bottom:8px;'>⚠️ AI hozir ishlamadi. Avvalgi tahlil ko'rsatilmoqda.</div>\n{data['ai']['advice_markdown']}"
            else:
                data["ai"] = {
                    "advice_markdown": f"AI tahlil vaqtincha mavjud emas. {get_next_slot_str()} da qayta urinib ko'ring.",
                    "scores": {"intizom": 0, "risk_boshqaruvi": 0, "barqarorlik": 0, "pattern_aniqlash": 0, "sizing": 0},
                    "actions": [],
                    "model": "",
                }

    write_audit(
        db,
        action="analytics.analyze",
        org_id=user.org_id,
        user_id=user.id,
        meta={"trade_count": len(rows)},
    )

    return data
