from fastapi import APIRouter

from app.api.routes import ai_assistant, analytics, auth, health, ingest, notifications, reports, settings, trades, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(trades.router, prefix="/trades", tags=["trades"])
api_router.include_router(ingest.router, prefix="/ingest", tags=["ingest"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(ai_assistant.router, prefix="/ai", tags=["ai_assistant"])

