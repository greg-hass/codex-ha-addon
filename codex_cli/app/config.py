"""Configuration settings for the Codex Home Assistant add-on."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    port: int = 8000
    log_level: str = "info"

    codex_home: str = "/data/.codex"
    workspace_dir: str = "/config"

    model: str = ""
    sandbox_mode: str = "workspace-write"
    approval_policy: str = "never"
    enable_web_search: bool = False
    terminal_cols: int = 120
    terminal_rows: int = 36

    model_config = SettingsConfigDict(
        env_prefix="CODEX_ADDON_",
        case_sensitive=False,
    )

    @property
    def codex_home_path(self) -> Path:
        path = Path(self.codex_home)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def workspace_path(self) -> Path:
        path = Path(self.workspace_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


settings = Settings()
