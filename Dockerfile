ARG BUILD_FROM
FROM ghcr.io/astral-sh/uv:0.9.26 AS uv

FROM ${BUILD_FROM}

ENV UV_PROJECT_ENVIRONMENT=/usr/src/app/.venv
ENV PATH="/usr/src/app/.venv/bin:${PATH}"

RUN \
    apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        jq \
        libopus0 \
        netcat-traditional \
        python3 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

WORKDIR /usr/src/app
COPY pyproject.toml uv.lock README.md ./
COPY wyoming_doubao_asr ./wyoming_doubao_asr
RUN uv sync --frozen --no-dev

WORKDIR /
COPY rootfs /
RUN chmod +x /run.sh

HEALTHCHECK --start-period=30s \
    CMD echo '{ "type": "describe" }' \
    | nc -w 1 localhost 10300 \
    | grep -q "doubao-asr" \
    || exit 1

CMD ["/run.sh"]
