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

## 0.2.1

- Expanded add-on mounts to include Home Assistant config, backups, media, add-ons, SSL, share, and addon config directories
- Changed the default workspace to `/homeassistant`
- Added Home Assistant-specific terminal shortcut hints in the sidebar
- Added clickable terminal shortcuts for automations, configuration, scripts, searches, and HA logs

## 0.2.2

- Changed the default sandbox mode to `danger-full-access` for easier Home Assistant troubleshooting
- Switched the Home Assistant sidebar icon to `mdi:home-assistant`
- Updated add-on branding to use the official Codex artwork
