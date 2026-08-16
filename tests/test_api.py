"""
Functional tests for the FastAPI HTTP surface.

Covers the metadata/schema routes without ffmpeg, plus real end-to-end
round trips through the action routes (upload -> real ffmpeg work -> a
valid response body) when ffmpeg is on PATH -- the previous version of this
file only exercised error/validation paths and left every route's success
body untested over HTTP, which was most of ``api.py``'s missed coverage.

Usage Example
-------------
>>> #   pytest tests/test_api.py

Author
------
Warith Harchaoui, Ph.D. -- https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import io
import shutil
import subprocess
import zipfile
from collections.abc import Iterator
from pathlib import Path

import cv2
import numpy as np
import pytest

# FastAPI is in the ``[api]`` optional extra -- skip cleanly otherwise.
fastapi = pytest.importorskip("fastapi")
httpx = pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from video_helper import black_video, is_valid_video_file, video_dimensions  # noqa: E402


@pytest.fixture(scope="module")
def client() -> Iterator[TestClient]:
    """Yield a TestClient bound to the video-helper FastAPI app."""
    from video_helper.api import app

    with TestClient(app) as c:
        yield c


# ---------------------------------------------------------------------------
# Metadata / schema routes -- no ffmpeg needed.
# ---------------------------------------------------------------------------


def test_health_and_docs_routes(client) -> None:
    """``/health`` returns 200 + a status payload; ``/docs`` serves Swagger UI."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

    r = client.get("/docs")
    assert r.status_code == 200
    assert "swagger" in r.text.lower() or "openapi" in r.text.lower()


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


def test_gui_and_root_routes_serve_html(client) -> None:
    """``/gui`` and ``/`` both serve the self-contained video-bench HTML page,
    including the operation options and field ids the page's JS depends on."""
    r = client.get("/gui")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    body = r.text.lower()
    assert "<!doctype html>" in body
    assert "video bench" in body
    assert 'value="convert"' in r.text and 'value="extract-frames"' in r.text
    assert 'value="compress"' in r.text and 'value="extract-flow"' in r.text
    assert 'id="flow_method"' in r.text and 'id="flow_output_format"' in r.text

    root = client.get("/")  # TestClient follows redirects by default
    assert root.status_code == 200
    assert "video bench" in root.text.lower()


def test_route_schemas_expose_expected_param_defaults(client) -> None:
    """The request-body schemas for extract-frames/compress/extract-flow list
    the CLI-parity fields with the same defaults as their library functions."""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    schema = r.json()

    def _props(path: str) -> dict:
        ref = schema["paths"][path]["post"]["requestBody"]["content"]["multipart/form-data"][
            "schema"
        ]["$ref"]
        return schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]["properties"]

    frames_props = _props("/extract-frames")
    assert "output_width" in frames_props and "output_height" in frames_props
    assert frames_props["pad_color"]["default"] == "black"

    compress_props = _props("/compress")
    assert compress_props["target_size_mb"]["default"] == 97.0
    assert compress_props["audio_bitrate"]["default"] == "128k"
    assert compress_props["vcodec"]["default"] == "libx265"
    assert compress_props["min_video_bitrate_kbps"]["default"] == 200

    flow_props = _props("/extract-flow")
    assert flow_props["output_format"]["default"] == "video"
    assert flow_props["method"]["default"] == "dis"
    assert flow_props["dis_preset"]["default"] == "fast"
    assert flow_props["raft_variant"]["default"] == "small"
    assert flow_props["device"]["default"] == "cpu"
    assert flow_props["frame_step"]["default"] == 1
    assert "output_width" in flow_props and "output_height" in flow_props
    assert flow_props["wavelet"]["default"] == "db2"


def test_action_routes_reject_bad_choice_params_with_400(client) -> None:
    """Every choice-constrained action-route parameter rejects an invalid
    value with a clean 400, never a raw 500/502 traceback -- covers
    /compress's vcodec and /extract-flow's method/output_format/
    dis_preset/raft_variant."""
    garbage = {"file": ("t.mp4", b"not-a-real-video", "video/mp4")}
    cases = [
        ("/compress", {"vcodec": "bogus"}),
        ("/extract-flow", {"output_format": "bogus"}),
        ("/extract-flow", {"method": "bogus"}),
        ("/extract-flow", {"dis_preset": "bogus"}),
        ("/extract-flow", {"raft_variant": "bogus"}),
    ]
    for path, data in cases:
        r = client.post(path, files=garbage, data=data)
        assert r.status_code == 400, f"{path} {data}"


