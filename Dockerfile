# Strands-based agent image.
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

COPY testagent/ testagent/
COPY pyproject.toml pyproject.toml
COPY README.md README.md
COPY .python-version .python-version
COPY uv.lock uv.lock

RUN uv sync --frozen

ENV OTEL_SERVICE_NAME=testagent

CMD ["uv", "run", "testagent", "--local"]
