"""
Tests for ``shrink_video``: HEVC re-encode kept only when lighter and faithful.

Module summary
--------------
Unit-tests the pure helpers (VMAF windows, audio copy-or-re-encode, the
calibrated starting quality), the refusals (output over input, a non-ISO-BMFF
container, an unknown encoder), and the "already HEVC" short cut. End to end,
a deliberately over-encoded H.264 clip (CRF 4) is shrunk with ``libx265``,
which every ffmpeg build in CI has, and with ``hevc_videotoolbox`` where the
platform has it. The CLI and HTTP surfaces are checked on the same clip.
Everything that scores VMAF is skipped when ffmpeg lacks ``libvmaf``.

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
import shutil
import subprocess

import ffmpeg
import os_helper as osh
import pytest

import video_helper as vh
from video_helper.main import (
    _shrink_audio_kwargs,
    _shrink_start,
    _vmaf_windows,
)

osh.verbosity(0)

needs_vmaf = pytest.mark.skipif(not vh.has_libvmaf(), reason="ffmpeg has no libvmaf")


@pytest.fixture(scope="module")
def over_encoded(tmp_path_factory) -> str:
    """A 3 s 640x360 H.264 clip at CRF 4 with 320 kbit/s audio: plenty to shrink."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("needs ffmpeg")
    path = tmp_path_factory.mktemp("shrink") / "over.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=640x360:r=25:d=3",
            "-f",
            "lavfi",
            "-i",
            "sine=f=440:d=3",
            "-c:v",
            "libx264",
            "-crf",
            "4",
            "-c:a",
            "aac",
            "-b:a",
            "320k",
            "-ac",
            "2",
            str(path),
        ],
        check=True,
        stdin=subprocess.DEVNULL,
    )
    return str(path)


def _streams(path: str) -> list[dict]:
    """ffprobe streams of *path*."""
    return ffmpeg.probe(path)["streams"]


def test_vmaf_windows_spread_over_long_files_and_cover_short_ones() -> None:
    """A short file is scored whole; a long one in evenly spaced windows."""
    assert _vmaf_windows(20.0, 4, 8.0) == [(0.0, 20.0)]
    assert [round(s) for s, _ in _vmaf_windows(800.0, 4, 8.0)] == [96, 296, 496, 696]
    assert _vmaf_windows(800.0, 0, 8.0) == [(0.0, 800.0)]


def test_light_audio_is_copied_and_heavy_audio_reencoded() -> None:
    """Up to 112 kbit/s per channel of AAC/MP3 is copied, anything else re-encoded."""
    assert _shrink_audio_kwargs([("aac", 2, 128)], "aac") == {"c:a:0": "copy"}
    assert _shrink_audio_kwargs([("mp3", 6, 448)], "aac") == {"c:a:0": "copy"}
    assert _shrink_audio_kwargs([("aac", 2, 480)], "aac_at") == {"c:a:0": "aac_at", "b:a:0": "192k"}
    assert _shrink_audio_kwargs([("pcm_s16le", 2, 1536)], "aac")["c:a:0"] == "aac"


def test_starting_quality_depends_on_encoder_and_height() -> None:
    """Small pictures start higher on VideoToolbox; a caller's start is honoured."""
    assert [_shrink_start("hevc_videotoolbox", None, h) for h in (480, 720, 1080)] == [71, 68, 65]
    assert _shrink_start("hevc_videotoolbox", 60, 2160) == 60
    assert _shrink_start("libx265", None, 360) == 24


def test_refuses_bad_destinations_and_encoders(over_encoded, tmp_path) -> None:
    """Output over input, a non-ISO-BMFF container and an unknown encoder are refused."""
    with pytest.raises(ValueError, match="both an input and the output"):
        vh.shrink_video(over_encoded, over_encoded)
    with pytest.raises(ValueError, match="mp4"):
        vh.shrink_video(over_encoded, str(tmp_path / "out.mkv"))
    with pytest.raises(ValueError, match="vcodec"):
        vh.shrink_video(over_encoded, str(tmp_path / "out.mp4"), vcodec="libx264")


@needs_vmaf
def test_vmaf_of_an_identical_copy_is_near_perfect(over_encoded, tmp_path) -> None:
    """The rank pairing lines the two sides up: identical pictures score ~100."""
    copy = str(tmp_path / "copy.mp4")
    shutil.copyfile(over_encoded, copy)
    score = vh.vmaf_score(copy, over_encoded)
    assert score["vmaf"] > 99 and score["vmaf_p1"] > 95 and score["frames"] == 75
    with pytest.raises(ValueError, match="compared with itself"):
        vh.vmaf_score(over_encoded, over_encoded)


