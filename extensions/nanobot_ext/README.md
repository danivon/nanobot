# nanobot-ext

Fork-owned Python extensions for nanobot.

The package exposes tools through the `nanobot.tools` entry point. The included `extension_echo` tool is a minimal smoke test and can be replaced by the first real extension.

Install the package from the repository root:

```bash
uv sync --all-extras --dev
uv run --no-sync python -m scripts.install_channel_dependencies --all-channels
```

Run the extension tests:

```bash
uv run --no-sync pytest extensions/nanobot_ext/tests -q
```

Add a tool by creating a module under `src/nanobot_ext/tools/` and registering its class in `pyproject.toml` under `[project.entry-points."nanobot.tools"]`. Restart the gateway after changing Python tool code.

## School Portal MCP

The school portal integration is an independent stdio MCP server. It provides `portal_status` and `portal_login`; the login tool reads credentials from a local file or environment variables and never accepts a password as a tool argument.

Create the runtime state directory and credentials file:

```bash
mkdir -p ~/.nanobot/extensions/school-portal
chmod 700 ~/.nanobot/extensions/school-portal
cp extensions/nanobot_ext/examples/credentials.example.json \
  ~/.nanobot/extensions/school-portal/credentials.json
chmod 600 ~/.nanobot/extensions/school-portal/credentials.json
```

Edit the copied credentials file with the real account. Alternatively, set `NANOBOT_SCHOOL_PORTAL_USERNAME` and `NANOBOT_SCHOOL_PORTAL_PASSWORD` in the gateway environment. The server stores the resulting browser session at `~/.nanobot/extensions/school-portal/session.json` with permissions `600`.

Register the server in `~/.nanobot/config.json`:

```json
{
  "tools": {
    "mcpServers": {
      "school-portal": {
        "command": "/Users/dcj/ai/nanobot/.venv/bin/nanobot-school-portal-mcp",
        "tool_timeout": 120
      }
    }
  }
}
```

The skill source is at `skills/school-portal/SKILL.md`. For local development, link it into the workspace:

```bash
mkdir -p ~/.nanobot/workspace/skills
ln -sfn /Users/dcj/ai/nanobot/extensions/nanobot_ext/skills/school-portal \
  ~/.nanobot/workspace/skills/school-portal
```
