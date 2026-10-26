# One image: the built single-page app, the API, and the embedding model.
#
# Everything the app needs is baked in -- Python deps, the 90 MB ONNX embedder,
# the regulation corpus and the compiled frontend -- so the running container
# downloads nothing and the host needs no Python, no Node and no psql. Docker
# and Make are the only requirements.

# -------------------------------------------------------------------- web ----
FROM node:20-slim AS web

WORKDIR /web
COPY web/package.json ./
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

# ---------------------------------------------------------------- builder ----
FROM python:3.12-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/opt/venv/bin:$PATH"

RUN python -m venv /opt/venv

WORKDIR /build
COPY api/pyproject.toml ./
COPY api/app ./app
RUN pip install ".[test]"

# ------------------------------------------------------------------ model ----
# Baked at build time, so the running container needs no model download. That
# matters for cold-start latency and for privacy: a container that cannot reach
# a model host cannot leak the corpus to one.
FROM builder AS model

ENV FASTEMBED_CACHE_PATH=/opt/models
RUN mkdir -p /opt/models \
 && python -c "\
from fastembed import TextEmbedding; \
TextEmbedding(model_name='BAAI/bge-small-en-v1.5', cache_dir='/opt/models'); \
print('baked BAAI/bge-small-en-v1.5')"

# ---------------------------------------------------------------- runtime ----
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    FASTEMBED_CACHE_PATH=/opt/models \
    HF_HUB_OFFLINE=1 \
    HOME=/home/app \
    DATA_DIR=/srv/data

# Non-root, with a real home so no library tries to write to /.
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --home-dir /home/app --create-home app

COPY --from=builder /opt/venv /opt/venv
COPY --from=model --chown=app:app /opt/models /opt/models

WORKDIR /srv
COPY --chown=app:app api/schema.sql ./
COPY --chown=app:app api/app ./app
COPY --chown=app:app api/scripts ./scripts
COPY --chown=app:app data ./data
COPY --from=web --chown=app:app /web/dist ./static
RUN mkdir -p /srv/outputs && chown app:app /srv/outputs

USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ------------------------------------------------------------------- test ----
# Same resolved dependencies as runtime, plus the test tree, so a local run and
# the image under demo cannot drift. The hash embedder keeps tests offline.
FROM runtime AS test

USER root
COPY --chown=app:app api/pyproject.toml ./
COPY --chown=app:app api/tests ./tests
RUN chown -R app:app /srv
USER app

ENV EMBED_BACKEND=hash
CMD ["pytest"]
