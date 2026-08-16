"""
Tests for ``compress_video``: two-pass, target-file-size HEVC compression.

Module summary
--------------
Unit-tests the bitrate-budget math (assertion floor, output-path defaults,
overwrite skip) and end-to-end verifies a real ffmpeg two-pass encode against
the ``shaky.mp4`` fixture (has audio, needed since the AAC pass would fail on
a silent source) — output validity, approximate target size, and the
``hvc1`` codec tag that makes HEVC output playable in QuickTime/Apple
players (the default ``hev1`` tag is not).

Author
------
Project maintainers.
"""

from __future__ import annotations

import os
from pathlib import Path

import ffmpeg
import os_helper as osh
import pytest

from video_helper import compress_video, extract_video_chunk, is_valid_video_file

FIXTURES_DIR = osh.join([os.path.dirname(__file__), "..", "video_tests"])
VIDEO_WITH_AUDIO = osh.join([FIXTURES_DIR, "shaky.mp4"])

osh.verbosity(0)


def _require(path) -> str:
    """Return the fixture path, skipping the test if it does not exist."""
    if not osh.file_exists(path):
        pytest.skip(f"Fixture missing: {path}")
    return path


@pytest.fixture(scope="module")
def short_clip(tmp_path_factory) -> str:
    """A ~4s clip with audio, trimmed from the fixture so two-pass tests stay fast."""
    src = _require(VIDEO_WITH_AUDIO)
    out = str(tmp_path_factory.mktemp("compress_fixtures") / "short.mp4")
    extract_video_chunk(src, 0.0, 4.0, out)
    return out


def _video_stream(path: str) -> dict:
    """Return the first video stream's ffprobe metadata."""
    probe = ffmpeg.probe(path)
    return next(s for s in probe["streams"] if s["codec_type"] == "video")


def test_compress_video_hits_target_size_and_is_valid(short_clip, tmp_path) -> None:
    """End-to-end: a feasible target size produces a valid, roughly-sized file."""
    out = str(tmp_path / "compressed.mp4")
    target_mb = 0.5
    result = compress_video(short_clip, out, target_size_mb=target_mb)
    assert result == out
    assert is_valid_video_file(out)
    size_mb = os.path.getsize(out) / (1024 * 1024)
    # Two-pass bitrate targeting is approximate (container/audio overhead,
    # VBV behavior) — allow a generous band rather than an exact match.
    assert size_mb < target_mb * 1.5


def test_compress_video_codec_tag_is_hvc1_only_for_default_hevc(short_clip, tmp_path) -> None:
    """Default vcodec=libx265 output is tagged hvc1 (QuickTime/Apple
    compatibility); vcodec=libx264 encodes H.264 and never applies the
    HEVC-only hvc1 tag."""
    hevc_out = str(tmp_path / "hevc.mp4")
    compress_video(short_clip, hevc_out, target_size_mb=0.5)
    hevc_stream = _video_stream(hevc_out)
    assert hevc_stream["codec_name"] == "hevc"
    assert hevc_stream.get("codec_tag_string") == "hvc1"

    h264_out = str(tmp_path / "h264.mp4")
    compress_video(short_clip, h264_out, target_size_mb=0.5, vcodec="libx264")
    assert _video_stream(h264_out)["codec_name"] == "h264"


def test_compress_video_copy_remuxes_without_reencoding(short_clip, tmp_path) -> None:
    """vcodec='copy' remuxes the source codec as-is instead of re-encoding."""
    src_stream = _video_stream(short_clip)
    out = str(tmp_path / "remuxed.mp4")
    result = compress_video(short_clip, out, vcodec="copy")
    assert result == out
    assert is_valid_video_file(out)
    assert _video_stream(out)["codec_name"] == src_stream["codec_name"]


def test_compress_video_output_defaults_to_compressed_suffix(short_clip, tmp_path) -> None:
    """Omitting output_video writes ``<input>-compressed.mp4`` next to the source."""
    src_copy = tmp_path / "clip.mp4"
    src_copy.write_bytes(Path(short_clip).read_bytes())
    result = compress_video(str(src_copy), target_size_mb=0.5)
    assert result == str(tmp_path / "clip-compressed.mp4")
    assert is_valid_video_file(result)


def test_compress_video_overwrite_false_skips_existing(short_clip, tmp_path) -> None:
    """overwrite=False returns an existing output untouched instead of re-encoding."""
    out = tmp_path / "already-there.mp4"
    out.write_bytes(b"not a real video, just a sentinel")
    before = out.stat().st_mtime_ns
    result = compress_video(short_clip, str(out), target_size_mb=0.5, overwrite=False)
    assert result == str(out)
    assert out.stat().st_mtime_ns == before
    assert out.read_bytes() == b"not a real video, just a sentinel"


def test_compress_video_clamps_to_floor_on_infeasible_target_size(short_clip, tmp_path) -> None:
    """A target size too small for the floor bitrate clamps to the floor instead
    of raising: per the function's own design (see its ``min_video_bitrate_kbps``
    docstring), a caller-supplied budget going negative on a longer-than-expected
    source must never be a hard failure — that would lose an entire pipeline's
    output over a compression nicety. The output exceeds the requested target
    size instead."""
    out = str(tmp_path / "compressed.mp4")
    target_mb = 0.05
    result = compress_video(short_clip, out, target_size_mb=target_mb)
    assert result == out
    assert is_valid_video_file(out)
    size_mb = os.path.getsize(out) / (1024 * 1024)
    assert size_mb > target_mb


def test_compress_video_rejects_invalid_input(tmp_path) -> None:
    """A nonexistent input path raises rather than silently no-op-ing."""
    with pytest.raises(AssertionError, match="Input video file not okay"):
        compress_video(str(tmp_path / "does-not-exist.mp4"))
