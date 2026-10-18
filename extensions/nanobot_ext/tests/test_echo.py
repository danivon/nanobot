"""Contract and discovery tests for the example extension tool."""

from importlib.metadata import entry_points

import pytest
from nanobot_ext.tools.echo import EchoTool


def test_echo_tool_contract() -> None:
    tool = EchoTool()

    assert tool.name == "extension_echo"
    assert tool.read_only is True
    assert tool.parameters["required"] == ["text"]


@pytest.mark.asyncio
async def test_echo_tool_returns_input() -> None:
    tool = EchoTool()

    assert await tool.execute(text="hello") == "hello"


def test_echo_tool_entry_point_is_installed() -> None:
    loaded = {entry.name: entry.load() for entry in entry_points(group="nanobot.tools")}

    assert loaded.get("extension_echo") is EchoTool
