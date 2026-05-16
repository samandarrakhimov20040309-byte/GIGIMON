import json
from collections import Counter
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlmodel import Session, select

from app.db.models import Insight, Report, ReportPeriod, Trade
from app.services.ai import generate_insight


def build_report_payload(trades: list[Trade], *, period: ReportPeriod, start: datetime, end: datetime) -> dict[str, Any]:
    symbols = [t.symbol for t in trades]
    sides = [t.side.lower() for t in trades]
    fees_total = sum(t.fee for t in trades)

    top_symbols = Counter(symbols).most_common(10)
    side_counts = Counter(sides)

    # Basic "risk rules" (MVP heuristics; real rules will use positions, SL/TP, leverage, equity)
    rule_flags: list[str] = []
    if len(trades) >= 50:
        rule_flags.append("overtrading_suspected")
    if side_counts.get("buy", 0) == 0 or side_counts.get("sell", 0) == 0:
        rule_flags.append("one_sided_bias")

    return {
        "period": period.value,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "trade_count": len(trades),
        "fees_total": fees_total,
        "top_symbols": top_symbols,
        "side_counts": dict(side_counts),
        "rule_flags": rule_flags,
    }


async def generate_period_report(
    db: Session,
    *,
    org_id: UUID,
    user_id: UUID,
    period: ReportPeriod,
    start: datetime,
    end: datetime,
) -> tuple[Report, Insight]:
    trades = db.exec(
        select(Trade)
        .where(Trade.org_id == org_id, Trade.user_id == user_id, Trade.executed_at >= start, Trade.executed_at < end)
        .order_by(Trade.executed_at.asc())
    ).all()

    payload = build_report_payload(trades, period=period, start=start, end=end)

    report = Report(
        org_id=org_id,
        user_id=user_id,
        period=period,
        period_start=start,
        period_end=end,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    ai = await generate_insight(report_payload=payload)
    insight = Insight(
        report_id=report.id,
        model=ai.get("model", ""),
        advice_markdown=ai.get("advice_markdown", ""),
        score_json=json.dumps(ai.get("scores", {}), ensure_ascii=False),
        actions_json=json.dumps(ai.get("actions", []), ensure_ascii=False),
    )
    db.add(insight)
    db.commit()
    db.refresh(insight)
    return report, insight

