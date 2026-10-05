from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    bot_token: str
    bot_admin_id: int = 0
    database_url: str = "sqlite:///./bot.db"
    default_timezone: str = "UTC"
    focus_warning_cooldown_minutes: int = 10
    focus_max_warnings_per_session: int = 3
    focus_pause_max_duration_minutes: int = 120
    log_level: str = "INFO"
    webapp_url: str = ""
    webapp_port: int = Field(default=8080, validation_alias="PORT")

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
