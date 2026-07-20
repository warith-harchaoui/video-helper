"""
Smoke tests for the FastAPI HTTP surface.

Only exercises endpoints that do not require ffmpeg or the network
(``/health``, plus OpenAPI schema introspection to catch endpoint-name
drift). Heavier round-trip tests belong to an integration suite where
a real ffmpeg is available.

Usage Example
-------------
>>> #   pytest tests/test_api.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

# FastAPI is in the ``[api]`` optional extra — skip cleanly otherwise.
fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Yield a TestClient bound to the video-helper FastAPI app."""
    from video_helper.api import app

    with TestClient(app) as c:
        yield c


def test_health_returns_ok(client) -> None:
    """``/health`` should return 200 + ``{"status": "ok"}``."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_openapi_lists_expected_endpoints(client) -> None:
    """The OpenAPI spec should list every expected route path."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    paths = r.json()["paths"]
    expected = {
        "/health",
        "/gui",
        "/validate",
        "/dimensions",
        "/duration",
        "/convert",
        "/chunk",
        "/black",
        "/image-loop",
        "/concat",
        "/overlay",
        "/extract-audio",
        "/mux-audio",
        "/burn-subs",
        "/srt2vtt",
        "/extract-frames",
    }
    assert expected.issubset(set(paths.keys()))


def test_docs_endpoint_is_served(client) -> None:
    """``/docs`` should serve the Swagger UI landing HTML."""
    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower() or "openapi" in r.text.lower()


def test_gui_returns_200_html(client) -> None:
    """``GET /gui`` should return 200 with a self-contained HTML page."""
    r = client.get("/gui")
    assert r.status_code == 200
    # It must be an HTML document (correct content type + a doctype).
    assert r.headers["content-type"].startswith("text/html")
    body = r.text.lower()
    assert "<!doctype html>" in body
    # Sanity-check it is the video bench and offers the real operations
    # (the JS builds endpoint URLs from these op names, so assert on them).
    assert "video bench" in body
    assert 'value="convert"' in r.text and 'value="extract-frames"' in r.text


def test_root_redirects_to_gui(client) -> None:
    """``GET /`` should redirect (or resolve) to the GUI page."""
    # follow_redirects defaults True in the TestClient; assert we land on HTML.
    r = client.get("/")
    assert r.status_code == 200
    assert "video bench" in r.text.lower()
