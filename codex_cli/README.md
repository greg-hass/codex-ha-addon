# Codex CLI Home Assistant Add-on

This project turns Home Assistant into a thin wrapper around the real [Codex CLI](https://github.com/openai/codex). The add-on exposes an ingress terminal UI that lets you:

- sign in with OpenAI device-code OAuth
- persist the resulting Codex session in `/data/.codex`
- run the interactive Codex terminal against `/homeassistant` and other mapped Home Assistant directories

## What it does

The add-on does not proxy the OpenAI API directly. Instead, it installs the official Codex CLI in the container and manages these flows for you:

1. `codex login --device-auth`
2. store auth state under the add-on data directory
3. run `codex` in a PTY-backed browser terminal

That means the login flow matches the current Codex CLI experience: open `https://auth.openai.com/codex/device`, enter the short code, and the add-on becomes authenticated once the CLI finishes the device flow.

## Configuration

```yaml
workspace_dir: /homeassistant
model: ""
sandbox_mode: workspace-write
approval_policy: never
enable_web_search: false
log_level: info
```

Notes:

- Leave `model` blank to use Codex CLI defaults.
- `workspace_dir` should point at a mapped directory such as `/homeassistant`, `/addons`, `/backup`, `/share`, `/media`, `/ssl`, or `/all_addon_configs`.
- `danger-full-access` is available, but it should be used carefully.

The add-on now mounts these Home Assistant-managed paths inside the container:

- `/homeassistant`
- `/addons`
- `/backup`
- `/share`
- `/media`
- `/ssl`
- `/all_addon_configs`

That includes common Home Assistant files such as:

- `/homeassistant/configuration.yaml`
- `/homeassistant/automations.yaml`
- `/homeassistant/scripts.yaml`
- `/homeassistant/scenes.yaml`

## Installation

1. Publish this repository or place it in a directory Home Assistant can use as an add-on repository.
2. Install the `Codex CLI` add-on from the Home Assistant add-on store.
3. Start the add-on.
4. Open the add-on panel from the sidebar.
5. Click `Connect with OpenAI`.
6. Complete the device-code login in your browser.

## API

The ingress UI uses these endpoints:

- `GET /health`
- `GET /api/auth/status`
- `POST /api/auth/login`
- `GET /api/auth/login/{session_id}`
- `POST /api/terminal/restart`
- `WS /ws/terminal`

## Important limitations

- This add-on currently targets `amd64` and `aarch64` only, because those are the Codex CLI Linux architectures available in the npm package metadata.
- The UI is terminal-focused and intentionally lightweight, but it is still a browser wrapper around the CLI rather than a native SSH shell.
- The add-on does not install a Home Assistant integration or services yet. It is an ingress-based add-on first.
