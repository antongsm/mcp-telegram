# MCP Telegram

Unified Telegram MCP server — MTProto + Bot API.

## Architecture

```
MCP Server (tg mcp)
├── user_* tools → HTTP → Daemon (:19876) → Telegram MTProto
└── bot_* tools  → HTTPS → api.telegram.org → Telegram Bot
```

## When to Use Which Tool

### user_* — MTProto (Personal Account)

**Use for sending messages from the user's account to other people:**

| Tool | Description |
|------|-------------|
| `user_send_message` | Send text from user's account |
| `user_send_file` | Send file/photo/voice |
| `user_get_messages` | Get chat history |
| `user_search_dialogs` | Search contacts/chats |
| `user_download_media` | Download media from message |
| `user_edit_message` | Edit a message |
| `user_delete_messages` | Delete messages |
| `user_check_daemon` | Check daemon status |

Examples:
```
Send @username a message "Hello!"
Send file /path/to/doc.pdf to @username
Find contact John
```

### bot_* — Bot API (Bot)

**Use for Claude ↔ User communication:**

| Tool | Description |
|------|-------------|
| `bot_send_message` | Send message via bot |
| `bot_send_file` | Send file via bot |
| `bot_send_photo` | Send photo via bot |
| `bot_send_voice` | Send voice message via bot |
| `bot_get_messages` | Get incoming messages |
| `bot_download_file` | Download file by file_id |

Examples:
```
Send me a Telegram message "Done!"
Check if there are new messages from the user
```

## Important

1. **Daemon must be running** for user_* tools:
   ```bash
   tg daemon start
   ```

2. **Configuration** is stored in `~/.mcp-telegram/config.json`

3. On `Daemon not running` error — start daemon or check status:
   ```bash
   tg daemon status
   ```

## CLI Commands

```bash
tg login           # Setup wizard
tg daemon start    # Start daemon
tg daemon status   # Check status
tg user send @user "text"  # Send from user account
tg bot send "text"         # Send via bot
```