@needs_vmaf
def test_x265_shrinks_an_over_encoded_clip(over_encoded, tmp_path) -> None:
    """End to end: lighter, faithful, hvc1-tagged, same duration, audio re-encoded."""
    out = str(tmp_path / "x265.mp4")
    report = vh.shrink_video(over_encoded, out, vcodec="libx265", min_vmaf=90, min_vmaf_p1=80)
    assert report["decision"] == "shrunk", report
    assert report["output"] == out and report["ratio"] <= 0.85 and report["vmaf"] >= 90
    video, audio = (
        next(s for s in _streams(out) if s["codec_type"] == k) for k in ("video", "audio")
    )
    assert video["codec_name"] == "hevc" and video["codec_tag_string"] == "hvc1"
    assert int(audio["bit_rate"]) < 250_000
    assert abs(vh.video_duration(out) - vh.video_duration(over_encoded)) < 0.5


@needs_vmaf
@pytest.mark.skipif(
    vh.hw_vcodec("", "hevc_videotoolbox") != "hevc_videotoolbox", reason="needs VideoToolbox"
)
def test_videotoolbox_shrinks_an_over_encoded_clip(over_encoded, tmp_path) -> None:
    """The hardware path reaches the same gates."""
    report = vh.shrink_video(
        over_encoded,
        str(tmp_path / "vt.mp4"),
        vcodec="hevc_videotoolbox",
        min_vmaf=90,
        min_vmaf_p1=80,
    )
    assert report["decision"] == "shrunk", report


@needs_vmaf
def test_unreachable_gates_keep_the_original_and_write_nothing(over_encoded, tmp_path) -> None:
    """A ratio no encode can meet means "kept", and no output file."""
    out = tmp_path / "never.mp4"
    report = vh.shrink_video(over_encoded, str(out), vcodec="libx265", max_ratio=0.001)
    assert report["decision"] == "kept" and report["reason"] == "gain too small"
    assert report["output"] is None and not out.exists()


@needs_vmaf
def test_hevc_sources_are_kept_without_encoding(over_encoded, tmp_path) -> None:
    """Already HEVC: nothing to gain from a second lossy generation."""
    hevc = str(tmp_path / "hevc.mp4")
    assert (
        vh.shrink_video(over_encoded, hevc, vcodec="libx265", min_vmaf=90, min_vmaf_p1=80)[
            "decision"
        ]
        == "shrunk"
    )
    report = vh.shrink_video(hevc, str(tmp_path / "again.mp4"))
    assert report == {**report, "decision": "kept", "reason": "already hevc", "output": None}


@needs_vmaf
def test_cli_prints_the_report(over_encoded, tmp_path) -> None:
    """``video-helper shrink`` prints the library's report as JSON."""
    from click.testing import CliRunner

    from video_helper.cli import cli

    out = tmp_path / "cli.mp4"
    result = CliRunner().invoke(
        cli,
        [
            "shrink",
            "--input",
            over_encoded,
            "--output",
            str(out),
            "--vcodec",
            "libx265",
            "--min-vmaf",
            "90",
            "--min-vmaf-p1",
            "80",
        ],
    )
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["decision"] == "shrunk" and out.exists()


@needs_vmaf
def test_http_answers_a_file_when_shrunk_and_json_when_kept(over_encoded) -> None:
    """``POST /shrink``: the video plus its report header, or the report alone."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from video_helper.api import app

    form = {"vcodec": "libx265", "min_vmaf": "90", "min_vmaf_p1": "80"}
    with TestClient(app) as client, open(over_encoded, "rb") as fh:
        body = fh.read()
        shrunk = client.post("/shrink", files={"file": ("over.mp4", body)}, data=form)
        kept = client.post(
            "/shrink", files={"file": ("over.mp4", body)}, data={**form, "max_ratio": "0.001"}
        )
    assert shrunk.status_code == 200, shrunk.text
    assert json.loads(shrunk.headers["x-shrink-report"])["decision"] == "shrunk"
    assert shrunk.content[4:8] == b"ftyp"
    assert kept.status_code == 200 and kept.json()["decision"] == "kept"
    assert "output" not in kept.json()


def test_http_refuses_an_unknown_encoder() -> None:
    """The route checks ``vcodec`` before spooling anything."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from video_helper.api import app

    with TestClient(app) as client:
        r = client.post("/shrink", files={"file": ("x.mp4", b"")}, data={"vcodec": "libx264"})
    assert r.status_code == 400 and "vcodec" in r.text
