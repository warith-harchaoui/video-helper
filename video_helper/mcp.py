"""Video Helper: Model Context Protocol (MCP) surface.

A thin adapter that exposes the FastAPI app from :mod:`video_helper.api` as
MCP tools, so any MCP-aware host (an agent runtime, an IDE integration, a
custom shell) can call video-helper's operations — validation, dimensions,
duration, format conversion, chunking, black-video/image-loop generation,
concat, overlay, audio mux/extraction, subtitle burn/conversion, and frame
extraction — as first-class tools. Uses `fastapi-mcp`
(https://github.com/tadata-org/fastapi_mcp): one wrapper publishes the whole
existing HTTP surface, so the routes are never duplicated.

Install the extra to pull in ``fastapi-mcp``::

    pip install "video-helper[mcp]"

Then run the server (HTTP API + MCP endpoint at ``/mcp``)::

    video-helper-mcp                 # console entry point
    python -m video_helper.mcp       # equivalent

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

try:
    from fastapi_mcp import FastApiMCP
except ImportError as exc:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        'The MCP surface needs the [mcp] extra: pip install "video-helper[mcp]"'
    ) from exc

# Reuse the exact same FastAPI app: MCP is a thin wrapper on top, no new routes.
from video_helper.api import app

# Publish the HTTP endpoints (validate / dimensions / duration / convert /
# chunk / black / image-loop / concat / overlay / extract-audio / mux-audio /
# burn-subs / srt2vtt / extract-frames) as MCP tools.
mcp = FastApiMCP(
    app,
    name="video-helper",
    description=(
        "Video Helper MCP tools: validate, inspect (dimensions/duration), "
        "convert, chunk, and compose video — black-video/image-loop "
        "generation, concat, overlay, audio mux/extraction, subtitle "
        "burn/conversion, and frame extraction — entirely on the local "
        "machine."
    ),
)
# Newer fastapi-mcp splits mount() into transport-specific mount_http(); fall back to
# the legacy mount() so a range of fastapi-mcp versions keeps working.
if hasattr(mcp, "mount_http"):
    mcp.mount_http()
else:  # pragma: no cover - legacy fastapi-mcp
    mcp.mount()


def main() -> None:
    """Console entry point (``video-helper-mcp``): serve the API + MCP endpoint.

    Boots the FastAPI app (now serving both the plain HTTP routes and the
    ``/mcp`` MCP endpoint) with uvicorn in a single worker. Local-first: binds
    to loopback by default (override with ``VIDEO_HELPER_HOST`` /
    ``VIDEO_HELPER_PORT``).
    """
    import os

    import uvicorn

    host = os.environ.get("VIDEO_HELPER_HOST", "127.0.0.1")
    port = int(os.environ.get("VIDEO_HELPER_PORT", "8000"))
    print(f"Video Helper API + MCP -> http://{host}:{port}  (MCP at /mcp)")
    uvicorn.run(app, host=host, port=port, workers=1)


if __name__ == "__main__":  # pragma: no cover
    main()
