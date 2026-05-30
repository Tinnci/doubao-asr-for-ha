#!/usr/bin/env bash
set -euo pipefail

OPTIONS_FILE="/data/options.json"

debug_logging="$(jq -r '.debug_logging // false' "${OPTIONS_FILE}")"
response_timeout_s="$(jq -r '.response_timeout_s // 15' "${OPTIONS_FILE}")"

log_level="INFO"
if [[ "${debug_logging}" == "true" ]]; then
  log_level="DEBUG"
fi

exec /usr/src/app/.venv/bin/wyoming-doubao-asr \
  --uri "tcp://0.0.0.0:10300" \
  --credentials-file "/data/doubao_credentials.json" \
  --response-timeout-s "${response_timeout_s}" \
  --zeroconf "doubao-asr" \
  --log-level "${log_level}"
