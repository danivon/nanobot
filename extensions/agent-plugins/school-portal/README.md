# SCAU School Portal Agent Plugin

This Agent Plugin bundles the `school-portal` Skill and the MCP server declaration for SCAU CAS login.

## Prerequisites

From the repository root, install the Python extension package so that `nanobot-school-portal-mcp` is available:

```bash
uv sync --all-extras --dev
uv run --no-sync python -m scripts.install_channel_dependencies --all-channels
```

The plugin does not package Python dependencies or user credentials. The MCP server command must be available on the gateway's `PATH`; the extension extra provides that console script.

## Install And Enable

Copy this directory to the nanobot workspace plugin directory:

```bash
mkdir -p ~/.nanobot/workspace/plugins
cp -R extensions/agent-plugins/school-portal ~/.nanobot/workspace/plugins/school-portal
```

Open the WebUI **Apps** page, review the plugin, and enable it. Creating the directory alone does not activate the plugin.

The plugin is treated as immutable after activation. Put credentials, sessions, logs, and other runtime state in `PLUGIN_DATA`, not in the installed plugin directory. Changing packaged files disables the plugin until it is reviewed and enabled again.

## Credentials

After enabling the plugin, call `portal_status`. If credentials are missing, the error reports the exact path under `PLUGIN_DATA`. Create that `credentials.json` with this shape:

```json
{
  "username": "your-student-id",
  "password": "your-password"
}
```

Set permissions:

```bash
chmod 700 "$PLUGIN_DATA"
chmod 600 "$PLUGIN_DATA/credentials.json"
```

Alternatively, configure `NANOBOT_SCHOOL_PORTAL_USERNAME` and `NANOBOT_SCHOOL_PORTAL_PASSWORD` in the gateway environment. Never put credentials in `plugin.json`, `mcp.json`, or the repository.

The saved session is written to `PLUGIN_DATA/session.json` with permissions `600`. It contains cookies and tokens and must not be committed or shared.

## Usage

After enabling the plugin, use the Skill from a new conversation:

```text
使用 school-portal 检查信息门户登录状态
```

The agent should call the MCP tools `portal_status` and `portal_login`. The wrapped names may be `mcp_school-portal_portal_status` and `mcp_school-portal_portal_login`.
