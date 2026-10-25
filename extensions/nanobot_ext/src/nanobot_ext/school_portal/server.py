"""Independent stdio MCP server for the school portal."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from .service import SchoolPortalService

SERVER_NAME = "school-portal"


def create_server(service: SchoolPortalService | None = None) -> FastMCP:
    portal = service or SchoolPortalService()
    server = FastMCP(
        SERVER_NAME,
        instructions="Minimal read-only login support for the SCAU information portal. Never expose cookies, JWTs, or passwords.",
        log_level="WARNING",
    )

    @server.tool(
        name="portal_status",
        description="Check whether a saved school portal CAS session exists.",
    )
    async def portal_status() -> str:
        status = portal.status()
        if not status.get("logged_in"):
            return "未登录：本地没有可用的门户会话。"
        username = status.get("username", "")
        real_name = status.get("real_name", "")
        suffix = f"（{real_name}）" if real_name else ""
        return f"已登录：{username}{suffix}。会话可能已过期，必要时重新登录。"

    @server.tool(
        name="portal_login",
        description=(
            "Log in to the school portal through CAS using credentials configured on this machine. "
            "This tool never accepts or returns a password."
        ),
    )
    async def portal_login() -> str:
        result: dict[str, Any] = await portal.login()
        if not result.get("ok"):
            return f"登录失败：{result.get('error', '未知错误')}"
        username = result.get("username", "")
        real_name = result.get("real_name", "")
        suffix = f"（{real_name}）" if real_name else ""
        return f"登录成功：{username}{suffix}"

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
