"""MCP Telegram - Unified Telegram integration for AI and CLI.

Three interfaces:
- MCP: `tg mcp` for Claude Code
- CLI: `tg user send`, `tg bot send` for humans
- HTTP API: daemon on :19876 for integrations
"""

from mcp_telegram.cli import app, main

__all__ = ["app", "main"]

if __name__ == "__main__":
    main()
