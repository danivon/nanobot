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

## School Portal Agent Plugin

The school portal integration is an independent stdio MCP server packaged with its Skill as an Agent Plugin. It provides `portal_status` and `portal_login`; the login tool reads credentials from `PLUGIN_DATA/credentials.json` or environment variables and never accepts a password as a tool argument.

The installable plugin source is at `extensions/agent-plugins/school-portal`. Install the Python package first so `nanobot-school-portal-mcp` is on `PATH`, then copy the plugin directory:

```bash
uv sync --all-extras --dev
mkdir -p ~/.nanobot/workspace/plugins
cp -R extensions/agent-plugins/school-portal \
  ~/.nanobot/workspace/plugins/school-portal
```

Open WebUI **Apps**, review the plugin, and enable it. Creating the directory alone does not activate it.

After activation, the MCP server runs with `PLUGIN_DATA` as its state directory. Put `credentials.json` there with permissions `600`; `session.json` is written there with permissions `600`. Do not put credentials or runtime data inside the installed plugin directory. The plugin package is immutable after activation, and changing packaged files disables it until it is reviewed again.

The plugin's `mcp.json` declares the server; no manual `tools.mcpServers` entry is needed. The Skill is bundled in `skills/school-portal/SKILL.md` and is loaded after the plugin is enabled.
