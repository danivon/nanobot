"""Drive the official CAS login page with Chrome and CDP."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import httpx
import websockets

logger = logging.getLogger(__name__)

DEFAULT_CAS_LOGIN_URL = (
    "https://cas.scau.edu.cn/lyuapServer/login"
    "?service=https://portal.scau.edu.cn/shiro-cas"
)

_POLL_FORM_JS = "!!document.querySelector('input[type=password]')"

_GREETING_JS = """(() => {
  const hits = [...document.querySelectorAll('body *')]
    .filter(e => /(早上好|上午好|下午好|晚上好)/.test(e.textContent || ''))
    .sort((a, b) => (a.textContent || '').length - (b.textContent || '').length);
  for (const el of hits.slice(0, 4)) {
    const value = (el.textContent || '').trim();
    let match = value.match(/([\\u4e00-\\u9fa5]{2,4})\\s*(?:，|,)?\\s*(?:早上好|上午好|下午好|晚上好)/);
    if (match) return match[1];
    match = value.match(/(?:早上好|上午好|下午好|晚上好)\\s*(?:，|,)?\\s*([\\u4e00-\\u9fa5]{2,4})/);
    if (match) return match[1];
  }
  return '';
})()"""

_FILL_JS = """(() => {
  const setVal = (el, value) => {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  };
  const password = document.querySelector('input[type=password]');
  if (!password) return 'NO_FORM';
  const inputs = [...document.querySelectorAll('input')]
    .filter(i => !['password', 'hidden', 'checkbox', 'radio'].includes(i.type) && !i.readOnly && !i.disabled);
  const user = inputs.find(i => /user|account|name|id|学|工/i.test((i.name || '') + (i.id || '') + (i.placeholder || ''))) || inputs[0];
  if (!user) return 'NO_USER_FIELD';
  setVal(user, %s);
  setVal(password, %s);
  return 'FILLED';
})()"""

_CLICK_JS = """(() => {
  const button = [...document.querySelectorAll('button, input[type=submit], [role=button]')]
    .find(item => /登\\s*录|login/i.test((item.textContent || '') + (item.value || '')))
    || document.querySelector('button[type=submit], input[type=submit], button');
  if (!button) return 'NO_BTN';
  button.click();
  return 'CLICKED';
})()"""


class CasDriverError(RuntimeError):
    """The official login page could not be driven to completion."""


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _chrome_binary() -> str:
    configured = os.environ.get("NANOBOT_SCHOOL_PORTAL_CHROME", "").strip()
    candidates = [
        configured,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome") or "",
        shutil.which("chromium") or "",
        shutil.which("chromium-browser") or "",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise CasDriverError("chrome_not_found")


async def _cdp(ws: Any, message_id: int, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    await ws.send(json.dumps({"id": message_id, "method": method, "params": params or {}}))
    while True:
        message = json.loads(await ws.recv())
        if message.get("id") == message_id:
            result = message.get("result", {})
            return result if isinstance(result, dict) else {}


async def _eval(ws: Any, message_id: int, expression: str) -> Any:
    result = await _cdp(
        ws,
        message_id,
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True},
    )
    return result.get("result", {}).get("value")


def _school_cookies(cookies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for cookie in cookies:
        domain = str(cookie.get("domain") or "").lstrip(".").lower()
        if domain == "scau.edu.cn" or domain.endswith(".scau.edu.cn"):
            result.append(cookie)
    return result


def _write_diagnostic(path: Path | None, data: str) -> None:
    if path is None or not data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(base64.b64decode(data))
    path.chmod(0o600)
    logger.warning("portal login timeout screenshot: %s", path)


async def cas_login(
    username: str,
    password: str,
    *,
    diagnostic_path: Path | None = None,
    timeout_s: float = 25.0,
) -> dict[str, Any]:
    """Fill the official login form and return the harvested browser session."""
    chrome = _chrome_binary()
    cas_url = os.environ.get("NANOBOT_SCHOOL_PORTAL_CAS_URL", DEFAULT_CAS_LOGIN_URL)
    port = _free_port()
    with tempfile.TemporaryDirectory(prefix="nanobot-school-portal-") as profile:
        process = subprocess.Popen(
            [
                chrome,
                "--headless=new",
                f"--remote-debugging-port={port}",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "--disable-gpu",
                "--disable-blink-features=AutomationControlled",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            ws_url = await _wait_for_cdp(port)
            async with websockets.connect(ws_url, max_size=16 * 1024 * 1024) as ws:
                message_id = 1
                await _cdp(ws, message_id, "Page.enable")
                message_id += 1
                await _cdp(ws, message_id, "Network.enable")
                message_id += 1
                await _cdp(
                    ws,
                    message_id,
                    "Page.addScriptToEvaluateOnNewDocument",
                    {
                        "source": (
                            "Object.defineProperty(navigator, 'webdriver', "
                            "{get: () => undefined});"
                        )
                    },
                )
                message_id += 1
                await _cdp(ws, message_id, "Page.navigate", {"url": cas_url})
                message_id += 1

                deadline = time.monotonic() + timeout_s
                while time.monotonic() < deadline:
                    if await _eval(ws, message_id, _POLL_FORM_JS):
                        break
                    await asyncio.sleep(0.5)
                else:
                    raise CasDriverError("form_not_found")

                fill = await _eval(
                    ws,
                    message_id,
                    _FILL_JS % (json.dumps(username), json.dumps(password)),
                )
                if fill != "FILLED":
                    raise CasDriverError(f"fill_failed:{fill}")

                clicked = await _eval(ws, message_id, _CLICK_JS)
                if clicked != "CLICKED":
                    raise CasDriverError(f"click_failed:{clicked}")

                while time.monotonic() < deadline:
                    url = str(await _eval(ws, message_id, "window.location.href") or "")
                    if "portal.scau.edu.cn" in url and "cas.scau.edu.cn" not in url:
                        message_id += 1
                        cookies = await _cdp(ws, message_id, "Storage.getCookies")
                        message_id += 1
                        local_storage = await _eval(ws, message_id, "JSON.stringify(window.localStorage)")
                        real_name = str(await _eval(ws, message_id, _GREETING_JS) or "")
                        return {
                            "ok": True,
                            "cookies": _school_cookies(cookies.get("cookies", [])),
                            "local_storage": local_storage or "{}",
                            "real_name": real_name,
                        }
                    slider = await _eval(
                        ws,
                        message_id,
                        "!!document.querySelector('#captcha-box iframe, #captcha-box *, "
                        "[id*=tcaptcha], [class*=tac-show]')",
                    )
                    if slider:
                        return {"ok": False, "code": "CAPTCHA_REQUIRED"}
                    error_text = await _eval(
                        ws,
                        message_id,
                        "([...document.querySelectorAll('.ant-message *, [class*=error]')]"
                        ".map(e => e.textContent || '').join(' ').trim())",
                    )
                    if error_text:
                        text = str(error_text).strip()[:120]
                        if "密码" in text or "口令" in text or "账号" in text:
                            return {"ok": False, "code": "PASSERROR"}
                        if "验证码" in text:
                            return {"ok": False, "code": "CODEFALSE"}
                        if "不存在" in text:
                            return {"ok": False, "code": "NOUSER"}
                        return {"ok": False, "code": "UNKNOWN", "message": text}
                    await asyncio.sleep(0.6)

                message_id += 1
                screenshot = await _cdp(
                    ws,
                    message_id,
                    "Page.captureScreenshot",
                    {"format": "png"},
                )
                _write_diagnostic(diagnostic_path, str(screenshot.get("data") or ""))
                current_url = str(await _eval(ws, message_id + 1, "window.location.href") or "")
                raise CasDriverError(f"no_result_timeout url={current_url}")
        finally:
            if process.poll() is None:
                process.kill()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


async def _wait_for_cdp(port: int) -> str:
    for _ in range(50):
        try:
            async with httpx.AsyncClient(timeout=1.0) as client:
                response = await client.get(f"http://127.0.0.1:{port}/json/list")
            targets = response.json()
            page = next((item for item in targets if item.get("type") == "page"), None)
            if page and page.get("webSocketDebuggerUrl"):
                return str(page["webSocketDebuggerUrl"])
        except Exception:
            pass
        await asyncio.sleep(0.2)
    raise CasDriverError("chrome_cdp_unavailable")
