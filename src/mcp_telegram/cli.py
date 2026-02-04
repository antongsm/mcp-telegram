"""MCP Telegram CLI - Unified command-line interface.

Three interfaces for Telegram:
1. MCP (for AI) - `tg mcp`
2. CLI (for humans) - `tg user send`, `tg bot send`
3. HTTP API (for integrations) - daemon on :19876

Usage:
    tg login              # Interactive setup wizard
    tg daemon start       # Start MTProto daemon
    tg user send @user "text"
    tg bot send "text"
"""

import asyncio
import importlib.metadata
import json
import os
import signal
import subprocess
import sys
import time
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Coroutine

import httpx
import typer
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mcp_telegram.config import (
    Config,
    get_config_dir,
    get_log_path,
    get_pid_path,
    get_session_path,
    load_config,
)

# =============================================================================
# App Setup
# =============================================================================

app = typer.Typer(
    name="tg",
    help="MCP Telegram - Unified Telegram integration for AI and CLI.",
    add_completion=False,
    no_args_is_help=True,
)

# Sub-apps
daemon_app = typer.Typer(help="Manage the MTProto daemon.")
user_app = typer.Typer(help="User account commands (MTProto).")
bot_app = typer.Typer(help="Bot commands (Bot API).")

app.add_typer(daemon_app, name="daemon")
app.add_typer(user_app, name="user")
app.add_typer(bot_app, name="bot")

console = Console()


