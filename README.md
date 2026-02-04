# MCP Telegram

<div align="center">
  <h3>Telegram MCP Server for Claude Code, Cursor, and AI Agents</h3>
  <p><strong>Send messages, files, voice notes via Telegram from your AI assistant</strong></p>
</div>

<div align="center">
    <a href="https://github.com/antongsm/mcp-telegram/stargazers"><img src="https://img.shields.io/github/stars/antongsm/mcp-telegram?style=social" alt="GitHub stars"></a>
    <a href="https://badge.fury.io/py/mcp-telegram"><img src="https://badge.fury.io/py/mcp-telegram.svg" alt="PyPI version"></a>
</div>

---

## Why MCP Telegram?

**Remote access to your computer via Telegram.** Ask Claude to send you files, screenshots, code snippets, or voice messages — receive them instantly in Telegram. Work from anywhere.

**Send messages as yourself.** Unlike bots, MTProto sends from YOUR personal account. Message friends, colleagues, or business contacts directly through Claude.

**Two-way communication.** Send commands to Claude via bot, receive results back. Perfect for headless servers or remote development.

---

- 📱 **Personal Account (MTProto)** — Send messages, files, voice from YOUR Telegram
- 🤖 **Bot API** — Two-way Claude ↔ You communication channel
- 📁 **File Transfer** — Send/receive documents, photos, voice messages
- 🎤 **Voice Messages** — Full voice note support (send and receive)
- 🔧 **Three Interfaces** — MCP (for AI), CLI (for humans), HTTP API (for scripts)
- 🏗️ **Daemon Architecture** — Solves SQLite session locking between AI sessions
- 🔒 **Secure** — Credentials stored locally, daemon listens only on localhost

## Use Cases

### Remote File Access
```
You: "Send me the latest build log"
Claude: *sends /var/log/build.log to your Telegram*
```

### Voice Notifications
```
You: "When tests finish, send me a voice message with results"
Claude: *runs tests, generates voice summary, sends to Telegram*
```

### Message Anyone
```
You: "Send @colleague the updated API documentation"
Claude: *sends message from YOUR account to @colleague*
```

### Two-Way Communication
```
[In Telegram] You: "Check server status"
[Bot receives] Claude: *runs diagnostics, sends report back*
```

---

## Table of Contents

