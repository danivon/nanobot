"""Credential handling, session persistence, and CAS login orchestration."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import stat
import tempfile
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .cas_driver import CasDriverError, cas_login

logger = logging.getLogger(__name__)

_ERROR_MESSAGES = {
    "NOUSER": "用户不存在",
    "PASSERROR": "密码错误",
    "CODEFALSE": "错误次数过多需要验证码，请稍后再试或先登录官网一次",
    "NOREGISTER": "该账号未注册",
    "NOAUTHORIZATION": "该账号无权访问信息门户",
    "TWOVERIFY": "该账号开启了二次验证，暂不支持",
    "CAPTCHA_REQUIRED": "账号触发滑块验证，请先到官网正常登录一次解除风控后再试",
}


@dataclass(frozen=True)
class PortalCredentials:
    username: str
    password: str


class PortalSessionStore:
    """Keep the browser-derived session outside the repository."""

    def __init__(self, state_dir: Path | None = None) -> None:
        configured = os.environ.get("NANOBOT_SCHOOL_PORTAL_STATE_DIR", "").strip()
        self.state_dir = (
            state_dir
            or (Path(configured).expanduser() if configured else Path.home() / ".nanobot" / "extensions" / "school-portal")
        ).resolve()
        self.session_path = self.state_dir / "session.json"
        self.credentials_path = self.state_dir / "credentials.json"
        self.diagnostic_path = self.state_dir / "last-login-timeout.png"

    def load(self) -> dict[str, Any] | None:
        if not self.session_path.is_file():
            return None
        try:
            payload = json.loads(self.session_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("portal session file is unreadable")
            return None
        if not isinstance(payload, dict) or not payload.get("username"):
            return None
        cookies = payload.get("cookies")
        if not isinstance(cookies, list):
            return None
        return payload

    def save(self, session: dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.state_dir.chmod(0o700)
        fd, temporary = tempfile.mkstemp(prefix=".session-", dir=self.state_dir, text=True)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(session, handle, ensure_ascii=False)
            os.replace(temporary, self.session_path)
            self.session_path.chmod(0o600)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def credentials(self) -> PortalCredentials | None:
        username = os.environ.get("NANOBOT_SCHOOL_PORTAL_USERNAME", "").strip()
        password = os.environ.get("NANOBOT_SCHOOL_PORTAL_PASSWORD", "")
        if username and password:
            return PortalCredentials(username=username, password=password)
        path = self.credentials_path
        if not path.is_file():
            return None
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                logger.warning("portal credentials file permissions are too open: %s", path)
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("portal credentials file is unreadable")
            return None
        if not isinstance(payload, dict):
            return None
        username = str(payload.get("username") or "").strip()
        password = str(payload.get("password") or "")
        if not username or not password:
            return None
        return PortalCredentials(username=username, password=password)

    def status(self) -> dict[str, Any]:
        session = self.load()
        if session is None:
            return {"logged_in": False}
        return {
            "logged_in": True,
            "username": str(session.get("username") or ""),
            "real_name": str(session.get("real_name") or ""),
            "logged_at": session.get("logged_at", 0),
        }


def _normalize(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _redact(message: str, password: str) -> str:
    return message.replace(password, "***") if password else message


class SchoolPortalService:
    """Minimal login service exposed through MCP."""

    def __init__(
        self,
        *,
        store: PortalSessionStore | None = None,
        login_fn: Callable[[str, str], Awaitable[dict[str, Any]]] | None = None,
    ) -> None:
        self.store = store or PortalSessionStore()
        self._login_fn = login_fn or cas_login
        self._lock = asyncio.Lock()

    def status(self) -> dict[str, Any]:
        return self.store.status()

    async def login(self) -> dict[str, Any]:
        credentials = self.store.credentials()
        if credentials is None:
            return {
                "ok": False,
                "error": (
                    f"未配置学校门户凭证，请填写 {self.store.credentials_path} "
                    "或设置环境变量"
                ),
            }
        username = _normalize(credentials.username)
        password = _normalize(credentials.password)
        if not username or not password:
            return {"ok": False, "error": "用户名或密码为空"}

        async with self._lock:
            try:
                result = await self._login_fn(username, password)
            except CasDriverError:
                logger.warning("portal CAS driver failed")
                return {"ok": False, "error": "统一认证服务访问异常，请稍后重试"}
            except Exception:
                logger.exception("portal CAS login failed")
                return {"ok": False, "error": "登录过程出现异常"}

            if not result.get("ok"):
                code = str(result.get("code") or "")
                message = str(
                    result.get("error")
                    or result.get("message")
                    or _ERROR_MESSAGES.get(code, "登录失败")
                )
                return {"ok": False, "error": _redact(message, password)}

            session = {
                "username": username,
                "real_name": str(result.get("real_name") or ""),
                "logged_at": time.time(),
                "cookies": result.get("cookies", []),
                "local_storage": result.get("local_storage", "{}"),
            }
            self.store.save(session)
            logger.info("school portal login succeeded")
            return {
                "ok": True,
                "username": username,
                "real_name": session["real_name"],
                "logged_at": session["logged_at"],
            }
