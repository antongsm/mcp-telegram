"""Configuration management for MCP Telegram.

Handles loading, saving, and validating configuration for both
MTProto (user account) and Bot API connections.
"""

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, SecretStr


def get_config_dir() -> Path:
    """Get the configuration directory path."""
    config_dir = Path(os.getenv("MCP_TELEGRAM_CONFIG_DIR", "~/.mcp-telegram")).expanduser()
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_path() -> Path:
    """Get the configuration file path."""
    return get_config_dir() / "config.json"


def get_session_path() -> Path:
    """Get the MTProto session file path."""
    return get_config_dir() / "session"


def get_pid_path() -> Path:
    """Get the daemon PID file path."""
    return get_config_dir() / "daemon.pid"


def get_log_path() -> Path:
    """Get the daemon log file path."""
    return get_config_dir() / "daemon.log"


def get_downloads_dir() -> Path:
    """Get the downloads directory path."""
    downloads = get_config_dir() / "downloads"
    downloads.mkdir(parents=True, exist_ok=True)
    return downloads


class UserConfig(BaseModel):
    """MTProto user account configuration."""

    api_id: str = Field(default="", description="Telegram API ID from my.telegram.org")
    api_hash: str = Field(default="", description="Telegram API Hash from my.telegram.org")
    phone: str = Field(default="", description="Phone number in international format")

    @property
    def is_configured(self) -> bool:
        """Check if user config is complete."""
        return bool(self.api_id and self.api_hash and self.phone)


class BotConfig(BaseModel):
    """Telegram Bot API configuration."""

    token: str = Field(default="", description="Bot token from @BotFather")
    chat_id: str = Field(default="", description="Default chat ID for notifications")

    @property
    def is_configured(self) -> bool:
        """Check if bot config is complete."""
        return bool(self.token)


class DaemonConfig(BaseModel):
    """Daemon configuration."""

    host: str = Field(default="127.0.0.1", description="Daemon bind host")
    port: int = Field(default=19876, description="Daemon bind port")

    @property
    def url(self) -> str:
        """Get daemon URL."""
        return f"http://{self.host}:{self.port}"


class Config(BaseModel):
    """Main configuration."""

    user: UserConfig = Field(default_factory=UserConfig)
    bot: BotConfig = Field(default_factory=BotConfig)
    daemon: DaemonConfig = Field(default_factory=DaemonConfig)

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file or create default."""
        config_path = get_config_path()

        if config_path.exists():
            try:
                data = json.loads(config_path.read_text())
                return cls.model_validate(data)
            except Exception:
                pass

        return cls()

    def save(self) -> None:
        """Save configuration to file."""
        config_path = get_config_path()
        config_path.write_text(
            json.dumps(self.model_dump(), indent=2)
        )

    @property
    def has_user(self) -> bool:
        """Check if user (MTProto) is configured."""
        return self.user.is_configured

    @property
    def has_bot(self) -> bool:
        """Check if bot is configured."""
        return self.bot.is_configured


def load_config() -> Config:
    """Load configuration (convenience function)."""
    return Config.load()


def save_config(config: Config) -> None:
    """Save configuration (convenience function)."""
    config.save()
