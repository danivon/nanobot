"""Tests for the school portal MCP service."""

from __future__ import annotations

import json
import stat
from pathlib import Path
from typing import Any

import pytest
from nanobot_ext.school_portal.service import PortalSessionStore, SchoolPortalService


def _store(tmp_path: Path) -> PortalSessionStore:
    return PortalSessionStore(tmp_path / "portal")


def _write_credentials(store: PortalSessionStore, username: str, password: str) -> None:
    store.state_dir.mkdir(parents=True, exist_ok=True)
    store.credentials_path.write_text(
        json.dumps({"username": username, "password": password}),
        encoding="utf-8",
    )
    store.credentials_path.chmod(0o600)


def test_status_without_session(tmp_path: Path) -> None:
    service = SchoolPortalService(store=_store(tmp_path))

    assert service.status() == {"logged_in": False}


@pytest.mark.asyncio
async def test_login_requires_credentials(tmp_path: Path) -> None:
    service = SchoolPortalService(store=_store(tmp_path))

    result = await service.login()

    assert result["ok"] is False
    assert "未配置" in result["error"]


@pytest.mark.asyncio
async def test_login_persists_session_without_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    _write_credentials(store, "20240001", "secret")
    captured: dict[str, str] = {}

    async def fake_login(username: str, password: str) -> dict[str, Any]:
        captured.update(username=username, password=password)
        return {
            "ok": True,
            "cookies": [{"name": "CASTGC", "value": "cookie-value", "domain": "cas.scau.edu.cn"}],
            "local_storage": "{}",
            "real_name": "测试用户",
        }

    monkeypatch.delenv("NANOBOT_SCHOOL_PORTAL_USERNAME", raising=False)
    monkeypatch.delenv("NANOBOT_SCHOOL_PORTAL_PASSWORD", raising=False)
    service = SchoolPortalService(store=store, login_fn=fake_login)

    result = await service.login()

    assert captured == {"username": "20240001", "password": "secret"}
    assert result["ok"] is True
    assert result["username"] == "20240001"
    assert "secret" not in json.dumps(result)
    assert service.status()["logged_in"] is True
    assert "cookies" not in service.status()
    payload = json.loads(store.session_path.read_text(encoding="utf-8"))
    assert payload["username"] == "20240001"
    assert "password" not in payload
    assert stat.S_IMODE(store.session_path.stat().st_mode) == 0o600


@pytest.mark.asyncio
async def test_login_failure_redacts_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)
    _write_credentials(store, "20240001", "secret")

    async def fake_login(username: str, password: str) -> dict[str, Any]:
        return {"ok": False, "error": f"bad password {password}"}

    monkeypatch.delenv("NANOBOT_SCHOOL_PORTAL_USERNAME", raising=False)
    monkeypatch.delenv("NANOBOT_SCHOOL_PORTAL_PASSWORD", raising=False)
    service = SchoolPortalService(store=store, login_fn=fake_login)

    result = await service.login()

    assert result["ok"] is False
    assert "secret" not in result["error"]
    assert "***" in result["error"]


@pytest.mark.asyncio
async def test_environment_credentials_are_used(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store(tmp_path)

    async def fake_login(username: str, password: str) -> dict[str, Any]:
        assert username == "env-user"
        assert password == "env-password"
        return {"ok": True, "cookies": [], "local_storage": "{}"}

    monkeypatch.setenv("NANOBOT_SCHOOL_PORTAL_USERNAME", "env-user")
    monkeypatch.setenv("NANOBOT_SCHOOL_PORTAL_PASSWORD", "env-password")
    service = SchoolPortalService(store=store, login_fn=fake_login)

    result = await service.login()

    assert result["ok"] is True
    assert service.status()["username"] == "env-user"
