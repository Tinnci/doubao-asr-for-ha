#!/usr/bin/env bash
set -euo pipefail

DATA_DIR="${DATA_DIR:-/data}"
OPTIONS_FILE="${OPTIONS_FILE:-${DATA_DIR}/options.json}"
WYOMING_DOUBAO_ASR_BIN="${WYOMING_DOUBAO_ASR_BIN:-/usr/src/app/.venv/bin/wyoming-doubao-asr}"

debug_logging="false"
response_timeout_s="15"

if [[ -f "${OPTIONS_FILE}" ]]; then
  debug_logging="$(jq -r '.debug_logging // false' "${OPTIONS_FILE}")"
  response_timeout_s="$(jq -r '.response_timeout_s // 15' "${OPTIONS_FILE}")"
fi

log_level="INFO"
if [[ "${debug_logging}" == "true" ]]; then
  log_level="DEBUG"
fi

exec "${WYOMING_DOUBAO_ASR_BIN}" \
  --uri "tcp://0.0.0.0:10300" \
  --credentials-file "${DATA_DIR}/doubao_credentials.json" \
  --response-timeout-s "${response_timeout_s}" \
  --zeroconf "doubao-asr" \
  --log-level "${log_level}"
