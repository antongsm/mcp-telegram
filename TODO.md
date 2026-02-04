# MCP Telegram - Roadmap

## Project Goal

Full-featured Claude Code integration with Telegram for two-way communication:

1. **Two-way file exchange** — send and receive any files via Telegram
2. **Voice messages** — send and receive voice messages for voice interaction
3. **Text messaging** — full chat with Claude via Telegram

---

## Status: COMPLETE ✅

Unified MCP server `mcp-telegram` with MTProto + Bot API is implemented.

---

## Completed

### Research (Phase 1)
- [x] Research existing MCP servers for Telegram
- [x] Test dryeab/mcp-telegram (MTProto) — works but writes to Saved Messages
- [x] Analyze alternatives: guangxiangdebizi, harnyk, mcp-communicator — no voice support
- [x] Decision: combine MTProto + Bot API into one server

### Implementation (Phase 2)
- [x] Create unified project `~/Tools/mcp-telegram`
- [x] Daemon architecture for MTProto (solves SQLite locking)
- [x] Bot API for two-way Claude ↔ User communication
- [x] Full CLI with typer
- [x] 14 MCP tools (8 user_*, 6 bot_*)
- [x] Voice messages working
- [x] Auto-start for macOS and Linux

---

## Implemented Tools

### user_* (MTProto — Personal Account)

| Tool | Description | Status |
|------|-------------|--------|
| `user_send_message` | Send text from user's account | ✅ |
| `user_send_file` | Send files/photos/voice | ✅ |
| `user_get_messages` | Get chat history | ✅ |
| `user_search_dialogs` | Search contacts/chats | ✅ |
| `user_download_media` | Download media | ✅ |
| `user_edit_message` | Edit messages | ✅ |
| `user_delete_messages` | Delete messages | ✅ |
| `user_check_daemon` | Check daemon status | ✅ |

### bot_* (Bot API — Bot)

| Tool | Description | Status |
|------|-------------|--------|
| `bot_send_message` | Send via bot (Claude → User) | ✅ |
| `bot_send_file` | Send files via bot | ✅ |
| `bot_send_photo` | Send photos via bot | ✅ |
| `bot_send_voice` | Send voice via bot | ✅ |
| `bot_get_messages` | Get incoming messages | ✅ |
| `bot_download_file` | Download by file_id | ✅ |

---

## Architecture

```
MCP Server (tg mcp)
├── user_* tools → HTTP → Daemon (:19876) → Telegram MTProto (your account)
└── bot_* tools  → HTTPS → api.telegram.org → Telegram Bot (@YourBot)
```

- **MTProto** — send from personal account to other people
- **Bot API** — two-way Claude ↔ User channel
- **Daemon** — solves SQLite session locking problem

---

## Configuration

```
~/.mcp-telegram/
├── config.json       # Credentials
├── session.session   # MTProto session
├── daemon.pid        # Daemon PID
├── daemon.log        # Daemon logs
└── downloads/        # Downloaded files
```

---

## CLI Commands

```bash
# Setup
tg login

# Daemon
tg daemon start|stop|status|logs|restart

# MTProto (user_*)
tg user send @username "text"
tg user send-file @username /path/to/file
tg user send-voice @username /path/to/voice.ogg
tg user messages @username
tg user dialogs
tg user whoami

# Bot API (bot_*)
tg bot send "text"
tg bot send-file /path/to/file
tg bot send-voice /path/to/voice.ogg
tg bot messages
tg bot info
```

---

## Usage in Claude Code

```bash
# Send message from your account
> Send @username a message "Hello!"

# Send file
> Send file /path/to/document.pdf to @username

# Send me a notification
> Send me a Telegram message "Done!"

# Check messages
> Check new Telegram messages
```

---

## Future Improvements

- [ ] Add `send_video` — video sending
- [ ] Add inline buttons
- [ ] Add group chat support
- [ ] Auto-create bot via MTProto

---

## Links

- GitHub: https://github.com/antongsm/mcp-telegram
- Telegram Bot API: https://core.telegram.org/bots/api
- Telethon: https://docs.telethon.dev/
- MCP SDK: https://github.com/modelcontextprotocol/python-sdk

---

*Last updated: 2026-02-04*
