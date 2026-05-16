from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GIGIMON_", env_file=".env", extra="ignore")

    env: str = "dev"
    app_name: str = "GIGIMON"
    base_url: AnyHttpUrl = "http://127.0.0.1:8000"

    database_url: str = "sqlite:///./gigimon.db"

    jwt_secret: str = "change-me"
    jwt_issuer: str = "gigimon"
    access_token_minutes: int = 1440  # 24 hours

    # AI (cloud, OpenAI-compatible)
    ai_provider: str = "openai"  # openai | gemini
    ai_base_url: str = "https://api.openai.com/v1"
    ai_api_key: str = ""
    ai_model: str = "gpt-4.1-mini"

    # Google OAuth skeleton
    google_client_id: str = ""
    google_client_secret: str = ""

    # Phone verification skeleton
    sms_provider: str = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""

    # Delivery skeleton
    email_from: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    telegram_bot_token: str = ""

    # Integrations
    webhook_shared_secret: str = "change-me-too"


settings = Settings()

