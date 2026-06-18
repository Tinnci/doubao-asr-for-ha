#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
OPTIONS_FILE="${OPTIONS_FILE:-${DATA_DIR}/options.json}"
WYOMING_DOUBAO_ASR_BIN="${WYOMING_DOUBAO_ASR_BIN:-/usr/src/app/.venv/bin/wyoming-doubao-asr}"
export PYTHONWARNINGS="${PYTHONWARNINGS:-ignore::SyntaxWarning}"

debug_logging="false"
response_timeout_s="15"
zeroconf_enabled="false"
zeroconf_timeout_s="5"
metrics_uri=""

if [[ -f "${OPTIONS_FILE}" ]]; then
  debug_logging="$(jq -r '.debug_logging // false' "${OPTIONS_FILE}")"
  response_timeout_s="$(jq -r '.response_timeout_s // 15' "${OPTIONS_FILE}")"
  zeroconf_enabled="$(jq -r '.zeroconf_enabled // false' "${OPTIONS_FILE}")"
  zeroconf_timeout_s="$(jq -r '.zeroconf_timeout_s // 5' "${OPTIONS_FILE}")"
  metrics_uri="$(jq -r '.metrics_uri // ""' "${OPTIONS_FILE}")"
fi

log_level="INFO"
if [[ "${debug_logging}" == "true" ]]; then
  log_level="DEBUG"
fi

args=(
  "${WYOMING_DOUBAO_ASR_BIN}"
  --uri "tcp://0.0.0.0:10300"
  --credentials-file "${DATA_DIR}/doubao_credentials.json"
  --response-timeout-s "${response_timeout_s}"
  --zeroconf-timeout-s "${zeroconf_timeout_s}"
  --log-level "${log_level}"
)

if [[ "${zeroconf_enabled}" == "true" ]]; then
  args+=(--zeroconf "doubao-asr")
fi

if [[ -n "${metrics_uri}" ]]; then
  args+=(--metrics-uri "${metrics_uri}")
fi

exec "${args[@]}"
