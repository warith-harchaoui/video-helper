import os
import pytest
import os_helper as osh
import numpy as np
from video_helper import (
    extract_unique_colors,
    srt2vtt,
    is_valid_video_file,
    video_dimensions,
    video_converter,
    extract_frames,
    dump_frames,
    extract_video_chunk,
)


# Local fixtures shipped with the repo (see video_tests/).
# `shaky.mp4` has audio; `example_converted.mp4` does not.
FIXTURES_DIR = osh.join([os.path.dirname(__file__), "..", "video_tests"])
VIDEO_WITH_AUDIO = osh.join([FIXTURES_DIR, "shaky.mp4"])
VIDEO_NO_AUDIO = osh.join([FIXTURES_DIR, "example_converted.mp4"])

osh.verbosity(0)


def _require(path):
    if not osh.file_exists(path):
        pytest.skip(f"Fixture missing: {path}")
    return path


def test_video_dimensions():
    """Video dimensions and frame rate are retrieved correctly."""
    video_file = _require(VIDEO_WITH_AUDIO)
    d = video_dimensions(video_file)
    assert {"width", "height", "frame_rate", "duration", "has_sound"} <= set(d)
    assert d["duration"] > 0
    assert d["has_sound"] is True


def test_video_conversion(tmp_path):
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


def test_frame_extraction():
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


def test_frames_dump(tmp_path):
    """Round-trip: extract a short window of frames, dump, and re-open."""
    video_file = _require(VIDEO_NO_AUDIO)
    d = video_dimensions(video_file)

    frames = list(
        extract_frames(video_file, start_instant=0.0, end_instant=1.0)
    )
    assert len(frames) > 0

    out = str(tmp_path / "frames.mp4")
    dump_frames(frames, out, int(round(d["frame_rate"])))
    assert is_valid_video_file(out)


def test_extract_video_chunk(tmp_path):
    """Temporal crop yields a valid, shorter video."""
    video_file = _require(VIDEO_NO_AUDIO)
    out = str(tmp_path / "chunk.mp4")
    extract_video_chunk(video_file, 1.0, 3.0, out)
    assert is_valid_video_file(out)
    d = video_dimensions(out)
    assert 1.5 < d["duration"] < 2.5