def test_status_for_and_cleanup_on_error_classify_and_reclaim(tmp_path) -> None:
    """``_status_for`` classifies client-input errors (400) vs. upstream/
    unexpected ones (502); ``_cleanup_on_error`` reclaims the temp dir only
    when the wrapped block raises -- every action route depends on both."""
    from video_helper.api import _cleanup_on_error, _status_for

    assert _status_for(AssertionError("bad input")) == 400
    assert _status_for(ValueError("bad input")) == 400
    assert _status_for(RuntimeError("ffmpeg failed")) == 502
    assert _status_for(ImportError("optional extra missing")) == 502

    failing_dir = tmp_path / "failing"
    failing_dir.mkdir()
    with pytest.raises(ValueError), _cleanup_on_error(failing_dir):
        raise ValueError("boom")
    assert not failing_dir.exists()

    success_dir = tmp_path / "success"
    success_dir.mkdir()
    with _cleanup_on_error(success_dir):
        pass
    assert success_dir.exists()  # untouched -- the caller's own background task owns this


def test_convert_route_cleans_up_temp_dir_on_failure(client, tmp_path, monkeypatch) -> None:
    """A full HTTP round trip: a failing ``/convert`` must not leak its temp
    dir. Deterministic and ffmpeg-independent: patches ``_new_tmpdir`` to
    return a directory under ``tmp_path`` and ``video_converter`` to always
    raise, exactly like a real ffmpeg/input failure would."""
    import video_helper.api as api_module

    leaked_dir = tmp_path / "video-helper-leak-check"
    leaked_dir.mkdir()
    monkeypatch.setattr(api_module, "_new_tmpdir", lambda: leaked_dir)

    def _boom(*args, **kwargs):
        raise AssertionError("Input video file not okay")

    monkeypatch.setattr(api_module, "video_converter", _boom)

    r = client.post("/convert", files={"file": ("t.mp4", b"not-a-real-video", "video/mp4")})
    assert r.status_code == 400
    assert not leaked_dir.exists()


# ---------------------------------------------------------------------------
# Real end-to-end round trips: upload -> real ffmpeg work -> valid output.
# ---------------------------------------------------------------------------

if shutil.which("ffmpeg") is None:
    _ffmpeg_reason = "ffmpeg is required for the API round-trip tests"
else:
    _ffmpeg_reason = ""


def _write_png(path: Path, color=(0, 0, 255), size=(32, 32)) -> Path:
    """Write a uniformly-colored PNG (BGR) and return its path."""
    img = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return path


def _write_silent_wav(path: Path, duration: float = 1.0, sample_rate: int = 16000) -> Path:
    """Generate a silent WAV via ffmpeg's anullsrc filter."""
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r={sample_rate}:cl=mono",
            "-t",
            str(duration),
            str(path),
        ],
        check=True,
    )
    return path


@pytest.mark.skipif(bool(_ffmpeg_reason), reason=_ffmpeg_reason)
def test_black_and_read_routes_round_trip(client, tmp_path) -> None:
    """``/black`` synthesizes a clip from parameters alone; the resulting
    bytes then round-trip through the three read routes (/validate,
    /dimensions, /duration) with real, correct values."""
    r = client.post(
        "/black",
        data={"duration": "1.0", "width": "64", "height": "48", "frame_rate": "15"},
    )
    assert r.status_code == 200
    clip_bytes = r.content
    clip_path = tmp_path / "black.mp4"
    clip_path.write_bytes(clip_bytes)
    assert is_valid_video_file(str(clip_path))

    files = {"file": ("black.mp4", clip_bytes, "video/mp4")}
    assert client.post("/validate", files=files).json() == {"valid": True}

    dims = client.post("/dimensions", files=files).json()
    assert (dims["width"], dims["height"]) == (64, 48)
    assert dims["has_sound"] is False

    dur = client.post("/duration", files=files).json()
    assert abs(dur["duration_seconds"] - 1.0) < 0.2


