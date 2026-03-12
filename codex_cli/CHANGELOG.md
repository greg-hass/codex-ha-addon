# Changelog

## 0.1.0

- Reworked the project into a Codex CLI Home Assistant add-on
- Added OpenAI device-code login support via `codex login --device-auth`
- Added a lightweight ingress UI for auth status and prompt execution
- Switched the container build to install the official Codex CLI

## 0.2.0

- Replaced the one-shot prompt form with a PTY-backed browser terminal
- Added WebSocket terminal bridging for an interactive Codex session
- Added restart support for the interactive terminal session
