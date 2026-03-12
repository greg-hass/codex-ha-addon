# Codex CLI Add-on Docs

## Overview

The add-on runs the official Codex CLI inside a Home Assistant add-on container and exposes a small ingress UI for:

- OpenAI device-code login
- checking login status
- running `codex exec` against a mapped working directory

## Runtime layout

- Codex auth state: `/data/.codex`
- Default workspace: `/config`
- Web UI and API: port `8000`

## API summary

### `GET /health`

Returns:

```json
{
  "status": "ok",
  "logged_in": false,
  "workspace_dir": "/config",
  "codex_home": "/data/.codex"
}
```

### `GET /api/auth/status`

Runs `codex login status` inside the add-on and returns whether the CLI is authenticated.

### `POST /api/auth/login`

Starts `codex login --device-auth` and returns the login session, verification URL, and one-time code when available.

### `GET /api/auth/login/{session_id}`

Polls the in-progress device auth session.

### `POST /api/exec`

Request body:

```json
{
  "prompt": "Review my Home Assistant automations in /config",
  "cwd": "/config",
  "model": "gpt-5-codex"
}
```

The response is streamed as plain text from the Codex CLI process.

## Notes

- The add-on currently targets `amd64` and `aarch64`.
- Device auth is based on the current Codex CLI flow, which prints `https://auth.openai.com/codex/device` and a short verification code.
- The add-on is intentionally minimal and does not try to reproduce the full terminal UI inside Home Assistant.
