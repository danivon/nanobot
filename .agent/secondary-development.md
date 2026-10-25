# Secondary Development

This fork adds capabilities without changing the agent execution core. Read this when adding extensions, changing fork-owned code, or syncing upstream.

## Boundaries

- Keep new Python code in `extensions/<package>/` and expose it through official extension points.
- Prefer, in order: skill, MCP server or Agent Plugin, custom Tool, channel adapter, core change.
- Avoid modifying `nanobot/agent/loop.py`, `nanobot/agent/runner.py`, `nanobot/session/`, and security policy. If a core change is unavoidable, isolate it in its own commit and document why.
- Depend on public tool and channel contracts; do not import private internal helpers.

## Extension points

- Python tool: create a separate package under `extensions/`, register it through `[project.entry-points."nanobot.tools"]`, and install it editable in the active environment.
- Personal skill: place it under `~/.nanobot/workspace/skills/<name>/SKILL.md`; it needs no packaging or gateway restart.
- Distributable skill or MCP bundle: keep its source under `extensions/agent-plugins/<name>/`, install it under `<workspace>/plugins/`, and enable it from Apps.
- New channel: place it under `nanobot/channels/<name>/` following `channel-package-guide.md`; treat it as an upstream-file change and keep it in a dedicated commit.
- Keep one active copy of each skill. Workspace skills override plugin skills, which override built-in skills.

## Environment and data

- Runtime configuration and data stay in `~/.nanobot`; never commit them or their secrets.
- Install Python dependencies with `uv sync --all-extras --dev`, followed by `uv run --no-sync python -m scripts.install_channel_dependencies --all-channels`.
- After `uv sync`, use `uv sync --inexact` to preserve editable extension packages, or declare the extension as an optional dependency in `pyproject.toml`.
- Build the WebUI with `cd webui && bun install --frozen-lockfile && bun run build`.

## Upstream sync

- `origin` is the fork and `upstream` is `HKUDS/nanobot`.
- Rebase `dev` onto `upstream/main` at stable points, such as weekly or before a release or major feature; do not rebase for every upstream commit.
- Create a backup branch before rebasing, keep `rerere` enabled, and push with `--force-with-lease`.
- Keep upstream-sync commits separate from feature commits and avoid reformatting upstream files.

## Verification

- Keep extension tests with the extension.
- Add an integration test when a tool or channel contract changes.
- Run `python -m scripts.check_import_boundaries` and the relevant tests after changes.
