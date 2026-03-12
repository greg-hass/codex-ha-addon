# Codex CLI Add-on Docs

## Overview

The add-on runs the official Codex CLI inside a Home Assistant add-on container and exposes a PTY-backed ingress UI for:

- OpenAI device-code login
- checking login status
- running an interactive Codex terminal against a mapped working directory

## Runtime layout

- Codex auth state: `/data/.codex`
- Default workspace: `/homeassistant`
- Web UI and API: port `8000`

## Mapped directories

The add-on now exposes these Home Assistant-managed paths:

- `/homeassistant`
- `/addons`
- `/backup`
- `/share`
- `/media`
- `/ssl`
- `/all_addon_configs`

Common Home Assistant files you can work with from Codex include:

- `/homeassistant/configuration.yaml`
- `/homeassistant/automations.yaml`
- `/homeassistant/scripts.yaml`
- `/homeassistant/scenes.yaml`

## API summary

### `GET /health`

Returns:

```json
{
  "status": "ok",
  "logged_in": false,
  "workspace_dir": "/homeassistant",
  "codex_home": "/data/.codex"
}
```

### `GET /api/auth/status`

Runs `codex login status` inside the add-on and returns whether the CLI is authenticated.

### `POST /api/auth/login`

Starts `codex login --device-auth` and returns the login session, verification URL, and one-time code when available.

### `GET /api/auth/login/{session_id}`

Polls the in-progress device auth session.

### `POST /api/terminal/restart`

Restarts the PTY-backed Codex terminal process.

### `WS /ws/terminal`

WebSocket endpoint used by the browser terminal. It accepts:

- `{"type":"input","data":"..."}` for keystrokes
- `{"type":"resize","cols":120,"rows":36}` for terminal resizing

## Notes

- The add-on currently targets `amd64` and `aarch64`.
- Device auth is based on the current Codex CLI flow, which prints `https://auth.openai.com/codex/device` and a short verification code.
- The add-on uses a browser terminal to interact with the real Codex CLI process running in the container.
