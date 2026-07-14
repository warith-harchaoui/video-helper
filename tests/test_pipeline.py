"""
Coverage for the pipeline primitives added in v1.2.0
(``video_duration``, ``black_video``, ``image_loop_to_video``,
``concat_videos``, ``overlay_image``, ``extract_audio_track``,
``mux_audio_video``, ``burn_subtitles``) plus the subtitle helpers
(``srt2vtt``, ``extract_unique_colors``).

All tests build their own fixtures on the fly under ``tmp_path``: a
solid-black PNG via ``cv2``, a 1 s silent WAV via ``ffmpeg``,
a one-cue SRT via plain ``open()``. They still need ffmpeg on PATH
(checked once at module scope and the whole file skipped if absent).
"""

from __future__ import annotations

import shutil
import subprocess

import cv2
import numpy as np
import os_helper as osh
import pytest

from video_helper import (
    black_video,
    burn_subtitles,
    concat_videos,
    extract_audio_track,
    extract_unique_colors,
    image_loop_to_video,
    is_valid_video_file,
    mux_audio_video,
    overlay_image,
    srt2vtt,
    video_dimensions,
    video_duration,
)

osh.verbosity(0)

if shutil.which("ffmpeg") is None:
    pytest.skip("ffmpeg is required for the pipeline tests", allow_module_level=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_subtitles_filter() -> bool:
    """Return True if ffmpeg was built with libass (subtitles filter)."""
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-filters"],
        capture_output=True,
        text=True,
        check=False,
    )
    return "subtitles" in proc.stdout


def _write_png(path, color=(0, 0, 0), size=(64, 64)) -> str:
    """Write a uniformly-colored PNG (BGR) and return its path."""
    img = np.full((size[1], size[0], 3), color, dtype=np.uint8)
    cv2.imwrite(str(path), img)
    return str(path)


def _write_srt(path) -> str:
    """Write a tiny multi-color SRT and return its path."""
    content = (
        "1\n"
        "00:00:00,500 --> 00:00:02,000\n"
        '<font color="#FF0000">Hello</font>\n'
        "\n"
        "2\n"
        "00:00:02,000 --> 00:00:04,000\n"
        '<font color="#00FF00">World</font>\n'
    )
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    return str(path)


# ---------------------------------------------------------------------------
# Subtitle helpers
# ---------------------------------------------------------------------------


def test_extract_unique_colors(tmp_path) -> None:
    """extract_unique_colors returns the distinct hex colors used in an SRT."""
    srt = _write_srt(tmp_path / "subs.srt")
    colors = extract_unique_colors(srt)
    assert colors == {"#FF0000", "#00FF00"}


def test_srt2vtt_default_paths(tmp_path) -> None:
    """srt2vtt writes sibling .vtt/.css with color cue classes and dot timecodes."""
    srt = _write_srt(tmp_path / "subs.srt")
    srt2vtt(srt)
    vtt = tmp_path / "subs.vtt"
    css = tmp_path / "subs.css"
    assert vtt.exists() and css.exists()
    vtt_text = vtt.read_text(encoding="utf-8")
    assert vtt_text.startswith("WEBVTT")
    # Cue classes derived from the hex colors.
    assert "<c.ff0000>Hello</c>" in vtt_text
    assert "<c.00ff00>World</c>" in vtt_text
    # Comma → dot in timecodes.
    assert "00:00:00.500 --> 00:00:02.000" in vtt_text


def test_srt2vtt_custom_paths(tmp_path) -> None:
    """srt2vtt honors explicit vtt/css paths and emits ::cue rules per color."""
    srt = _write_srt(tmp_path / "subs.srt")
    vtt = tmp_path / "out.vtt"
    css = tmp_path / "out.css"
    srt2vtt(srt, str(vtt), str(css))
    assert vtt.exists() and css.exists()
    css_text = css.read_text(encoding="utf-8")
    # Both colors get a ::cue rule.
    assert "::cue(.ff0000)" in css_text
    assert "::cue(.00ff00)" in css_text


# ---------------------------------------------------------------------------
# video_duration
# ---------------------------------------------------------------------------


def test_video_duration_matches_black_video(tmp_path) -> None:
    """video_duration reports the duration of a generated black clip."""
    out = str(tmp_path / "black.mp4")
    black_video(1.5, 64, 64, out, frame_rate=15)
    assert is_valid_video_file(out)
    assert abs(video_duration(out) - 1.5) < 0.2


# ---------------------------------------------------------------------------
# black_video
# ---------------------------------------------------------------------------


def test_black_video_dimensions(tmp_path) -> None:
    """black_video rounds odd dimensions down to even and produces a silent clip."""
    out = str(tmp_path / "black.mp4")
    black_video(0.5, 65, 33, out, frame_rate=15)  # odd dims → rounded down
    assert is_valid_video_file(out)
    d = video_dimensions(out)
    assert d["width"] == 64 and d["height"] == 32
    assert d["has_sound"] is False


