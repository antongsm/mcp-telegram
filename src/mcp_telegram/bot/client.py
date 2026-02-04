"""Telegram Bot API client.

This module provides a clean interface for Telegram Bot API:
- Sending messages, files, photos, voice from a bot
- Receiving messages from users
- Downloading files
"""

import logging
from pathlib import Path
from typing import Any

import httpx

from mcp_telegram.config import Config

logger = logging.getLogger(__name__)

BOT_API_BASE = "https://api.telegram.org/bot"


class BotClient:
    """Telegram Bot API client."""

    def __init__(self, config: Config):
        self.config = config

    @property
    def token(self) -> str:
        """Get bot token."""
        if not self.config.bot.token:
            raise RuntimeError("Bot not configured. Run 'tg login' first.")
        return self.config.bot.token

    @property
    def default_chat_id(self) -> str:
        """Get default chat ID."""
        return self.config.bot.chat_id

    @property
    def api_url(self) -> str:
        """Get Bot API base URL."""
        return f"{BOT_API_BASE}{self.token}"

    async def _request(
        self,
        method: str,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make a request to Bot API.

        Args:
            method: API method name
            data: Request data
            files: Files to upload

        Returns:
            API response dict
        """
        url = f"{self.api_url}/{method}"

        async with httpx.AsyncClient(timeout=60.0) as client:
            if files:
                response = await client.post(url, data=data, files=files)
            else:
                response = await client.post(url, json=data)

            result = response.json()

            if not result.get("ok"):
                error = result.get("description", "Unknown error")
                raise RuntimeError(f"Bot API error: {error}")

            return result.get("result", {})

    async def get_me(self) -> dict[str, Any]:
        """Get bot info."""
        return await self._request("getMe")

    async def send_message(
        self,
        text: str,
        chat_id: str | None = None,
        parse_mode: str = "Markdown",
    ) -> dict[str, Any]:
        """Send a text message.

        Args:
            text: Message text (supports Markdown)
            chat_id: Target chat ID (uses default if not specified)
            parse_mode: Parse mode (Markdown or HTML)

        Returns:
            Sent message info
        """
        return await self._request("sendMessage", {
            "chat_id": chat_id or self.default_chat_id,
            "text": text,
            "parse_mode": parse_mode,
        })

    async def send_document(
        self,
        file_path: str,
        caption: str = "",
        chat_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a document/file.

        Args:
            file_path: Path to file
            caption: Optional caption
            chat_id: Target chat ID

        Returns:
            Sent message info
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            return await self._request(
                "sendDocument",
                data={
                    "chat_id": chat_id or self.default_chat_id,
                    "caption": caption,
                },
                files={"document": (path.name, f)},
            )

    async def send_photo(
        self,
        file_path: str,
        caption: str = "",
        chat_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a photo.

        Args:
            file_path: Path to image file
            caption: Optional caption
            chat_id: Target chat ID

        Returns:
            Sent message info
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            return await self._request(
                "sendPhoto",
                data={
                    "chat_id": chat_id or self.default_chat_id,
                    "caption": caption,
                },
                files={"photo": (path.name, f)},
            )

    async def send_voice(
        self,
        file_path: str,
        caption: str = "",
        chat_id: str | None = None,
    ) -> dict[str, Any]:
        """Send a voice message.

        Args:
            file_path: Path to audio file (.ogg with OPUS preferred)
            caption: Optional caption
            chat_id: Target chat ID

        Returns:
            Sent message info
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        with open(path, "rb") as f:
            return await self._request(
                "sendVoice",
                data={
                    "chat_id": chat_id or self.default_chat_id,
                    "caption": caption,
                },
                files={"voice": (path.name, f)},
            )

    async def get_updates(
        self,
        offset: int | None = None,
        limit: int = 10,
        timeout: int = 0,
    ) -> list[dict[str, Any]]:
        """Get incoming updates (messages).

        Args:
            offset: Identifier of the first update to be returned
            limit: Maximum number of updates
            timeout: Long polling timeout in seconds

        Returns:
            List of updates
        """
        data: dict[str, Any] = {"limit": limit, "timeout": timeout}
        if offset:
            data["offset"] = offset

        return await self._request("getUpdates", data)

    async def get_messages(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent messages from bot chat.

        This is a convenience wrapper around get_updates that
        extracts just the messages.

        Args:
            limit: Maximum number of messages

        Returns:
            List of message dicts
        """
        updates = await self.get_updates(limit=limit)
        messages = []

        for update in updates:
            msg = update.get("message", {})
            if msg:
                messages.append({
                    "update_id": update.get("update_id"),
                    "message_id": msg.get("message_id"),
                    "date": msg.get("date"),
                    "text": msg.get("text", ""),
                    "from": msg.get("from", {}),
                    "chat": msg.get("chat", {}),
                    "has_photo": "photo" in msg,
                    "has_document": "document" in msg,
                    "has_voice": "voice" in msg,
                })

        return messages

    async def download_file(
        self,
        file_id: str,
        save_path: str,
    ) -> dict[str, Any]:
        """Download a file by file_id.

        Args:
            file_id: Telegram file_id from a message
            save_path: Path to save the file

        Returns:
            Dict with downloaded file path
        """
        # Get file path from Telegram
        file_info = await self._request("getFile", {"file_id": file_id})
        file_path = file_info.get("file_path")

        if not file_path:
            raise ValueError("Could not get file path")

        # Download the file
        download_url = f"https://api.telegram.org/file/bot{self.token}/{file_path}"

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.get(download_url)
            response.raise_for_status()

            save = Path(save_path)
            save.parent.mkdir(parents=True, exist_ok=True)
            save.write_bytes(response.content)

            return {"path": str(save.resolve())}

    async def get_chat_id(self) -> str | None:
        """Get chat ID from recent messages.

        Useful for initial setup - send a message to the bot,
        then call this to get the chat ID.

        Returns:
            Chat ID or None if no messages
        """
        updates = await self.get_updates(limit=1)
        if updates:
            msg = updates[0].get("message", {})
            chat = msg.get("chat", {})
            return str(chat.get("id", ""))
        return None
