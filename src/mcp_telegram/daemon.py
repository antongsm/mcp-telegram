"""MTProto daemon - holds persistent Telegram connection.

This daemon solves the SQLite session locking problem by maintaining
a single connection that multiple clients (MCP, CLI) can share via HTTP.

Architecture:
    CLI/MCP → HTTP → Daemon (:19876) → Telegram MTProto

Usage:
    python -m mcp_telegram.daemon start    # Start daemon
    python -m mcp_telegram.daemon stop     # Stop daemon
    python -m mcp_telegram.daemon status   # Check status
    python -m mcp_telegram.daemon login    # Interactive login
"""

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Any

from aiohttp import web
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

from mcp_telegram.config import (
    Config,
    get_config_dir,
    get_log_path,
    get_pid_path,
    get_session_path,
    load_config,
)
from mcp_telegram.user.client import UserClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(get_log_path()),
    ],
)
logger = logging.getLogger(__name__)

# Global state
_client: UserClient | None = None
_config: Config | None = None


async def get_client() -> UserClient:
    """Get or create the MTProto client."""
    global _client, _config

    if _config is None:
        _config = load_config()

    if _client is None:
        _client = UserClient(_config)

    if not await _client.is_authorized():
        raise RuntimeError("Not authorized. Run 'tg login' first.")

    return _client


# =============================================================================
# HTTP Handlers
# =============================================================================


async def handle_health(request: web.Request) -> web.Response:
    """Health check endpoint."""
    try:
        client = await get_client()
        me = await client.get_me()
        return web.json_response({
            "ok": True,
            "status": "connected",
            "user": me,
        })
    except Exception as e:
        return web.json_response({
            "ok": False,
            "status": "error",
            "error": str(e),
        }, status=500)


async def handle_send_message(request: web.Request) -> web.Response:
    """Send a text message."""
    try:
        data = await request.json()
        entity = data.get("entity")
        message = data.get("message", "")
        reply_to = data.get("reply_to")

        if not entity:
            return web.json_response(
                {"ok": False, "error": "entity is required"},
                status=400,
            )

        client = await get_client()
        result = await client.send_message(entity, message, reply_to)

        return web.json_response({"ok": True, **result})

    except Exception as e:
        logger.exception("Error in send_message")
        return web.json_response(
            {"ok": False, "error": str(e)},
            status=500,
        )


async def handle_send_file(request: web.Request) -> web.Response:
    """Send a file."""
    try:
        data = await request.json()
        entity = data.get("entity")
        file_path = data.get("file_path")
        caption = data.get("caption", "")
        voice = data.get("voice", False)

        if not entity or not file_path:
            return web.json_response(
                {"ok": False, "error": "entity and file_path are required"},
                status=400,
            )

        if not Path(file_path).exists():
            return web.json_response(
                {"ok": False, "error": f"File not found: {file_path}"},
                status=400,
            )

        client = await get_client()
        result = await client.send_file(entity, file_path, caption, voice)

        return web.json_response({"ok": True, **result})

    except Exception as e:
        logger.exception("Error in send_file")
        return web.json_response(
            {"ok": False, "error": str(e)},
            status=500,
        )


async def handle_get_messages(request: web.Request) -> web.Response:
    """Get messages from a chat."""
    try:
        data = await request.json()
        entity = data.get("entity")
        limit = data.get("limit", 10)

        if not entity:
            return web.json_response(
                {"ok": False, "error": "entity is required"},
                status=400,
            )

        client = await get_client()
        messages = await client.get_messages(entity, limit)

        return web.json_response({"ok": True, "messages": messages})

    except Exception as e:
        logger.exception("Error in get_messages")
        return web.json_response(
            {"ok": False, "error": str(e)},
            status=500,
        )


async def handle_search_dialogs(request: web.Request) -> web.Response:
    """Search dialogs."""
    try:
        data = await request.json()
        query = data.get("query", "")
        limit = data.get("limit", 10)

        client = await get_client()
        dialogs = await client.search_dialogs(query, limit)

        return web.json_response({"ok": True, "dialogs": dialogs})

    except Exception as e:
        logger.exception("Error in search_dialogs")
        return web.json_response(
            {"ok": False, "error": str(e)},
            status=500,
        )


