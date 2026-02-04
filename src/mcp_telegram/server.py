"""MCP Telegram Server - Unified MTProto + Bot API.

Provides MCP tools for:
- user_* — MTProto (send from personal account via daemon)
- bot_* — Bot API (communication channel)

Usage:
    tg mcp  # Start MCP server
"""

import asyncio
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from mcp_telegram.config import load_config
from mcp_telegram.bot.client import BotClient

# =============================================================================
# Server Setup
# =============================================================================

server = Server("mcp-telegram")


def get_daemon_url() -> str:
    """Get daemon URL from config."""
    config = load_config()
    return config.daemon.url


async def daemon_request(
    endpoint: str,
    data: dict | None = None,
    timeout: float = 60.0,
) -> dict:
    """Make request to MTProto daemon."""
    url = f"{get_daemon_url()}/{endpoint}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        if data:
            response = await client.post(url, json=data)
        else:
            response = await client.get(url)
        return response.json()


async def check_daemon() -> tuple[bool, str]:
    """Check if daemon is running."""
    try:
        result = await daemon_request("health")
        if result.get("ok"):
            user = result.get("user", {})
            return True, f"Connected as {user.get('first_name')} (@{user.get('username')})"
        return False, result.get("error", "Unknown error")
    except Exception as e:
        return False, f"Daemon not running: {e}"


