from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from app.db.models import ReportPeriod


@dataclass(frozen=True)
class PeriodWindow:
    start_utc: datetime
    end_utc: datetime


def _tzinfo(tz: str):
    if ZoneInfo is None:
        return timezone.utc
    try:
        return ZoneInfo(tz)
    except Exception:
        return timezone.utc


def last_closed_window(period: ReportPeriod, *, tz: str, now_utc: datetime | None = None) -> PeriodWindow:
    """
    Returns the last fully closed window for the given period.
    For skeleton: uses user tz (if available), then converts boundaries to UTC.
    """
    now_utc = now_utc or datetime.now(timezone.utc)
    tzinfo = _tzinfo(tz)
    now_local = now_utc.astimezone(tzinfo)

    if period == ReportPeriod.daily:
        end_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        start_local = end_local - timedelta(days=1)
    elif period == ReportPeriod.weekly:
        # week starts Monday
        end_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = end_local - timedelta(days=end_local.weekday())
        start_local = end_local - timedelta(days=7)
    elif period == ReportPeriod.monthly:
        end_local = now_local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if end_local.month == 1:
            start_local = end_local.replace(year=end_local.year - 1, month=12)
        else:
            start_local = end_local.replace(month=end_local.month - 1)
    elif period == ReportPeriod.quarterly:
        q = (now_local.month - 1) // 3 + 1
        q_start_month = 3 * (q - 1) + 1
        end_local = now_local.replace(month=q_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        # move to start of current quarter, then subtract 3 months for previous quarter
        m = end_local.month - 3
        y = end_local.year
        if m <= 0:
            m += 12
            y -= 1
        start_local = end_local.replace(year=y, month=m)
    else:  # yearly
        end_local = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        start_local = end_local.replace(year=end_local.year - 1)

    return PeriodWindow(start_utc=start_local.astimezone(timezone.utc), end_utc=end_local.astimezone(timezone.utc))

