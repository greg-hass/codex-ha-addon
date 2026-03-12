#!/usr/bin/env bash

set -euo pipefail

IMAGE_NAME="codex-ha-addon"
VERSION="${1:-0.1.0}"

echo "Building Codex CLI add-on image ${IMAGE_NAME}:${VERSION}"
docker build -t "${IMAGE_NAME}:${VERSION}" .