# =============================================================================
# Tool Definitions
# =============================================================================


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available tools."""
    return [
        # =====================================================================
        # User Tools (MTProto via daemon)
        # =====================================================================
        Tool(
            name="user_send_message",
            description="Send a text message from YOUR Telegram account to any user, group, or channel.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Recipient: @username, +phone, chat ID, or 'me' for Saved Messages"
                    },
                    "message": {
                        "type": "string",
                        "description": "Message text (supports Markdown)"
                    },
                    "reply_to": {
                        "type": "integer",
                        "description": "Optional: message ID to reply to"
                    }
                },
                "required": ["entity", "message"]
            }
        ),
        Tool(
            name="user_send_file",
            description="Send a file from YOUR Telegram account. Can send documents, photos, or voice messages.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Recipient: @username, +phone, or chat ID"
                    },
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to file"
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption"
                    },
                    "voice": {
                        "type": "boolean",
                        "description": "Send as voice message (for audio files)"
                    }
                },
                "required": ["entity", "file_path"]
            }
        ),
        Tool(
            name="user_get_messages",
            description="Get message history from any chat in YOUR Telegram account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Chat: @username, +phone, or chat ID"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages (default: 10)"
                    }
                },
                "required": ["entity"]
            }
        ),
        Tool(
            name="user_search_dialogs",
            description="Search contacts and chats in YOUR Telegram account.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (name or username)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of results (default: 10)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="user_download_media",
            description="Download media (photo, document, voice) from a message.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Chat: @username, +phone, or chat ID"
                    },
                    "message_id": {
                        "type": "integer",
                        "description": "Message ID containing media"
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Absolute path to save file"
                    }
                },
                "required": ["entity", "message_id", "save_path"]
            }
        ),
        Tool(
            name="user_edit_message",
            description="Edit a message you sent.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Chat: @username, +phone, or chat ID"
                    },
                    "message_id": {
                        "type": "integer",
                        "description": "Message ID to edit"
                    },
                    "text": {
                        "type": "string",
                        "description": "New message text"
                    }
                },
                "required": ["entity", "message_id", "text"]
            }
        ),
        Tool(
            name="user_delete_messages",
            description="Delete messages from a chat.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "description": "Chat: @username, +phone, or chat ID"
                    },
                    "message_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "List of message IDs to delete"
                    }
                },
                "required": ["entity", "message_ids"]
            }
        ),
        Tool(
            name="user_check_daemon",
            description="Check if the MTProto daemon is running and connected.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),

        # =====================================================================
        # Bot Tools (Bot API direct)
        # =====================================================================
        Tool(
            name="bot_send_message",
            description="Send a message via Telegram bot to the configured chat (Claude -> User communication).",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Message text (supports Markdown)"
                    },
                    "chat_id": {
                        "type": "string",
                        "description": "Optional: override default chat ID"
                    }
                },
                "required": ["text"]
            }
        ),
        Tool(
            name="bot_send_file",
            description="Send a file via Telegram bot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to file"
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption"
                    },
                    "chat_id": {
                        "type": "string",
                        "description": "Optional: override default chat ID"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="bot_send_photo",
            description="Send a photo via Telegram bot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to image"
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption"
                    },
                    "chat_id": {
                        "type": "string",
                        "description": "Optional: override default chat ID"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="bot_send_voice",
            description="Send a voice message via Telegram bot.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Absolute path to audio file (.ogg with OPUS preferred)"
                    },
                    "caption": {
                        "type": "string",
                        "description": "Optional caption"
                    },
                    "chat_id": {
                        "type": "string",
                        "description": "Optional: override default chat ID"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="bot_get_messages",
            description="Get messages received by the bot (User -> Claude communication).",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages (default: 10)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="bot_download_file",
            description="Download a file sent to the bot by file_id.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "string",
                        "description": "Telegram file_id from a message"
                    },
                    "save_path": {
                        "type": "string",
                        "description": "Absolute path to save the file"
                    }
                },
                "required": ["file_id", "save_path"]
            }
        ),
    ]


# =============================================================================
# Tool Handlers
# =============================================================================


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    # =========================================================================
    # User Tools (MTProto via daemon)
    # =========================================================================

    if name == "user_check_daemon":
        ok, msg = await check_daemon()
        return [TextContent(type="text", text=msg)]

    if name.startswith("user_"):
        # Check daemon first
        ok, msg = await check_daemon()
        if not ok:
            return [TextContent(type="text", text=f"Error: {msg}\n\nStart daemon with: tg daemon start")]

        if name == "user_send_message":
            result = await daemon_request("send_message", {
                "entity": arguments["entity"],
                "message": arguments["message"],
                "reply_to": arguments.get("reply_to"),
            })
            if result.get("ok"):
                return [TextContent(type="text", text=f"Message sent (ID: {result.get('message_id')})")]
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]

        if name == "user_send_file":
            result = await daemon_request("send_file", {
                "entity": arguments["entity"],
                "file_path": arguments["file_path"],
                "caption": arguments.get("caption", ""),
                "voice": arguments.get("voice", False),
            })
            if result.get("ok"):
                return [TextContent(type="text", text=f"File sent (ID: {result.get('message_id')})")]
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]

        if name == "user_get_messages":
            result = await daemon_request("get_messages", {
                "entity": arguments["entity"],
                "limit": arguments.get("limit", 10),
            })
            if result.get("ok"):
                messages = result.get("messages", [])
                if not messages:
                    return [TextContent(type="text", text="No messages found")]

                lines = []
                for msg in messages:
                    date = msg.get("date", "")[:10]
                    msg_id = msg.get("id")
                    text = msg.get("text", "")[:200]
                    media = f" [{msg.get('media_type')}]" if msg.get("has_media") else ""
                    lines.append(f"[{date}] #{msg_id}{media}: {text}")

                return [TextContent(type="text", text="\n".join(lines))]
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]

        if name == "user_search_dialogs":
            result = await daemon_request("search_dialogs", {
                "query": arguments.get("query", ""),
                "limit": arguments.get("limit", 10),
            })
            if result.get("ok"):
                dialogs = result.get("dialogs", [])
                if not dialogs:
                    return [TextContent(type="text", text="No dialogs found")]

                lines = []
                for d in dialogs:
                    dtype = d.get("type", "")
                    name = d.get("name", "")
                    username = f"@{d.get('username')}" if d.get("username") else ""
                    lines.append(f"[{dtype}] {name} {username}")

                return [TextContent(type="text", text="\n".join(lines))]
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]

        if name == "user_download_media":
            result = await daemon_request("download_media", {
                "entity": arguments["entity"],
                "message_id": arguments["message_id"],
                "save_path": arguments["save_path"],
            }, timeout=120.0)
            if result.get("ok"):
                return [TextContent(type="text", text=f"Downloaded to: {result.get('path')}")]
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]

        if name == "user_edit_message":
            result = await daemon_request("edit_message", {
                "entity": arguments["entity"],
                "message_id": arguments["message_id"],
                "text": arguments["text"],
            })
            if result.get("ok"):
                return [TextContent(type="text", text=f"Message edited")]
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]

        if name == "user_delete_messages":
            result = await daemon_request("delete_messages", {
                "entity": arguments["entity"],
                "message_ids": arguments["message_ids"],
            })
            if result.get("ok"):
                return [TextContent(type="text", text=f"Messages deleted")]
            return [TextContent(type="text", text=f"Error: {result.get('error')}")]

    # =========================================================================
    # Bot Tools (Bot API direct)
    # =========================================================================

    if name.startswith("bot_"):
        config = load_config()
        if not config.has_bot:
            return [TextContent(type="text", text="Error: Bot not configured. Run: tg login")]

        bot = BotClient(config)

        try:
            if name == "bot_send_message":
                result = await bot.send_message(
                    arguments["text"],
                    arguments.get("chat_id"),
                )
                return [TextContent(type="text", text=f"Message sent (ID: {result.get('message_id')})")]

            if name == "bot_send_file":
                result = await bot.send_document(
                    arguments["file_path"],
                    arguments.get("caption", ""),
                    arguments.get("chat_id"),
                )
                return [TextContent(type="text", text="File sent")]

            if name == "bot_send_photo":
                result = await bot.send_photo(
                    arguments["file_path"],
                    arguments.get("caption", ""),
                    arguments.get("chat_id"),
                )
                return [TextContent(type="text", text="Photo sent")]

            if name == "bot_send_voice":
                result = await bot.send_voice(
                    arguments["file_path"],
                    arguments.get("caption", ""),
                    arguments.get("chat_id"),
                )
                return [TextContent(type="text", text="Voice message sent")]

            if name == "bot_get_messages":
                messages = await bot.get_messages(arguments.get("limit", 10))
                if not messages:
                    return [TextContent(type="text", text="No messages")]

                lines = []
                for msg in messages:
                    from_user = msg.get("from", {})
                    text = msg.get("text", "")[:200]
                    lines.append(f"{from_user.get('first_name', 'Unknown')}: {text}")

                return [TextContent(type="text", text="\n".join(lines))]

            if name == "bot_download_file":
                result = await bot.download_file(
                    arguments["file_id"],
                    arguments["save_path"],
                )
                return [TextContent(type="text", text=f"Downloaded to: {result.get('path')}")]

        except Exception as e:
            return [TextContent(type="text", text=f"Error: {e}")]

    return [TextContent(type="text", text=f"Unknown tool: {name}")]


# =============================================================================
# Entry Point
# =============================================================================


def run_server() -> None:
    """Run the MCP server."""
    async def main():
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(main())


if __name__ == "__main__":
    run_server()
