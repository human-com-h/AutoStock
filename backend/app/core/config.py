from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="AUTOSTOCK_")

    app_name: str = "AutoStock"
    data_dir: Path = Path.home() / "AppData" / "Roaming" / "AutoStock"
    db_filename: str = "autostock.db"
    port_https: int = 8756
    port_http: int = 8757
    allow_negative_stock_default: bool = True
    session_cookie_name: str = "autostock_session"
    session_max_age_days: int = 30
    localhost_auto_login: bool = True
    open_browser_on_start: bool = True

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"


settings = Settings()