@pytest.mark.skipif(bool(_ffmpeg_reason), reason=_ffmpeg_reason)
def test_convert_chunk_and_compress_routes_round_trip(client, tmp_path) -> None:
    """``/convert`` (resize + fps + strip audio), ``/chunk`` (temporal
    slice), and ``/compress`` (vcodec='copy' remux, kept fast) each return a
    real, valid video reflecting the requested transform."""
    src = tmp_path / "src.mp4"
    black_video(2.0, 128, 96, str(src), frame_rate=30)
    upload = {"file": ("src.mp4", src.read_bytes(), "video/mp4")}

    r = client.post(
        "/convert",
        files=upload,
        data={"frame_rate": "15", "width": "64", "height": "48", "without_sound": "true"},
    )
    assert r.status_code == 200
    converted = tmp_path / "converted.mp4"
    converted.write_bytes(r.content)
    d = video_dimensions(str(converted))
    assert (d["width"], d["height"]) == (64, 48)
    assert round(d["frame_rate"]) == 15

    r = client.post("/chunk", files=upload, data={"start": "0.0", "end": "1.0"})
    assert r.status_code == 200
    chunk_path = tmp_path / "chunk.mp4"
    chunk_path.write_bytes(r.content)
    assert is_valid_video_file(str(chunk_path))
    assert video_dimensions(str(chunk_path))["duration"] < 2.0

    r = client.post("/compress", files=upload, data={"vcodec": "copy"})
    assert r.status_code == 200
    compressed = tmp_path / "compressed.mp4"
    compressed.write_bytes(r.content)
    assert is_valid_video_file(str(compressed))


@pytest.mark.skipif(bool(_ffmpeg_reason), reason=_ffmpeg_reason)
def test_concat_overlay_and_mux_audio_routes_round_trip(client, tmp_path) -> None:
    """The multi-upload routes -- ``/concat`` (2+ videos), ``/overlay``
    (video + image), ``/mux-audio`` (video + audio) -- each spool their
    extra upload(s) under a distinct name (not clobbering the primary
    upload) and produce a valid result."""
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    black_video(1.0, 64, 64, str(a), frame_rate=15)
    black_video(1.0, 64, 64, str(b), frame_rate=15)

    r = client.post(
        "/concat",
        files=[
            ("files", ("a.mp4", a.read_bytes(), "video/mp4")),
            ("files", ("b.mp4", b.read_bytes(), "video/mp4")),
        ],
        data={"reencode": "true", "frame_rate": "15"},
    )
    assert r.status_code == 200
    concatenated = tmp_path / "concat.mp4"
    concatenated.write_bytes(r.content)
    assert abs(video_dimensions(str(concatenated))["duration"] - 2.0) < 0.3

    png = _write_png(tmp_path / "overlay.png")
    r = client.post(
        "/overlay",
        files={
            "file": ("a.mp4", a.read_bytes(), "video/mp4"),
            "image": ("overlay.png", png.read_bytes(), "image/png"),
        },
        data={"x": "5", "y": "5"},
    )
    assert r.status_code == 200
    overlaid = tmp_path / "overlaid.mp4"
    overlaid.write_bytes(r.content)
    d = video_dimensions(str(overlaid))
    assert (d["width"], d["height"]) == (64, 64)  # overlay must not resize the base video

    wav = _write_silent_wav(tmp_path / "silence.wav")
    r = client.post(
        "/mux-audio",
        files={
            "file": ("a.mp4", a.read_bytes(), "video/mp4"),
            "audio": ("silence.wav", wav.read_bytes(), "audio/wav"),
        },
    )
    assert r.status_code == 200
    muxed = tmp_path / "muxed.mp4"
    muxed.write_bytes(r.content)
    assert video_dimensions(str(muxed))["has_sound"] is True


@pytest.mark.skipif(bool(_ffmpeg_reason), reason=_ffmpeg_reason)
def test_extract_frames_and_extract_flow_routes_round_trip(client, tmp_path) -> None:
    """``/extract-frames`` returns a ZIP of real PNG frames; ``/extract-flow``
    (output_format='npy') returns a real ``(T, H, W, 2)`` flow array."""
    src = tmp_path / "src.mp4"
    black_video(1.0, 64, 64, str(src), frame_rate=15)
    upload = {"file": ("src.mp4", src.read_bytes(), "video/mp4")}

    r = client.post("/extract-frames", files=upload, data={"frame_step": "5"})
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        names = zf.namelist()
        assert len(names) > 0
        assert all(n.endswith(".png") for n in names)

    r = client.post(
        "/extract-flow",
        files=upload,
        data={"output_format": "npy", "method": "dis", "frame_step": "5"},
    )
    assert r.status_code == 200
    npy_path = tmp_path / "flow.npy"
    npy_path.write_bytes(r.content)
    arr = np.load(npy_path)
    assert arr.ndim == 4 and arr.shape[-1] == 2 and arr.dtype == np.float32
