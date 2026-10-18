"""Minimal example tool for the fork-owned extension package."""

from __future__ import annotations

from typing import Any

from nanobot.agent.tools.base import Tool


class EchoTool(Tool):
    """Return the provided text unchanged."""

    @property
    def name(self) -> str:
        return "extension_echo"

    @property
    def description(self) -> str:
        return "Return the provided text unchanged. Minimal smoke-test tool for the fork extension package."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Text to return unchanged.",
                },
            },
            "required": ["text"],
            "additionalProperties": False,
        }

    @property
    def read_only(self) -> bool:
        return True

    async def execute(self, text: str, **kwargs: Any) -> str:
        return text
