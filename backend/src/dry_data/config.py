"""Application configuration via environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dry Data application settings.

    All values can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Paths
    project_root: Path = Path(__file__).resolve().parent.parent.parent
    duckdb_path: Path = Path("data/dry_data.duckdb")
    raw_data_dir: Path = Path("data/raw")
    cleaned_data_dir: Path = Path("data/cleaned")

    # OpenAI
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"

    # FRED
    fred_api_key: str = ""

    # Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging
    log_level: str = "INFO"

    # Query safety
    max_query_rows: int = 1000
    query_timeout_seconds: int = 30

    @property
    def raw_dir(self) -> Path:
        """Absolute path to raw data directory."""
        return self.project_root / self.raw_data_dir

    @property
    def cleaned_dir(self) -> Path:
        """Absolute path to cleaned data directory."""
        return self.project_root / self.cleaned_data_dir

    @property
    def db_path(self) -> Path:
        """Absolute path to DuckDB file."""
        return self.project_root / self.duckdb_path


# Singleton — import this from anywhere
settings = Settings()