def async_command(func: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Decorator to run async functions in typer commands."""
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(func(*args, **kwargs))
    return wrapper


# =============================================================================
# Daemon Helpers
# =============================================================================


def daemon_request(
    endpoint: str,
    data: dict | None = None,
    method: str = "POST",
    timeout: float = 30.0,
) -> dict:
    """Make a request to the daemon."""
    config = load_config()
    url = f"{config.daemon.url}/{endpoint}"

    try:
        if method == "GET":
            response = httpx.get(url, timeout=timeout)
        else:
            response = httpx.post(url, json=data or {}, timeout=timeout)
        return response.json()
    except httpx.ConnectError:
        return {"ok": False, "error": "Daemon not running. Start with: tg daemon start"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def is_daemon_running() -> bool:
    """Check if daemon is running."""
    result = daemon_request("health", method="GET", timeout=5.0)
    return result.get("ok", False)


# =============================================================================
# Root Commands
# =============================================================================


@app.command()
def version() -> None:
    """Show version."""
    try:
        ver = importlib.metadata.version("mcp-telegram")
    except importlib.metadata.PackageNotFoundError:
        ver = "development"

    console.print(f"MCP Telegram v{ver}")


@app.command()
def login() -> None:
    """Interactive setup wizard for MTProto and Bot."""
    console.print(Panel.fit(
        "[bold blue]MCP Telegram Setup Wizard[/bold blue]\n\n"
        "This wizard will configure:\n"
        "1. MTProto - Send messages from YOUR account\n"
        "2. Bot API - Claude <-> You communication (optional)",
        title="🚀 Setup",
        border_style="blue",
    ))

    config = load_config()

    # =========================
    # MTProto Setup
    # =========================
    console.print("\n[bold cyan]═══ MTProto Setup ═══[/bold cyan]")
    console.print("[dim]Credentials from https://my.telegram.org/apps[/dim]\n")

    # API ID
    default_id = config.user.api_id or ""
    api_id = console.input(
        f"[cyan]API ID[/cyan]{f' [{default_id}]' if default_id else ''}: "
    ).strip() or default_id
    config.user.api_id = api_id

    # API Hash
    default_hash = config.user.api_hash or ""
    masked = f"{default_hash[:8]}..." if default_hash else ""
    api_hash = console.input(
        f"[cyan]API Hash[/cyan]{f' [{masked}]' if masked else ''}: "
    ).strip() or default_hash
    config.user.api_hash = api_hash

    # Phone
    default_phone = config.user.phone or ""
    phone = console.input(
        f"[cyan]Phone[/cyan]{f' [{default_phone}]' if default_phone else ''}: "
    ).strip() or default_phone
    config.user.phone = phone

    # Save config
    config.save()
    console.print("[green]✓ Config saved[/green]")

    # Authorize
    if api_id and api_hash and phone:
        console.print("\n[yellow]Connecting to Telegram...[/yellow]")

        from mcp_telegram.daemon import do_login
        asyncio.run(do_login())

    # =========================
    # Bot Setup (Optional)
    # =========================
    console.print("\n[bold cyan]═══ Bot Setup (Optional) ═══[/bold cyan]")
    console.print("[dim]Create a bot at @BotFather[/dim]\n")

    setup_bot = console.input("[cyan]Configure bot?[/cyan] [Y/n]: ").strip().lower()

    if setup_bot != "n":
        # Token
        default_token = config.bot.token or ""
        masked_token = f"{default_token[:10]}..." if default_token else ""
        token = console.input(
            f"[cyan]Bot Token[/cyan]{f' [{masked_token}]' if masked_token else ''}: "
        ).strip() or default_token
        config.bot.token = token

        # Chat ID
        default_chat = config.bot.chat_id or ""
        chat_id = console.input(
            f"[cyan]Chat ID[/cyan]{f' [{default_chat}]' if default_chat else ''}: "
        ).strip() or default_chat
        config.bot.chat_id = chat_id

        config.save()
        console.print("[green]✓ Bot config saved[/green]")

        # Test bot
        if token:
            console.print("[yellow]Testing bot...[/yellow]")
            try:
                response = httpx.get(
                    f"https://api.telegram.org/bot{token}/getMe",
                    timeout=10.0,
                )
                data = response.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    console.print(f"[green]✓ Bot: @{bot_info.get('username')}[/green]")
                else:
                    console.print(f"[red]✗ Bot error: {data.get('description')}[/red]")
            except Exception as e:
                console.print(f"[red]✗ Failed to test bot: {e}[/red]")

    # =========================
    # Summary
    # =========================
    console.print(Panel.fit(
        f"[bold green]Setup Complete![/bold green]\n\n"
        f"Config: {get_config_dir()}/config.json\n"
        f"Session: {get_session_path()}\n\n"
        f"[bold]Next steps:[/bold]\n"
        f"1. Start daemon: [cyan]tg daemon start[/cyan]\n"
        f"2. Send message: [cyan]tg user send @username 'Hello!'[/cyan]",
        title="✅ Done",
        border_style="green",
    ))


@app.command()
def config() -> None:
    """Show current configuration."""
    cfg = load_config()

    console.print(Panel.fit(
        f"[bold]MTProto:[/bold]\n"
        f"  API ID: {cfg.user.api_id or '[not set]'}\n"
        f"  API Hash: {cfg.user.api_hash[:8] + '...' if cfg.user.api_hash else '[not set]'}\n"
        f"  Phone: {cfg.user.phone or '[not set]'}\n"
        f"  Configured: {'✓' if cfg.has_user else '✗'}\n\n"
        f"[bold]Bot:[/bold]\n"
        f"  Token: {cfg.bot.token[:10] + '...' if cfg.bot.token else '[not set]'}\n"
        f"  Chat ID: {cfg.bot.chat_id or '[not set]'}\n"
        f"  Configured: {'✓' if cfg.has_bot else '✗'}\n\n"
        f"[bold]Daemon:[/bold]\n"
        f"  URL: {cfg.daemon.url}\n"
        f"  Running: {'✓' if is_daemon_running() else '✗'}",
        title="📋 Configuration",
        border_style="blue",
    ))


@app.command()
def mcp() -> None:
    """Start MCP server (for Claude Code)."""
    from mcp_telegram.server import run_server
    run_server()


@app.command()
def tools() -> None:
    """List available MCP tools."""
    console.print(Panel.fit(
        "[bold]User Tools (MTProto):[/bold]\n"
        "  user_send_message    Send text from your account\n"
        "  user_send_file       Send file/photo\n"
        "  user_send_voice      Send voice message\n"
        "  user_get_messages    Get chat history\n"
        "  user_search_dialogs  Search contacts/chats\n"
        "  user_download_media  Download media\n"
        "  user_edit_message    Edit sent message\n"
        "  user_delete_message  Delete messages\n"
        "  user_check_daemon    Check daemon status\n\n"
        "[bold]Bot Tools (Bot API):[/bold]\n"
        "  bot_send_message     Send via bot\n"
        "  bot_send_file        Send file via bot\n"
        "  bot_send_voice       Send voice via bot\n"
        "  bot_send_photo       Send photo via bot\n"
        "  bot_get_messages     Get incoming messages\n"
        "  bot_download_file    Download file",
        title="🔧 MCP Tools",
        border_style="blue",
    ))


# =============================================================================
# Daemon Commands
# =============================================================================


@daemon_app.command("start")
def daemon_start(
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
) -> None:
    """Start the MTProto daemon."""
    if is_daemon_running():
        console.print("[green]✓ Daemon is already running[/green]")
        return

    config = load_config()
    if not config.has_user:
        console.print("[red]✗ User not configured. Run: tg login[/red]")
        raise typer.Exit(1)

    # Find Python and daemon module
    python = sys.executable
    daemon_module = "mcp_telegram.daemon"

    if foreground:
        os.execv(python, [python, "-m", daemon_module, "start"])
    else:
        # Start in background
        log_dir = get_config_dir()
        stdout_log = log_dir / "daemon.stdout.log"
        stderr_log = log_dir / "daemon.stderr.log"

        subprocess.Popen(
            [python, "-m", daemon_module, "start"],
            stdout=open(stdout_log, "a"),
            stderr=open(stderr_log, "a"),
            start_new_session=True,
        )

        # Wait for daemon to start
        console.print("[yellow]Starting daemon...[/yellow]")
        for _ in range(20):
            time.sleep(0.5)
            if is_daemon_running():
                result = daemon_request("health", method="GET")
                user = result.get("user", {})
                console.print(
                    f"[green]✓ Daemon started. "
                    f"Connected as {user.get('first_name')} (@{user.get('username')})[/green]"
                )
                return

        console.print("[red]✗ Daemon failed to start. Check logs: tg daemon logs[/red]")
        raise typer.Exit(1)


@daemon_app.command("stop")
def daemon_stop() -> None:
    """Stop the daemon."""
    pid_path = get_pid_path()

    if not pid_path.exists():
        console.print("[yellow]Daemon not running[/yellow]")
        return

    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]✓ Sent SIGTERM to PID {pid}[/green]")

        # Wait for shutdown
        for _ in range(10):
            time.sleep(0.5)
            try:
                os.kill(pid, 0)
            except OSError:
                console.print("[green]✓ Daemon stopped[/green]")
                return

        console.print("[yellow]Daemon may still be shutting down[/yellow]")
    except (OSError, ValueError) as e:
        console.print(f"[red]✗ Failed to stop: {e}[/red]")
        pid_path.unlink(missing_ok=True)


@daemon_app.command("status")
def daemon_status() -> None:
    """Check daemon status."""
    pid_path = get_pid_path()

    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            console.print(f"[green]✓ Daemon running (PID {pid})[/green]")
        except (OSError, ValueError):
            console.print("[yellow]Daemon not running (stale PID file)[/yellow]")
            return
    else:
        console.print("[yellow]Daemon not running[/yellow]")
        return

    # Health check
    result = daemon_request("health", method="GET", timeout=5.0)
    if result.get("ok"):
        user = result.get("user", {})
        console.print(f"Connected as {user.get('first_name')} (@{user.get('username')})")
    else:
        console.print(f"[red]Health check failed: {result.get('error')}[/red]")


@daemon_app.command("logs")
def daemon_logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of lines"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Follow log output"),
) -> None:
    """View daemon logs."""
    log_file = get_log_path()

    if not log_file.exists():
        console.print("[yellow]No log file found[/yellow]")
        return

    if follow:
        subprocess.run(["tail", "-f", str(log_file)])
    else:
        subprocess.run(["tail", f"-{lines}", str(log_file)])


@daemon_app.command("restart")
def daemon_restart() -> None:
    """Restart the daemon."""
    daemon_stop()
    time.sleep(1)
    daemon_start(foreground=False)


# =============================================================================
# User Commands (MTProto)
# =============================================================================


@user_app.command("send")
def user_send(
    entity: str = typer.Argument(..., help="@username, +phone, or chat ID"),
    message: str = typer.Argument(..., help="Message text"),
    reply_to: int = typer.Option(None, "--reply-to", "-r", help="Message ID to reply to"),
) -> None:
    """Send a text message from your account."""
    result = daemon_request("send_message", {
        "entity": entity,
        "message": message,
        "reply_to": reply_to,
    })

    if result.get("ok"):
        console.print(f"[green]✓ Sent (ID: {result.get('message_id')})[/green]")
    else:
        console.print(f"[red]✗ {result.get('error')}[/red]")
        raise typer.Exit(1)


@user_app.command("send-file")
def user_send_file(
    entity: str = typer.Argument(..., help="@username, +phone, or chat ID"),
    file_path: str = typer.Argument(..., help="Path to file"),
    caption: str = typer.Option("", "--caption", "-c", help="Caption"),
    voice: bool = typer.Option(False, "--voice", "-v", help="Send as voice message"),
) -> None:
    """Send a file from your account."""
    if not Path(file_path).exists():
        console.print(f"[red]✗ File not found: {file_path}[/red]")
        raise typer.Exit(1)

    result = daemon_request("send_file", {
        "entity": entity,
        "file_path": str(Path(file_path).resolve()),
        "caption": caption,
        "voice": voice,
    })

    if result.get("ok"):
        console.print(f"[green]✓ Sent (ID: {result.get('message_id')})[/green]")
    else:
        console.print(f"[red]✗ {result.get('error')}[/red]")
        raise typer.Exit(1)


@user_app.command("send-voice")
def user_send_voice(
    entity: str = typer.Argument(..., help="@username, +phone, or chat ID"),
    file_path: str = typer.Argument(..., help="Path to audio file"),
    caption: str = typer.Option("", "--caption", "-c", help="Caption"),
) -> None:
    """Send a voice message from your account."""
    user_send_file(entity, file_path, caption, voice=True)


@user_app.command("messages")
def user_messages(
    entity: str = typer.Argument(..., help="@username, +phone, or chat ID"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of messages"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get messages from a chat."""
    result = daemon_request("get_messages", {
        "entity": entity,
        "limit": limit,
    })

    if not result.get("ok"):
        console.print(f"[red]✗ {result.get('error')}[/red]")
        raise typer.Exit(1)

    messages = result.get("messages", [])

    if as_json:
        print(json.dumps(messages, indent=2, ensure_ascii=False))
        return

    if not messages:
        console.print("[yellow]No messages[/yellow]")
        return

    for msg in reversed(messages):  # Show oldest first
        date = msg.get("date", "")[:10]
        msg_id = msg.get("id")
        text = msg.get("text", "")[:100]
        media = f" [{msg.get('media_type')}]" if msg.get("has_media") else ""

        console.print(f"[dim]{date}[/dim] [cyan]#{msg_id}[/cyan]{media}: {text}")


@user_app.command("dialogs")
def user_dialogs(
    query: str = typer.Option("", "--query", "-q", help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of results"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List or search dialogs."""
    result = daemon_request("search_dialogs", {
        "query": query,
        "limit": limit,
    })

    if not result.get("ok"):
        console.print(f"[red]✗ {result.get('error')}[/red]")
        raise typer.Exit(1)

    dialogs = result.get("dialogs", [])

    if as_json:
        print(json.dumps(dialogs, indent=2, ensure_ascii=False))
        return

    if not dialogs:
        console.print("[yellow]No dialogs found[/yellow]")
        return

    table = Table(box=ROUNDED, show_header=True)
    table.add_column("Type", style="dim")
    table.add_column("Name")
    table.add_column("Username")
    table.add_column("Unread", justify="right")

    for d in dialogs:
        table.add_row(
            d.get("type", ""),
            d.get("name", ""),
            f"@{d.get('username')}" if d.get("username") else "",
            str(d.get("unread_count", 0)),
        )

    console.print(table)


@user_app.command("download")
def user_download(
    entity: str = typer.Argument(..., help="@username, +phone, or chat ID"),
    message_id: int = typer.Argument(..., help="Message ID"),
    save_path: str = typer.Argument(..., help="Path to save file"),
) -> None:
    """Download media from a message."""
    result = daemon_request("download_media", {
        "entity": entity,
        "message_id": message_id,
        "save_path": str(Path(save_path).resolve()),
    }, timeout=120.0)

    if result.get("ok"):
        console.print(f"[green]✓ Downloaded to {result.get('path')}[/green]")
    else:
        console.print(f"[red]✗ {result.get('error')}[/red]")
        raise typer.Exit(1)


@user_app.command("whoami")
@async_command
async def user_whoami() -> None:
    """Show current Telegram account."""
    result = daemon_request("health", method="GET")

    if result.get("ok"):
        user = result.get("user", {})
        console.print(Panel.fit(
            f"[bold]{user.get('first_name')} {user.get('last_name', '')}[/bold]\n"
            f"Username: @{user.get('username')}\n"
            f"Phone: {user.get('phone')}\n"
            f"ID: {user.get('id')}",
            title="👤 Current Account",
            border_style="blue",
        ))
    else:
        console.print(f"[red]✗ {result.get('error')}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Bot Commands
# =============================================================================


@bot_app.command("send")
@async_command
async def bot_send(
    message: str = typer.Argument(..., help="Message text"),
    chat_id: str = typer.Option(None, "--chat-id", "-c", help="Target chat ID"),
) -> None:
    """Send a message via bot."""
    from mcp_telegram.bot.client import BotClient

    config = load_config()
    if not config.has_bot:
        console.print("[red]✗ Bot not configured. Run: tg login[/red]")
        raise typer.Exit(1)

    client = BotClient(config)

    try:
        result = await client.send_message(message, chat_id)
        console.print(f"[green]✓ Sent (ID: {result.get('message_id')})[/green]")
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


@bot_app.command("send-file")
@async_command
async def bot_send_file(
    file_path: str = typer.Argument(..., help="Path to file"),
    caption: str = typer.Option("", "--caption", "-c", help="Caption"),
    chat_id: str = typer.Option(None, "--chat-id", help="Target chat ID"),
) -> None:
    """Send a file via bot."""
    from mcp_telegram.bot.client import BotClient

    config = load_config()
    if not config.has_bot:
        console.print("[red]✗ Bot not configured. Run: tg login[/red]")
        raise typer.Exit(1)

    if not Path(file_path).exists():
        console.print(f"[red]✗ File not found: {file_path}[/red]")
        raise typer.Exit(1)

    client = BotClient(config)

    try:
        result = await client.send_document(file_path, caption, chat_id)
        console.print(f"[green]✓ Sent[/green]")
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


@bot_app.command("send-photo")
@async_command
async def bot_send_photo(
    file_path: str = typer.Argument(..., help="Path to image"),
    caption: str = typer.Option("", "--caption", "-c", help="Caption"),
    chat_id: str = typer.Option(None, "--chat-id", help="Target chat ID"),
) -> None:
    """Send a photo via bot."""
    from mcp_telegram.bot.client import BotClient

    config = load_config()
    if not config.has_bot:
        console.print("[red]✗ Bot not configured. Run: tg login[/red]")
        raise typer.Exit(1)

    client = BotClient(config)

    try:
        result = await client.send_photo(file_path, caption, chat_id)
        console.print(f"[green]✓ Sent[/green]")
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


@bot_app.command("send-voice")
@async_command
async def bot_send_voice(
    file_path: str = typer.Argument(..., help="Path to audio file"),
    caption: str = typer.Option("", "--caption", "-c", help="Caption"),
    chat_id: str = typer.Option(None, "--chat-id", help="Target chat ID"),
) -> None:
    """Send a voice message via bot."""
    from mcp_telegram.bot.client import BotClient

    config = load_config()
    if not config.has_bot:
        console.print("[red]✗ Bot not configured. Run: tg login[/red]")
        raise typer.Exit(1)

    client = BotClient(config)

    try:
        result = await client.send_voice(file_path, caption, chat_id)
        console.print(f"[green]✓ Sent[/green]")
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


@bot_app.command("messages")
@async_command
async def bot_messages(
    limit: int = typer.Option(10, "--limit", "-n", help="Number of messages"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Get messages received by bot."""
    from mcp_telegram.bot.client import BotClient

    config = load_config()
    if not config.has_bot:
        console.print("[red]✗ Bot not configured. Run: tg login[/red]")
        raise typer.Exit(1)

    client = BotClient(config)

    try:
        messages = await client.get_messages(limit)

        if as_json:
            print(json.dumps(messages, indent=2, ensure_ascii=False))
            return

        if not messages:
            console.print("[yellow]No messages[/yellow]")
            return

        for msg in messages:
            from_user = msg.get("from", {})
            text = msg.get("text", "")[:100]
            console.print(
                f"[cyan]{from_user.get('first_name', 'Unknown')}[/cyan]: {text}"
            )
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


@bot_app.command("info")
@async_command
async def bot_info() -> None:
    """Show bot information."""
    from mcp_telegram.bot.client import BotClient

    config = load_config()
    if not config.has_bot:
        console.print("[red]✗ Bot not configured. Run: tg login[/red]")
        raise typer.Exit(1)

    client = BotClient(config)

    try:
        info = await client.get_me()
        console.print(Panel.fit(
            f"[bold]{info.get('first_name')}[/bold]\n"
            f"Username: @{info.get('username')}\n"
            f"ID: {info.get('id')}\n"
            f"Can join groups: {info.get('can_join_groups', False)}\n"
            f"Can read all messages: {info.get('can_read_all_group_messages', False)}",
            title="🤖 Bot Info",
            border_style="blue",
        ))
    except Exception as e:
        console.print(f"[red]✗ {e}[/red]")
        raise typer.Exit(1)


# =============================================================================
# Entry Point
# =============================================================================


def main() -> None:
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
