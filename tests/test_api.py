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
        "/compress",
        "/image-loop",
        "/concat",
        "/overlay",
        "/extract-audio",
        "/mux-audio",
        "/burn-subs",
        "/srt2vtt",
        "/extract-frames",
        "/extract-flow",
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
    assert 'value="compress"' in r.text
    assert 'value="extract-flow"' in r.text
    assert 'id="flow_method"' in r.text and 'id="flow_output_format"' in r.text


def test_root_redirects_to_gui(client) -> None:
    """``GET /`` should redirect (or resolve) to the GUI page."""
    # follow_redirects defaults True in the TestClient; assert we land on HTML.
    r = client.get("/")
    assert r.status_code == 200
    assert "video bench" in r.text.lower()


def test_extract_frames_route_exposes_pad_color_params(client) -> None:
    """``/extract-frames`` request-body schema lists the pad_color CLI-parity fields."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    body_schema_ref = schema["paths"]["/extract-frames"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"]["$ref"]
    body_schema_name = body_schema_ref.rsplit("/", 1)[-1]
    props = schema["components"]["schemas"][body_schema_name]["properties"]
    assert "output_width" in props
    assert "output_height" in props
    assert "pad_color" in props
    assert props["pad_color"]["default"] == "black"


def test_compress_route_exposes_expected_params(client) -> None:
    """``/compress`` request-body schema matches compress_video()'s defaults."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    body_schema_ref = schema["paths"]["/compress"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"]["$ref"]
    body_schema_name = body_schema_ref.rsplit("/", 1)[-1]
    props = schema["components"]["schemas"][body_schema_name]["properties"]
    assert props["target_size_mb"]["default"] == 97.0
    assert props["audio_bitrate"]["default"] == "128k"
    assert props["vcodec"]["default"] == "libx265"
    assert props["min_video_bitrate_kbps"]["default"] == 200


def test_compress_route_rejects_bad_vcodec(client) -> None:
    """An unsupported ``vcodec`` should 400, not a raw 500 traceback from ffmpeg."""
    r = client.post(
        "/compress",
        files={"file": ("t.mp4", b"not-a-real-video", "video/mp4")},
        data={"vcodec": "bogus"},
    )
    assert r.status_code == 400


def test_extract_flow_route_exposes_expected_params(client) -> None:
    """``/extract-flow`` request-body schema matches extract_optical_flow()'s defaults."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()
    body_schema_ref = schema["paths"]["/extract-flow"]["post"]["requestBody"]["content"][
        "multipart/form-data"
    ]["schema"]["$ref"]
    body_schema_name = body_schema_ref.rsplit("/", 1)[-1]
    props = schema["components"]["schemas"][body_schema_name]["properties"]
    assert props["output_format"]["default"] == "video"
    assert props["method"]["default"] == "dis"
    assert props["dis_preset"]["default"] == "fast"
    assert props["raft_variant"]["default"] == "small"
    assert props["device"]["default"] == "cpu"
    assert props["frame_step"]["default"] == 1
    assert "output_width" in props
    assert "output_height" in props
    assert props["wavelet"]["default"] == "db2"


def test_extract_flow_route_rejects_bad_output_format(client) -> None:
    """An unsupported ``output_format`` should 400, not a raw 500 traceback."""
    r = client.post(
        "/extract-flow",
        files={"file": ("t.mp4", b"not-a-real-video", "video/mp4")},
        data={"output_format": "bogus"},
    )
    assert r.status_code == 400


def test_extract_flow_route_rejects_bad_method(client) -> None:
    """An unsupported ``method`` should 400 with a clean message, not an opaque 502."""
    r = client.post(
        "/extract-flow",
        files={"file": ("t.mp4", b"not-a-real-video", "video/mp4")},
        data={"method": "bogus"},
    )
    assert r.status_code == 400


def test_extract_flow_route_rejects_bad_dis_preset(client) -> None:
    """An unsupported ``dis_preset`` should 400 with a clean message."""
    r = client.post(
        "/extract-flow",
        files={"file": ("t.mp4", b"not-a-real-video", "video/mp4")},
        data={"dis_preset": "bogus"},
    )
    assert r.status_code == 400


def test_extract_flow_route_rejects_bad_raft_variant(client) -> None:
    """An unsupported ``raft_variant`` should 400 with a clean message."""
    r = client.post(
        "/extract-flow",
        files={"file": ("t.mp4", b"not-a-real-video", "video/mp4")},
        data={"raft_variant": "bogus"},
    )
    assert r.status_code == 400


def test_status_for_classifies_client_vs_upstream_errors() -> None:
    """``AssertionError``/``ValueError`` -> 400 (bad input); anything else -> 502."""
    from video_helper.api import _status_for

    assert _status_for(AssertionError("bad input")) == 400
    assert _status_for(ValueError("bad input")) == 400
    assert _status_for(RuntimeError("ffmpeg failed")) == 502
    assert _status_for(ImportError("optional extra missing")) == 502


def test_cleanup_on_error_removes_tmp_only_on_failure(tmp_path) -> None:
    """The failure path deletes ``tmp``; the success path leaves it alone.

    Every action route relies on this: ``background.add_task(_cleanup, tmp)``
    only runs after a successful response, so a failure inside the
    ``with _cleanup_on_error(tmp):`` block must be the thing that reclaims
    the temp dir — otherwise every failed request leaks it forever.
    """
    from video_helper.api import _cleanup_on_error

    failing_dir = tmp_path / "failing"
    failing_dir.mkdir()
    with pytest.raises(ValueError), _cleanup_on_error(failing_dir):
        raise ValueError("boom")
    assert not failing_dir.exists()

    success_dir = tmp_path / "success"
    success_dir.mkdir()
    with _cleanup_on_error(success_dir):
        pass
    assert success_dir.exists()  # untouched — the caller's own background task owns this


def test_convert_route_cleans_up_temp_dir_on_failure(client, tmp_path, monkeypatch) -> None:
    """A full HTTP round trip: a failing ``/convert`` must not leak its temp dir.

    Deterministic and ffmpeg-independent: patches ``_new_tmpdir`` to return a
    directory under ``tmp_path`` (so the test can inspect it) and
    ``video_converter`` to always raise, exactly like a real ffmpeg/input
    failure would.
    """
    import video_helper.api as api_module

    leaked_dir = tmp_path / "video-helper-leak-check"
    leaked_dir.mkdir()
    monkeypatch.setattr(api_module, "_new_tmpdir", lambda: leaked_dir)

    def _boom(*args, **kwargs):
        raise AssertionError("Input video file not okay")

    monkeypatch.setattr(api_module, "video_converter", _boom)

    r = client.post(
        "/convert",
        files={"file": ("t.mp4", b"not-a-real-video", "video/mp4")},
    )
    assert r.status_code == 400
    assert not leaked_dir.exists()