async def handle_download_media(request: web.Request) -> web.Response:
    """Download media from a message."""
    try:
        data = await request.json()
        entity = data.get("entity")
        message_id = data.get("message_id")
        save_path = data.get("save_path")

        if not entity or not message_id or not save_path:
            return web.json_response(
                {"ok": False, "error": "entity, message_id, and save_path are required"},
                status=400,
            )

        client = await get_client()
        result = await client.download_media(entity, message_id, save_path)

        return web.json_response({"ok": True, **result})

    except Exception as e:
        logger.exception("Error in download_media")
        return web.json_response(
            {"ok": False, "error": str(e)},
            status=500,
        )


async def handle_edit_message(request: web.Request) -> web.Response:
    """Edit a message."""
    try:
        data = await request.json()
        entity = data.get("entity")
        message_id = data.get("message_id")
        text = data.get("text")

        if not entity or not message_id or not text:
            return web.json_response(
                {"ok": False, "error": "entity, message_id, and text are required"},
                status=400,
            )

        client = await get_client()
        result = await client.edit_message(entity, message_id, text)

        return web.json_response({"ok": True, **result})

    except Exception as e:
        logger.exception("Error in edit_message")
        return web.json_response(
            {"ok": False, "error": str(e)},
            status=500,
        )


async def handle_delete_messages(request: web.Request) -> web.Response:
    """Delete messages."""
    try:
        data = await request.json()
        entity = data.get("entity")
        message_ids = data.get("message_ids", [])

        if not entity or not message_ids:
            return web.json_response(
                {"ok": False, "error": "entity and message_ids are required"},
                status=400,
            )

        client = await get_client()
        result = await client.delete_messages(entity, message_ids)

        return web.json_response({"ok": True, **result})

    except Exception as e:
        logger.exception("Error in delete_messages")
        return web.json_response(
            {"ok": False, "error": str(e)},
            status=500,
        )


# =============================================================================
# Daemon Lifecycle
# =============================================================================


def create_app() -> web.Application:
    """Create the aiohttp application."""
    app = web.Application()

    # Routes
    app.router.add_get("/health", handle_health)
    app.router.add_post("/send_message", handle_send_message)
    app.router.add_post("/send_file", handle_send_file)
    app.router.add_post("/get_messages", handle_get_messages)
    app.router.add_post("/search_dialogs", handle_search_dialogs)
    app.router.add_post("/download_media", handle_download_media)
    app.router.add_post("/edit_message", handle_edit_message)
    app.router.add_post("/delete_messages", handle_delete_messages)

    return app


async def run_daemon() -> None:
    """Run the daemon."""
    global _client, _config

    _config = load_config()

    if not _config.has_user:
        logger.error("User not configured. Run 'tg login' first.")
        sys.exit(1)

    pid_path = get_pid_path()

    # Check for existing daemon
    if pid_path.exists():
        try:
            old_pid = int(pid_path.read_text().strip())
            os.kill(old_pid, 0)  # Check if running
            logger.error(f"Daemon already running (PID {old_pid})")
            sys.exit(1)
        except (OSError, ValueError):
            pass  # Not running, continue

    # Write PID
    pid_path.write_text(str(os.getpid()))

    # Connect to Telegram
    _client = UserClient(_config)
    try:
        me = await _client.get_me()
        logger.info(f"Connected as {me.get('first_name')} (@{me.get('username')})")
    except Exception as e:
        logger.error(f"Failed to connect: {e}")
        pid_path.unlink(missing_ok=True)
        sys.exit(1)

    # Setup signal handlers
    loop = asyncio.get_event_loop()

    async def shutdown():
        logger.info("Shutting down...")
        if _client:
            await _client.disconnect()
        pid_path.unlink(missing_ok=True)

    def handle_signal(sig):
        logger.info(f"Received signal {sig}")
        asyncio.create_task(shutdown())
        loop.stop()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))

    # Start HTTP server
    app = create_app()
    runner = web.AppRunner(app)
    await runner.setup()

    host = _config.daemon.host
    port = _config.daemon.port
    site = web.TCPSite(runner, host, port)
    await site.start()

    logger.info(f"Daemon listening on {host}:{port}")

    # Run forever
    try:
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        pass
    finally:
        await shutdown()
        await runner.cleanup()


