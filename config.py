"""Configuration management for Tyre Invoice Consolidator & Dashboard.

Uses pydantic-settings to manage environment variables and provide type-safe
settings with sensible defaults.
"""

from pathlib import Path
from typing import Dict, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Telegram Bot Settings
    bot_token: str = Field(
        default="1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ_MOCK",
        description="Telegram bot token obtained from @BotFather",
        alias="BOT_TOKEN",
    )

    # AI Provider Settings ('gemini' or 'deepseek')
    ai_provider: str = Field(
        default="gemini",
        description="Active AI Provider: 'gemini' or 'deepseek'",
        alias="AI_PROVIDER",
    )

    # Google Gemini Settings (Vision AI)
    gemini_api_key: Optional[str] = Field(
        default=None,
        description="Google Gemini API key",
        alias="GEMINI_API_KEY",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model name (e.g. gemini-2.5-flash, gemini-2.0-flash, gemini-1.5-flash)",
        alias="GEMINI_MODEL",
    )

    # DeepSeek Settings
    deepseek_api_key: Optional[str] = Field(
        default=None,
        description="DeepSeek API key",
        alias="DEEPSEEK_API_KEY",
    )
    deepseek_model: str = Field(
        default="google/gemini-3.1-flash-lite-image",
        description="OpenRouter/DeepSeek vision model name",
        alias="DEEPSEEK_MODEL",
    )
    deepseek_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="API base URL for OpenRouter / DeepSeek",
        alias="DEEPSEEK_BASE_URL",
    )

    # Album debouncing window in seconds
    album_debounce_seconds: float = Field(
        default=3.5,
        description="Sliding debounce delay in seconds to collect multi-image albums",
        alias="ALBUM_DEBOUNCE_SECONDS",
    )

    # Web Dashboard Settings
    web_host: str = Field(
        default="0.0.0.0",
        description="Host address for the web dashboard server",
        alias="WEB_HOST",
    )
    web_port: int = Field(
        default=8000,
        description="Port for the web dashboard server",
        alias="WEB_PORT",
    )

    # Directory Paths
    temp_dir: Path = Field(
        default=Path("./temp_downloads"),
        description="Directory for temporary downloaded images",
        alias="TEMP_DIR",
    )
    output_dir: Path = Field(
        default=Path("./output_invoices"),
        description="Directory for generated PDF invoices",
        alias="OUTPUT_DIR",
    )
    db_path: Path = Field(
        default=Path("./invoices.db"),
        description="Path to SQLite database file",
        alias="DB_PATH",
    )

    # Invoice Business Settings
    currency: str = Field(
        default="MAD",
        description="Currency symbol used in invoices (e.g. MAD or DH)",
        alias="CURRENCY",
    )
    company_name: str = Field(
        default="Tous Pneus",
        description="Company name displayed on invoice headers",
        alias="COMPANY_NAME",
    )
    company_address: str = Field(
        default="189 LOT ANOUAR SIDI BENNOUR MAROC Sidi Bennour",
        description="Company physical address displayed on invoice headers",
        alias="COMPANY_ADDRESS",
    )
    company_phone: str = Field(
        default="+212618468839",
        description="Company telephone contact number",
        alias="COMPANY_PHONE",
    )
    company_email: str = Field(
        default="oraiche-pneus@gmail.com",
        description="Company email address",
        alias="COMPANY_EMAIL",
    )

    def setup_directories(self) -> None:
        """Ensure temporary and output directories exist."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)


def update_env_file(updates: Dict[str, str]) -> None:
    """Persist updated key-value pairs to the local .env file."""
    env_path = Path(".env")
    lines = []
    existing_keys = set()
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _ = stripped.split("=", 1)
            k = k.strip()
            if k in updates:
                new_lines.append(f"{k}={updates[k]}")
                existing_keys.add(k)
                continue
        new_lines.append(line)

    for k, v in updates.items():
        if k not in existing_keys and v is not None:
            new_lines.append(f"{k}={v}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


# Global settings singleton instance
settings = Settings()
settings.setup_directories()
