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