- [Quick Start](#quick-start)
- [Use Cases](#use-cases)
- [Architecture](#architecture)
- [CLI Reference](#cli-reference)
- [MCP Tools](#mcp-tools)
- [Configuration](#configuration)
- [Getting Credentials](#getting-credentials)
- [Auto-Start (macOS)](#auto-start-macos)
- [Auto-Start (Linux)](#auto-start-linux)
- [Security](#security)
- [Troubleshooting](#troubleshooting)
- [Development](#development)
- [License](#license)

## Quick Start

### 1. Install

```bash
# With uv (recommended)
uv tool install mcp-telegram

# With pip
pip install mcp-telegram

# From source
git clone https://github.com/antongsm/mcp-telegram
cd mcp-telegram
uv sync
```

### 2. Setup

```bash
tg login
```

The wizard will guide you through:
1. **MTProto setup** — Get API credentials from [my.telegram.org/apps](https://my.telegram.org/apps)
2. **Bot setup (optional)** — Create a bot via [@BotFather](https://t.me/BotFather)

### 3. Start daemon

```bash
tg daemon start
```

### 4. Add to Claude Code

```bash
claude mcp add telegram -- tg mcp
```

That's it! Now Claude can send messages from your Telegram.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       Claude Code                            │
│                           ↓                                  │
│                    MCP Server (tg mcp)                       │
│                      ↓           ↓                           │
│          ┌──────────┴───┐   ┌───┴──────────┐                │
│          │   user_*     │   │    bot_*     │                │
│          │   tools      │   │    tools     │                │
│          └──────┬───────┘   └───────┬──────┘                │
│                 ↓                   ↓                        │
│          HTTP → Daemon        Direct HTTPS                   │
│                 ↓                   ↓                        │
│          Telegram MTProto    Telegram Bot API                │
│          (your account)      (@YourBot)                      │
└─────────────────────────────────────────────────────────────┘
```

**Why daemon?** Telethon uses SQLite for session storage. Without daemon, multiple Claude sessions would lock each other out. The daemon holds a single connection that all sessions share via HTTP.

## CLI Reference

### Setup & Config

```bash
tg login           # Interactive setup wizard
tg config          # Show current configuration
tg version         # Show version
tg tools           # List MCP tools
```

### Daemon (MTProto)

```bash
tg daemon start    # Start in background
tg daemon start -f # Start in foreground
tg daemon stop     # Stop daemon
tg daemon status   # Check status
tg daemon logs     # View logs
tg daemon logs -f  # Follow logs
tg daemon restart  # Restart daemon
```

### User Commands (MTProto)

Send messages **from YOUR account** to other people:

```bash
# Send text
tg user send @username "Hello!"
tg user send +79001234567 "Hi there"

# Send file
tg user send-file @username /path/to/document.pdf
tg user send-file @username photo.jpg -c "Nice photo!"

# Send voice
tg user send-voice @username voice.ogg

# Read messages
tg user messages @username
tg user messages @username -n 20
tg user messages @username --json

# Search contacts
tg user dialogs
tg user dialogs -q "John"

# Download media
tg user download @username 12345 ~/Downloads/file.jpg

# Account info
tg user whoami
```

### Bot Commands (Bot API)

Communication channel **Claude ↔ You**:

```bash
# Send to default chat
tg bot send "Hello from Claude!"
tg bot send-file /path/to/file.pdf
tg bot send-photo /path/to/image.jpg
tg bot send-voice /path/to/voice.ogg

# Read messages from users
tg bot messages
tg bot messages -n 20

# Bot info
tg bot info
```

## MCP Tools

### User Tools (MTProto)

| Tool | Description |
|------|-------------|
| `user_send_message` | Send text from your account |
| `user_send_file` | Send file/photo/voice |
| `user_get_messages` | Get chat history |
| `user_search_dialogs` | Search contacts/chats |
| `user_download_media` | Download media |
| `user_edit_message` | Edit sent message |
| `user_delete_messages` | Delete messages |
| `user_check_daemon` | Check daemon status |

### Bot Tools (Bot API)

| Tool | Description |
|------|-------------|
| `bot_send_message` | Send via bot (Claude → User) |
| `bot_send_file` | Send file via bot |
| `bot_send_photo` | Send photo via bot |
| `bot_send_voice` | Send voice via bot |
| `bot_get_messages` | Get incoming messages |
| `bot_download_file` | Download file by file_id |

## Configuration

All configuration stored in `~/.mcp-telegram/`:

```
~/.mcp-telegram/
├── config.json       # Credentials
├── session.session   # MTProto session
├── daemon.pid        # Daemon PID
├── daemon.log        # Daemon logs
└── downloads/        # Downloaded media
```

### config.json structure

```json
{
  "user": {
    "api_id": "12345678",
    "api_hash": "abcdef...",
    "phone": "+79001234567"
  },
  "bot": {
    "token": "123456:ABC-DEF...",
    "chat_id": "987654321"
  },
  "daemon": {
    "host": "127.0.0.1",
    "port": 19876
  }
}
```

## Getting Credentials

### Step 1: MTProto API (Required for user_* tools)

MTProto allows sending messages from YOUR personal Telegram account.

1. **Open** [my.telegram.org/apps](https://my.telegram.org/apps) in your browser

2. **Log in** with your phone number (international format: `+1234567890`)
   - You'll receive a code in Telegram app
   - Enter the code on the website

3. **Create application**:
   - App title: `MCP Telegram` (or any name)
   - Short name: `mcptg` (or any name)
   - Platform: `Other`
   - Description: leave empty

4. **Copy credentials**:
   - `App api_id` → this is your **API ID** (numbers only)
   - `App api_hash` → this is your **API Hash** (32 characters)

5. **Run setup wizard**:
   ```bash
   tg login
   ```
   Enter API ID, API Hash, and your phone number. A verification code will be sent to your Telegram app.

> **Note**: API credentials are tied to your account. Keep them secret. They allow full access to your Telegram.

### Step 2: Bot Token (Required for bot_* tools)

Bot API provides a two-way communication channel between you and Claude.

1. **Open Telegram** and search for [@BotFather](https://t.me/BotFather)

2. **Create a new bot**:
   ```
   /newbot
   ```

3. **Follow the prompts**:
   - Bot name: `My Claude Bot` (display name)
   - Bot username: `my_claude_bot` (must end with `bot`)

4. **Copy the token**:
   ```
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

5. **Get your Chat ID**:
   - Send any message to your new bot
   - Run:
     ```bash
     tg bot messages
     ```
   - Note the `chat_id` from the output

   Or use curl:
   ```bash
   curl "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[0].message.chat.id'
   ```

6. **Add to config**:
   ```bash
   tg login  # Will prompt for bot token and chat_id
   ```

### Step 3: First Login

After getting credentials, run the setup wizard:

```bash
tg login
```

The wizard will:
1. Ask for API ID, API Hash, Phone (for MTProto)
2. Send a verification code to your Telegram app
3. Ask for Bot Token and Chat ID (optional, for Bot API)
4. Save everything to `~/.mcp-telegram/config.json`

### Step 4: Verify Setup

```bash
# Check MTProto connection
tg daemon start
tg user whoami
# Should show: Anton (@MT_nes) or your account

# Check Bot connection
tg bot info
# Should show your bot's name and username

# Test sending
tg user send me "Test from MTProto"
tg bot send "Test from Bot API"
```

## Auto-Start (macOS)

Create `~/Library/LaunchAgents/com.mcp.telegram.daemon.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.mcp.telegram.daemon</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/tg</string>
        <string>daemon</string>
        <string>start</string>
        <string>--foreground</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/YOU/.mcp-telegram/daemon.stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOU/.mcp-telegram/daemon.stderr.log</string>
</dict>
</plist>
```

Load it:
```bash
launchctl load ~/Library/LaunchAgents/com.mcp.telegram.daemon.plist
```

## Auto-Start (Linux)

### systemd (Ubuntu, Debian, Fedora, CentOS, Arch)

Create `/etc/systemd/system/mcp-telegram.service`:

```ini
[Unit]
Description=MCP Telegram Daemon
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/home/YOUR_USERNAME
Environment="PATH=/home/YOUR_USERNAME/.local/bin:/usr/local/bin:/usr/bin"
ExecStart=/home/YOUR_USERNAME/.local/bin/tg daemon start --foreground
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
# Replace YOUR_USERNAME with your actual username
sudo systemctl daemon-reload
sudo systemctl enable mcp-telegram
sudo systemctl start mcp-telegram

# Check status
sudo systemctl status mcp-telegram

# View logs
sudo journalctl -u mcp-telegram -f
```

### User-level systemd (no sudo required)

Create `~/.config/systemd/user/mcp-telegram.service`:

```ini
[Unit]
Description=MCP Telegram Daemon
After=network.target

[Service]
Type=simple
ExecStart=%h/.local/bin/tg daemon start --foreground
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
```

Enable and start:
```bash
systemctl --user daemon-reload
systemctl --user enable mcp-telegram
systemctl --user start mcp-telegram

# Enable lingering (keeps service running after logout)
loginctl enable-linger $USER

# Check status
systemctl --user status mcp-telegram
```

### Docker (any Linux)

```dockerfile
FROM python:3.12-slim

RUN pip install mcp-telegram

COPY config.json /root/.mcp-telegram/config.json
COPY session.session /root/.mcp-telegram/session.session

EXPOSE 19876

CMD ["tg", "daemon", "start", "--foreground"]
```

```bash
docker build -t mcp-telegram .
docker run -d --name mcp-telegram -p 127.0.0.1:19876:19876 mcp-telegram
```

> **Note**: For Docker, you need to copy `session.session` from a machine where you've already logged in, since the login process requires interactive input.

### Supervisor (legacy systems)

Create `/etc/supervisor/conf.d/mcp-telegram.conf`:

```ini
[program:mcp-telegram]
command=/home/YOUR_USERNAME/.local/bin/tg daemon start --foreground
directory=/home/YOUR_USERNAME
user=YOUR_USERNAME
autostart=true
autorestart=true
stderr_logfile=/var/log/mcp-telegram.err.log
stdout_logfile=/var/log/mcp-telegram.out.log
```

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start mcp-telegram
```

## Security

This project is designed with security in mind:

- **Local credentials only** — API keys stored in `~/.mcp-telegram/config.json`, never transmitted except to Telegram
- **Localhost daemon** — HTTP server binds to `127.0.0.1` only, inaccessible from network
- **No data collection** — No analytics, no telemetry, no external services
- **Read-only by default** — Delete operations require explicit message IDs
- **Open source** — Full code audit available

### What the code does NOT do:
- Does not delete your account or contacts
- Does not send spam or bulk messages
- Does not expose credentials to third parties
- Does not have hidden backdoors
- Does not access chats without explicit commands

## Troubleshooting

### Daemon not starting

```bash
# Check logs
tg daemon logs

# Check if port is in use
lsof -i :19876

# Kill stale processes
pkill -f "mcp_telegram.daemon"
```

### Session expired

```bash
# Re-login
tg login
```

### Database locked (SQLite error)

This shouldn't happen with daemon architecture. If it does:

```bash
# Stop all processes
tg daemon stop
pkill -f "mcp_telegram"

# Restart
tg daemon start
```

## Development

```bash
# Clone
git clone https://github.com/antongsm/mcp-telegram
cd mcp-telegram

# Install with dev deps
uv sync --dev

# Run tests
uv run pytest

# Lint
uv run ruff check .
uv run ruff format .

# Type check
uv run pyright
```

## License

MIT

## Keywords

`mcp` `telegram` `claude` `claude-code` `cursor` `ai-agent` `mtproto` `bot-api` `telethon` `model-context-protocol` `llm` `ai-assistant` `file-transfer` `voice-messages` `remote-access` `automation`

## Credits

- Original MTProto implementation by [Yeabsira Driba](https://github.com/dryeab)
- Unified daemon architecture by [Anton Nozdrin](https://github.com/antongsm)
- Built with [Telethon](https://github.com/LonamiWebs/Telethon) and [MCP](https://modelcontextprotocol.io/)

---

<div align="center">
  <p>Made with Claude Code by <a href="https://github.com/dryeab">Yeabsira Driba</a> & <a href="https://github.com/antongsm">Anton Nozdrin</a></p>
</div>
