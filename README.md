# Codex CLI Home Assistant Repository

This repository contains a Home Assistant add-on that runs the official Codex CLI and supports OpenAI device-code login.

## Repository layout

- [`repository.json`](/Users/greg/codex-ha-addon/repository.json): Home Assistant add-on repository metadata
- [`codex_cli`](/Users/greg/codex-ha-addon/codex_cli): the add-on itself

## Add to Home Assistant

1. Open Home Assistant.
2. Go to `Settings -> Add-ons -> Add-on Store`.
3. Open the overflow menu and choose `Repositories`.
4. Add this repository URL.
5. Install `Codex CLI` from the store.

## Local development

The add-on files live in [`codex_cli/config.yaml`](/Users/greg/codex-ha-addon/codex_cli/config.yaml) and the FastAPI service lives in [`codex_cli/app/main.py`](/Users/greg/codex-ha-addon/codex_cli/app/main.py).
