"""MTProto user client for sending messages from personal Telegram account.

This module wraps Telethon to provide a clean interface for:
- Sending messages, files, voice notes from your account
- Reading messages from any chat
- Searching dialogs/contacts
- Downloading media
"""

import logging
from pathlib import Path
from typing import Any

from telethon import TelegramClient
from telethon.tl import types, patched

from mcp_telegram.config import Config, get_session_path

logger = logging.getLogger(__name__)


class UserClient:
    """MTProto client wrapper for user account operations."""

    def __init__(self, config: Config):
        self.config = config
        self._client: TelegramClient | None = None

    @property
    def client(self) -> TelegramClient:
        """Get or create the Telegram client."""
        if self._client is None:
            if not self.config.user.is_configured:
                raise RuntimeError(
                    "User not configured. Run 'tg login' first."
                )
            self._client = TelegramClient(
                str(get_session_path()),
                int(self.config.user.api_id),
                self.config.user.api_hash,
            )
        return self._client

    async def connect(self) -> None:
        """Connect to Telegram."""
        if not self.client.is_connected():
            await self.client.connect()

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()

    async def is_authorized(self) -> bool:
        """Check if the user is authorized."""
        await self.connect()
        return await self.client.is_user_authorized()

    async def get_me(self) -> dict[str, Any]:
        """Get current user info."""
        await self.connect()
        me = await self.client.get_me()
        if me:
            return {
                "id": me.id,
                "first_name": me.first_name,
                "last_name": me.last_name,
                "username": me.username,
                "phone": me.phone,
            }
        return {}

    async def send_message(
        self,
        entity: str | int,
        message: str,
        reply_to: int | None = None,
    ) -> dict[str, Any]:
        """Send a text message.

        Args:
            entity: Username (@user), phone (+123...), or chat ID
            message: Text message to send
            reply_to: Optional message ID to reply to

        Returns:
            Dict with message_id and chat_id
        """
        await self.connect()
        result = await self.client.send_message(
            entity,
            message,
            reply_to=reply_to,
        )
        return {
            "message_id": result.id,
            "chat_id": result.chat_id,
        }

    async def send_file(
        self,
        entity: str | int,
        file_path: str,
        caption: str = "",
        voice: bool = False,
    ) -> dict[str, Any]:
        """Send a file.

        Args:
            entity: Username, phone, or chat ID
            file_path: Path to file to send
            caption: Optional caption
            voice: Send as voice message (for audio files)

        Returns:
            Dict with message_id and chat_id
        """
        await self.connect()
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        result = await self.client.send_file(
            entity,
            file_path,
            caption=caption,
            voice_note=voice,
        )
        return {
            "message_id": result.id,
            "chat_id": result.chat_id,
        }

    async def get_messages(
        self,
        entity: str | int,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Get messages from a chat.

        Args:
            entity: Username, phone, or chat ID
            limit: Number of messages to fetch

        Returns:
            List of message dicts
        """
        await self.connect()
        messages = []

        async for msg in self.client.iter_messages(entity, limit=limit):
            if isinstance(msg, patched.MessageService | patched.MessageEmpty):
                continue

            msg_data: dict[str, Any] = {
                "id": msg.id,
                "date": msg.date.isoformat() if msg.date else None,
                "text": msg.text or "",
                "from_id": msg.sender_id,
                "has_media": msg.media is not None,
            }

            # Determine media type
            if msg.media:
                if isinstance(msg.media, types.MessageMediaPhoto):
                    msg_data["media_type"] = "photo"
                elif isinstance(msg.media, types.MessageMediaDocument):
                    msg_data["media_type"] = "document"
                    # Try to get filename
                    if msg.media.document:
                        for attr in msg.media.document.attributes:
                            if isinstance(attr, types.DocumentAttributeFilename):
                                msg_data["file_name"] = attr.file_name
                            elif isinstance(attr, types.DocumentAttributeAudio):
                                if attr.voice:
                                    msg_data["media_type"] = "voice"
                                else:
                                    msg_data["media_type"] = "audio"
                else:
                    msg_data["media_type"] = "other"

            messages.append(msg_data)

        return messages

    async def search_dialogs(
        self,
        query: str = "",
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search or list dialogs.

        Args:
            query: Search query (empty for recent dialogs)
            limit: Number of results

        Returns:
            List of dialog dicts
        """
        await self.connect()
        dialogs = []

        async for dialog in self.client.iter_dialogs(limit=limit):
            entity = dialog.entity
            dialog_data: dict[str, Any] = {
                "id": dialog.id,
                "name": dialog.name,
                "unread_count": dialog.unread_count,
            }

            # Determine type
            if isinstance(entity, types.User):
                dialog_data["type"] = "user"
                dialog_data["username"] = entity.username
            elif isinstance(entity, types.Chat):
                dialog_data["type"] = "group"
            elif isinstance(entity, types.Channel):
                if entity.broadcast:
                    dialog_data["type"] = "channel"
                else:
                    dialog_data["type"] = "supergroup"

            # Filter by query if provided
            if query:
                name_lower = (dialog.name or "").lower()
                query_lower = query.lower()
                if query_lower not in name_lower:
                    continue

            dialogs.append(dialog_data)

            if len(dialogs) >= limit:
                break

        return dialogs

    async def download_media(
        self,
        entity: str | int,
        message_id: int,
        save_path: str,
    ) -> dict[str, Any]:
        """Download media from a message.

        Args:
            entity: Username, phone, or chat ID
            message_id: Message ID containing media
            save_path: Path to save the file

        Returns:
            Dict with downloaded file path
        """
        await self.connect()

        # Get the message
        message = await self.client.get_messages(entity, ids=message_id)
        if not message:
            raise ValueError(f"Message {message_id} not found")

        if not message.media:
            raise ValueError(f"Message {message_id} has no media")

        # Download
        downloaded = await message.download_media(file=save_path)
        if downloaded:
            return {"path": str(Path(downloaded).resolve())}

        raise ValueError("Failed to download media")

    async def edit_message(
        self,
        entity: str | int,
        message_id: int,
        text: str,
    ) -> dict[str, Any]:
        """Edit a message.

        Args:
            entity: Username, phone, or chat ID
            message_id: Message ID to edit
            text: New text

        Returns:
            Dict with message_id
        """
        await self.connect()
        await self.client.edit_message(entity, message_id, text)
        return {"message_id": message_id}

    async def delete_messages(
        self,
        entity: str | int,
        message_ids: list[int],
    ) -> dict[str, Any]:
        """Delete messages.

        Args:
            entity: Username, phone, or chat ID
            message_ids: List of message IDs to delete

        Returns:
            Dict with deleted count
        """
        await self.connect()
        result = await self.client.delete_messages(entity, message_ids)
        return {"deleted": len(message_ids)}