def test_black_video_rejects_bad_duration(tmp_path) -> None:
    """black_video rejects a non-positive duration with an assertion."""
    with pytest.raises(AssertionError):
        black_video(0.0, 64, 64, str(tmp_path / "x.mp4"))


# ---------------------------------------------------------------------------
# image_loop_to_video
# ---------------------------------------------------------------------------


def test_image_loop_to_video_letterbox(tmp_path) -> None:
    """image_loop_to_video letterboxes a still into an exact target resolution."""
    png = _write_png(tmp_path / "still.png", color=(255, 0, 0), size=(50, 40))
    out = str(tmp_path / "still.mp4")
    image_loop_to_video(png, 1.0, out, frame_rate=15, width=128, height=72)
    assert is_valid_video_file(out)
    d = video_dimensions(out)
    assert d["width"] == 128 and d["height"] == 72
    assert d["has_sound"] is False


# ---------------------------------------------------------------------------
# concat_videos
# ---------------------------------------------------------------------------


def test_concat_videos_doubles_duration(tmp_path) -> None:
    """Concatenating two equal clips yields a clip of roughly double duration."""
    a = str(tmp_path / "a.mp4")
    b = str(tmp_path / "b.mp4")
    black_video(1.0, 64, 64, a, frame_rate=15)
    black_video(1.0, 64, 64, b, frame_rate=15)
    out = str(tmp_path / "ab.mp4")
    concat_videos([a, b], out, reencode=True, frame_rate=15)
    assert is_valid_video_file(out)
    assert abs(video_duration(out) - 2.0) < 0.2


def test_concat_videos_rejects_empty(tmp_path) -> None:
    """concat_videos rejects an empty input list with an assertion."""
    with pytest.raises(AssertionError):
        concat_videos([], str(tmp_path / "x.mp4"))


# ---------------------------------------------------------------------------
# overlay_image
# ---------------------------------------------------------------------------


def test_overlay_image_preserves_dimensions(tmp_path) -> None:
    """overlay_image keeps the base video's dimensions unchanged."""
    base = str(tmp_path / "base.mp4")
    black_video(1.0, 128, 72, base, frame_rate=15)
    overlay = _write_png(tmp_path / "ovr.png", color=(0, 255, 0), size=(16, 16))
    out = str(tmp_path / "out.mp4")
    overlay_image(base, overlay, out, x="10", y="10")
    assert is_valid_video_file(out)
    d = video_dimensions(out)
    assert d["width"] == 128 and d["height"] == 72


# ---------------------------------------------------------------------------
# extract_audio_track + mux_audio_video
# ---------------------------------------------------------------------------


def _make_silent_wav(path, duration=1.0, sample_rate=16000) -> str:
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
    return str(path)


def test_mux_then_extract_roundtrip(tmp_path) -> None:
    """Muxing audio into a silent clip then extracting it round-trips a sound track."""
    video = str(tmp_path / "silent.mp4")
    audio = _make_silent_wav(tmp_path / "silence.wav", duration=1.0)
    black_video(1.0, 64, 64, video, frame_rate=15)

    muxed = str(tmp_path / "muxed.mp4")
    mux_audio_video(video, audio, muxed)
    assert is_valid_video_file(muxed)
    d = video_dimensions(muxed)
    assert d["has_sound"] is True

    out_audio = str(tmp_path / "back.wav")
    extract_audio_track(muxed, out_audio, sample_rate=16000, channels=1)
    assert osh.file_exists(out_audio) and osh.size_file(out_audio) > 0


# ---------------------------------------------------------------------------
# burn_subtitles
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_subtitles_filter(),
    reason="ffmpeg built without libass (subtitles filter)",
)
def test_burn_subtitles_smoke(tmp_path) -> None:
    """burn_subtitles produces a valid clip preserving the source duration."""
    video = str(tmp_path / "in.mp4")
    black_video(2.5, 128, 72, video, frame_rate=15)
    srt = _write_srt(tmp_path / "subs.srt")
    out = str(tmp_path / "burned.mp4")
    burn_subtitles(video, srt, out)
    assert is_valid_video_file(out)
    assert abs(video_duration(out) - 2.5) < 0.2


def test_burn_subtitles_rejects_unknown_format(tmp_path) -> None:
    """burn_subtitles rejects a subtitle file with an unknown format."""
    video = str(tmp_path / "in.mp4")
    black_video(0.5, 64, 64, video, frame_rate=15)
    bad = tmp_path / "subs.txt"
    bad.write_text("not subtitles")
    with pytest.raises(ValueError):
        burn_subtitles(video, str(bad), str(tmp_path / "out.mp4"))
