from __future__ import annotations

from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.db.engine import engine
from app.db.models import ReportPeriod, User
from app.services.reports import generate_period_report
from app.services.time import last_closed_window


async def _generate_for_all_users(period: ReportPeriod) -> None:
    # APScheduler calls this in the event loop (AsyncIOScheduler).
    with Session(engine) as db:
        users = db.exec(select(User).where(User.is_active.is_(True))).all()
        for u in users:
            w = last_closed_window(period, tz=u.tz, now_utc=datetime.now(timezone.utc))
            await generate_period_report(
                db,
                org_id=u.org_id,
                user_id=u.id,
                period=period,
                start=w.start_utc,
                end=w.end_utc,
            )


def start_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=timezone.utc)

    # Daily at 00:05 UTC (report window uses user tz to compute "last closed" day)
    scheduler.add_job(_generate_for_all_users, CronTrigger(hour=0, minute=5), args=[ReportPeriod.daily])
    # Weekly Monday 00:10 UTC
    scheduler.add_job(_generate_for_all_users, CronTrigger(day_of_week="mon", hour=0, minute=10), args=[ReportPeriod.weekly])
    # Monthly 1st 00:15 UTC
    scheduler.add_job(_generate_for_all_users, CronTrigger(day=1, hour=0, minute=15), args=[ReportPeriod.monthly])
    # Quarterly: Jan/Apr/Jul/Oct 1st 00:20 UTC
    scheduler.add_job(_generate_for_all_users, CronTrigger(month="1,4,7,10", day=1, hour=0, minute=20), args=[ReportPeriod.quarterly])
    # Yearly: Jan 1st 00:25 UTC
    scheduler.add_job(_generate_for_all_users, CronTrigger(month=1, day=1, hour=0, minute=25), args=[ReportPeriod.yearly])

    scheduler.start()
    return scheduler

