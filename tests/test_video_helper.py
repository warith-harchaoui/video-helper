"""
Core library tests for ``video_helper``.

Module summary
--------------
Exercises the primary public functions — validation, dimension probing,
conversion, chunk extraction, and frame extraction / dumping — against the
committed fixtures in ``video_tests/``. Integration-heavy cases are guarded
so the suite degrades gracefully when a fixture or optional backend is
missing.

Author
------
Project maintainers.
"""

from __future__ import annotations

import os

import numpy as np
import os_helper as osh
import pytest

from video_helper import (
    dump_frames,
    extract_frames,
    extract_video_chunk,
    is_valid_video_file,
    video_converter,
    video_dimensions,
)

# Local fixtures shipped with the repo (see video_tests/).
# `shaky.mp4` has audio; `example_converted.mp4` does not.
FIXTURES_DIR = osh.join([os.path.dirname(__file__), "..", "video_tests"])
VIDEO_WITH_AUDIO = osh.join([FIXTURES_DIR, "shaky.mp4"])
VIDEO_NO_AUDIO = osh.join([FIXTURES_DIR, "example_converted.mp4"])

osh.verbosity(0)


def _require(path) -> str:
    """Return the fixture path, skipping the test if it does not exist."""
    if not osh.file_exists(path):
        pytest.skip(f"Fixture missing: {path}")
    return path


def test_video_dimensions() -> None:
    """Video dimensions and frame rate are retrieved correctly."""
    video_file = _require(VIDEO_WITH_AUDIO)
    d = video_dimensions(video_file)
    assert {"width", "height", "frame_rate", "duration", "has_sound"} <= set(d)
    assert d["duration"] > 0
    assert d["has_sound"] is True


def test_video_conversion(tmp_path) -> None:
    """Conversion applies fps, resize, and audio stripping."""
    video_file = _require(VIDEO_WITH_AUDIO)
    src = video_dimensions(video_file)

    frame_rate = 15
    width = src["width"] // 2 & ~1  # ensure even
    height = src["height"] // 2 & ~1
    output_video_file = str(tmp_path / "converted.mp4")

    video_converter(
        video_file,
        output_video_file,
        frame_rate=frame_rate,
        width=width,
        height=height,
        without_sound=True,
    )

    d = video_dimensions(output_video_file)
    assert d["width"] == width
    assert d["height"] == height
    assert round(d["frame_rate"]) == frame_rate
    assert d["has_sound"] is False
    assert d["duration"] > 0


def test_video_conversion_defaults_extensionless_output_to_mp4(tmp_path) -> None:
    """An output path with no extension gets one (mp4) instead of failing.

    Regression test: ffmpeg cannot infer a muxer from an extensionless path,
    and folder_name_ext().ext would be "" in that case, so video_converter
    used to hand ffmpeg an unusable target.
    """
    video_file = _require(VIDEO_WITH_AUDIO)
    output_video_file = str(tmp_path / "converted")  # no extension

    video_converter(video_file, output_video_file, without_sound=True)

    assert not osh.file_exists(output_video_file)
    assert osh.file_exists(output_video_file + ".mp4")


def test_frame_extraction() -> None:
    """Frame extraction honors time range and frame_step."""
    video_file = _require(VIDEO_NO_AUDIO)
    d = video_dimensions(video_file)
    frame_rate = d["frame_rate"]

    start_instant = 1.0
    end_instant = 2.0
    frame_step = 5

    frames = list(
        extract_frames(
            video_file,
            start_instant=start_instant,
            end_instant=end_instant,
            frame_step=frame_step,
        )
    )

    assert len(frames) > 0
    for frame in frames:
        assert isinstance(frame, np.ndarray)
        assert frame.shape[-1] == 3
        assert frame.shape[0] == d["height"]
        assert frame.shape[1] == d["width"]

    expected = int((end_instant - start_instant) * frame_rate / frame_step)
    assert abs(len(frames) - expected) <= 2

    frame_interval = 0.5
    frames_interval = list(
        extract_frames(
            video_file,
            start_instant=start_instant,
            end_instant=end_instant,
            frame_interval=frame_interval,
        )
    )
    expected_interval = int((end_instant - start_instant) / frame_interval)
    assert abs(len(frames_interval) - expected_interval) <= 2


def test_frames_dump_round_trip_from_a_real_video(tmp_path) -> None:
    """Round-trip: extract a short window of real frames, dump, and re-open
    as a valid video."""
    video_file = _require(VIDEO_NO_AUDIO)
    d = video_dimensions(video_file)

    frames = list(extract_frames(video_file, start_instant=0.0, end_instant=1.0))
    assert len(frames) > 0

    out = str(tmp_path / "frames.mp4")
    dump_frames(frames, out, int(round(d["frame_rate"])))
    assert is_valid_video_file(out)


def test_dump_frames_preserves_bgr_channel_order(tmp_path) -> None:
    """dump_frames writes frames as-is (BGR), matching extract_frames' own
    contract — it must not silently swap red and blue (regression: an
    internal RGB2BGR conversion previously flipped BGR input to the wrong
    colors on write)."""
    red_bgr = np.zeros((16, 16, 3), dtype=np.uint8)
    red_bgr[..., 2] = 255  # pure red in BGR: channel 2 (R) lit, 0 (B) and 1 (G) off
    frames = [red_bgr.copy() for _ in range(5)]

    out = str(tmp_path / "red.mp4")
    dump_frames(frames, out, fps=5)
    assert is_valid_video_file(out)

    readback = next(iter(extract_frames(out, start_index=0, end_index=0)))
    # Lossy H.264 round-trip: assert the dominant channel, not exact equality.
    mean_b, mean_g, mean_r = (
        readback[..., 0].mean(),
        readback[..., 1].mean(),
        readback[..., 2].mean(),
    )
    assert mean_r > mean_b and mean_r > mean_g, (
        f"Expected red (BGR) to survive the round trip, got B={mean_b:.0f} G={mean_g:.0f} R={mean_r:.0f}"
    )


def test_extract_video_chunk(tmp_path) -> None:
    """Temporal crop yields a valid, shorter video."""
    video_file = _require(VIDEO_NO_AUDIO)
    out = str(tmp_path / "chunk.mp4")
    extract_video_chunk(video_file, 1.0, 3.0, out)
    assert is_valid_video_file(out)
    d = video_dimensions(out)
    assert 1.5 < d["duration"] < 2.5
