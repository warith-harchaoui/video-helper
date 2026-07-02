# syntax=docker/dockerfile:1.6
#
# video-helper — reproducible container image.
#
# Two-stage build: the base stage pulls system deps (ffmpeg is
# mandatory for the whole toolkit) and installs the package with the
# [api,mcp] extras so the container can serve the HTTP + MCP surfaces
# out of the box. PyAV is included by default so the frame-extraction
# dispatcher picks the fastest backend (windowed / sparse reads).
#
# Build:
#   docker build -t video-helper .
#
# Run (HTTP + MCP on 0.0.0.0:8000):
#   docker run --rm -p 8000:8000 video-helper
#
# Run CLI one-shot:
#   docker run --rm -v $PWD:/data video-helper \
#     video-helper chunk --input /data/in.mp4 --start 10 --end 20 --output /data/cut.mp4

# --- base -------------------------------------------------------------------
FROM python:3.11-slim AS base

# System deps: ffmpeg + libass (subtitle burn-in) + tini for signal
# handling. No compilers — we install from wheels only.
RUN apt-get update && apt-get install --no-install-recommends -y \
        ffmpeg \
        libass9 \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root runtime user; the app never needs root at runtime.
RUN useradd --create-home --shell /bin/bash app
WORKDIR /app

# --- deps -------------------------------------------------------------------
# Copy the package first so pip picks up pyproject.toml before we invalidate
# the layer with source changes.
COPY --chown=app:app pyproject.toml README.md LICENSE ./
COPY --chown=app:app video_helper ./video_helper

# Install core + api + mcp + pyav (dispatcher's best backend for windowed /
# sparse reads). torch / pillow stay out of the default image — they are
# optional and drag in ~2 GB.
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir '.[api,mcp,pyav]'

# --- runtime ----------------------------------------------------------------
USER app
EXPOSE 8000
ENV PYTHONUNBUFFERED=1 \
    VIDEO_HELPER_HOST=0.0.0.0 \
    VIDEO_HELPER_PORT=8000

# tini reaps orphan children (ffmpeg subprocesses) cleanly on SIGTERM.
ENTRYPOINT ["/usr/bin/tini", "--"]
# Default: serve FastAPI + MCP. Override for one-shot CLI usage.
CMD ["video-helper-mcp"]
