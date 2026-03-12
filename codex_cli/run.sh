#!/usr/bin/with-contenv bashio

set -e

OPTIONS_FILE="/data/options.json"

read_option() {
    local key="$1"
    local default_value="$2"

    if [ -f "${OPTIONS_FILE}" ]; then
        local value
        value="$(jq -er --arg key "${key}" '.[$key]' "${OPTIONS_FILE}" 2>/dev/null || true)"
        if [ -n "${value}" ] && [ "${value}" != "null" ]; then
            printf '%s' "${value}"
            return 0
        fi
    fi

    printf '%s' "${default_value}"
}

export CODEX_ADDON_PORT="8000"
export CODEX_ADDON_LOG_LEVEL="$(read_option 'log_level' 'info')"
export CODEX_ADDON_WORKSPACE_DIR="$(read_option 'workspace_dir' '/config')"
export CODEX_ADDON_MODEL="$(read_option 'model' '')"
export CODEX_ADDON_SANDBOX_MODE="$(read_option 'sandbox_mode' 'workspace-write')"
export CODEX_ADDON_APPROVAL_POLICY="$(read_option 'approval_policy' 'never')"
export CODEX_ADDON_ENABLE_WEB_SEARCH="$(read_option 'enable_web_search' 'false')"
export CODEX_ADDON_CODEX_HOME="/data/.codex"

mkdir -p "${CODEX_ADDON_CODEX_HOME}"

bashio::log.info "Starting Codex CLI add-on"
bashio::log.info "Workspace: ${CODEX_ADDON_WORKSPACE_DIR}"
bashio::log.info "Sandbox: ${CODEX_ADDON_SANDBOX_MODE}"

cd /app
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${CODEX_ADDON_PORT}" \
    --log-level "${CODEX_ADDON_LOG_LEVEL}" \
    --access-log
