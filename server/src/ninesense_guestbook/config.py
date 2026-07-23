from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "sqlite:////var/lib/ninesense/guestbook.sqlite3"
    contact_key: str
    security_key: str
    session_pepper: str
    rate_limit_key: str
    cookie_secure: bool = False
    cookie_name: str = "ninesense_admin"
    session_hours: int = 8
    login_challenge_minutes: int = 5
    smtp_host: str = ""
    smtp_port: int = 465
    smtp_username: str = ""
    smtp_password: str = ""
    notification_to: str = ""
    public_admin_url: str = "/admin/"

    model_config = SettingsConfigDict(env_prefix="NINESENSE_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