async def do_login() -> None:
    """Interactive login."""
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    console.print(Panel.fit(
        "[bold blue]MCP Telegram - MTProto Login[/bold blue]\n\n"
        "You need API credentials from Telegram:\n"
        "1. Go to [link]https://my.telegram.org/apps[/link]\n"
        "2. Log in with your phone number\n"
        "3. Create an app (any name)\n"
        "4. Copy API ID and API Hash",
        title="🔐 Setup",
        border_style="blue",
    ))

    config = load_config()

    # Get credentials
    if config.user.api_id:
        console.print(f"\n[dim]Current API ID: {config.user.api_id}[/dim]")
        api_id = console.input("[cyan]API ID[/cyan] (Enter to keep): ").strip()
        if api_id:
            config.user.api_id = api_id
    else:
        config.user.api_id = console.input("\n[cyan]API ID[/cyan]: ").strip()

    if config.user.api_hash:
        console.print(f"[dim]Current API Hash: {config.user.api_hash[:8]}...[/dim]")
        api_hash = console.input("[cyan]API Hash[/cyan] (Enter to keep): ").strip()
        if api_hash:
            config.user.api_hash = api_hash
    else:
        config.user.api_hash = console.input("[cyan]API Hash[/cyan]: ").strip()

    if config.user.phone:
        console.print(f"[dim]Current phone: {config.user.phone}[/dim]")
        phone = console.input("[cyan]Phone[/cyan] (Enter to keep): ").strip()
        if phone:
            config.user.phone = phone
    else:
        config.user.phone = console.input("[cyan]Phone[/cyan] (+79001234567): ").strip()

    # Save config
    config.save()

    # Connect and authorize
    console.print("\n[yellow]Connecting to Telegram...[/yellow]")

    client = TelegramClient(
        str(get_session_path()),
        int(config.user.api_id),
        config.user.api_hash,
    )

    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        console.print(Panel.fit(
            f"[bold green]Already logged in![/bold green]\n"
            f"Account: {me.first_name} (@{me.username})",
            title="✅ Success",
            border_style="green",
        ))
        await client.disconnect()
        return

    # Request code
    await client.send_code_request(config.user.phone)
    console.print("[green]Verification code sent to Telegram app[/green]")

    code = console.input("\n[cyan]Enter code[/cyan]: ").strip()

    try:
        await client.sign_in(config.user.phone, code)
    except SessionPasswordNeededError:
        password = console.input("[cyan]2FA Password[/cyan]: ", password=True).strip()
        await client.sign_in(password=password)

    me = await client.get_me()
    console.print(Panel.fit(
        f"[bold green]Login successful![/bold green]\n"
        f"Account: {me.first_name} (@{me.username})\n\n"
        f"Session saved to: {get_session_path()}",
        title="✅ Success",
        border_style="green",
    ))

    await client.disconnect()


def daemon_start() -> None:
    """Start the daemon."""
    asyncio.run(run_daemon())


def daemon_stop() -> None:
    """Stop the daemon."""
    pid_path = get_pid_path()

    if not pid_path.exists():
        print("Daemon not running")
        return

    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"Sent SIGTERM to PID {pid}")
    except (OSError, ValueError) as e:
        print(f"Failed to stop daemon: {e}")
        pid_path.unlink(missing_ok=True)


def daemon_status() -> None:
    """Check daemon status."""
    import httpx

    config = load_config()
    pid_path = get_pid_path()

    # Check PID
    if pid_path.exists():
        try:
            pid = int(pid_path.read_text().strip())
            os.kill(pid, 0)
            print(f"Daemon running (PID {pid})")
        except (OSError, ValueError):
            print("Daemon not running (stale PID file)")
            return
    else:
        print("Daemon not running")
        return

    # Check health
    try:
        response = httpx.get(f"{config.daemon.url}/health", timeout=5.0)
        data = response.json()
        if data.get("ok"):
            user = data.get("user", {})
            print(f"Connected as {user.get('first_name')} (@{user.get('username')})")
        else:
            print(f"Health check failed: {data.get('error')}")
    except Exception as e:
        print(f"Cannot reach daemon: {e}")


def login() -> None:
    """Interactive login."""
    asyncio.run(do_login())


def main() -> None:
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python -m mcp_telegram.daemon <command>")
        print("Commands: start, stop, status, login")
        sys.exit(1)

    command = sys.argv[1]

    if command == "start":
        daemon_start()
    elif command == "stop":
        daemon_stop()
    elif command == "status":
        daemon_status()
    elif command == "login":
        login()
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
