---
name: school-portal
description: "登录华南农业大学信息门户 CAS，并在用户需要访问门户数据时检查登录状态。"
---

# School Portal

Use this skill only for the SCAU information portal. The current scope is login and local session status; do not claim to retrieve grades, schedules, notices, or other portal data.

## Workflow

1. Call the `portal_status` MCP tool first; in nanobot it may be named `mcp_school-portal_portal_status`. If it reports an existing session, do not log in again unless the user explicitly asks to refresh the login.
2. If no session exists, call `portal_login`; in nanobot it may be named `mcp_school-portal_portal_login`. The MCP server reads credentials from the plugin data directory (`PLUGIN_DATA/credentials.json`) or the `NANOBOT_SCHOOL_PORTAL_USERNAME` and `NANOBOT_SCHOOL_PORTAL_PASSWORD` environment variables.
3. Report only the login result, username, and optional real name. Never print or repeat passwords, cookies, JWTs, session files, or connection details.

## Credential Rules

- Never ask the user to paste a password into chat.
- If credentials are missing, tell the user to create `credentials.json` in the plugin data directory with permissions `600`, or to configure the environment variables, then retry.
- Do not attempt to bypass CAPTCHA, slider verification, two-factor authentication, or account lockout controls.
- If the tool reports CAPTCHA, slider, or two-factor verification, ask the user to complete a normal login on the official portal first.

## Security

- Treat the saved session as a secret.
- Do not read or display the session file unless the user explicitly asks for troubleshooting; even then, redact all cookie and token values.
- The portal connection is read-only for this milestone. Do not submit forms, select courses, or change account settings.
