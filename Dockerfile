FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app

# The lock must come from PyPI. A lock made in the offline box points at /opt/wheels and cannot build here.
RUN --mount=type=bind,source=uv.lock,target=/tmp/uv.lock ! grep -q /opt/wheels /tmp/uv.lock \
    || { echo "uv.lock verwijst naar /opt/wheels: draai 'uv lock' op de Mac en commit het resultaat" >&2; exit 1; }

# Dependencies first, so a change in the code or the saints reuses this layer.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY data ./data
RUN uv sync --frozen --no-dev

# The game state lives on a mounted volume at /db; the saints and questions are baked into the image.
ENV PATH="/app/.venv/bin:$PATH" DURFHEILIG_DATA=/app/data DURFHEILIG_DB=/db/spel.db APP_PORT=8080
RUN useradd --system --uid 10001 app && mkdir /db && chown app /db
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import os,urllib.request as u; u.urlopen(f'http://127.0.0.1:{os.environ[\"APP_PORT\"]}/health', timeout=4)"

CMD ["python", "-m", "durfheilig.app"]
