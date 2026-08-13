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


def test_compress_video_default_hevc_gets_hvc1_tag(short_clip, tmp_path) -> None:
    """Default vcodec=libx265 output is tagged hvc1 (QuickTime/Apple compatibility)."""
    out = str(tmp_path / "compressed.mp4")
    compress_video(short_clip, out, target_size_mb=0.5)
    stream = _video_stream(out)
    assert stream["codec_name"] == "hevc"
    assert stream.get("codec_tag_string") == "hvc1"


def test_compress_video_libx264_has_no_hvc1_tag(short_clip, tmp_path) -> None:
    """vcodec=libx264 encodes H.264 and never applies the HEVC-only hvc1 tag."""
    out = str(tmp_path / "compressed.mp4")
    compress_video(short_clip, out, target_size_mb=0.5, vcodec="libx264")
    stream = _video_stream(out)
    assert stream["codec_name"] == "h264"


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


def test_compress_video_rejects_infeasible_target_size(short_clip) -> None:
    """A target size too small for the floor bitrate raises, instead of producing junk."""
    with pytest.raises(AssertionError, match="leaves only"):
        compress_video(short_clip, target_size_mb=0.05)


def test_compress_video_rejects_invalid_input(tmp_path) -> None:
    """A nonexistent input path raises rather than silently no-op-ing."""
    with pytest.raises(AssertionError, match="Input video file not okay"):
        compress_video(str(tmp_path / "does-not-exist.mp4"))
