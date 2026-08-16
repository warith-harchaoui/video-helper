"""
Functional tests for v1.5.0 features: ``http_headers``, ``output_width`` /
``output_height``, ``pad_color``.

The ``http_headers`` round-trip needs a real HTTP server with header
echoing, which is out of scope for unit tests -- we cover the wiring via
direct calls to the internal joiner. The resize+pad path is fully
unit-testable on synthetic frames, then verified end to end against the
committed fixture.
"""

from __future__ import annotations

import os

import numpy as np
import pytest

from video_helper import extract_frames, is_valid_video_file
from video_helper.main import (
    _apply_output_transform,
    _join_http_headers,
    _parse_pad_color,
)

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "video_tests")
VIDEO_NO_AUDIO = os.path.join(FIXTURES_DIR, "example_converted.mp4")


def test_join_http_headers_formats_crlf_lines() -> None:
    """None/empty mappings return None; a populated mapping renders CRLF-
    terminated 'K: V' lines, as ffmpeg/PyAV expect."""
    assert _join_http_headers(None) is None
    assert _join_http_headers({}) is None

    out = _join_http_headers({"User-Agent": "Mozilla", "Referer": "https://x.com/"})
    assert "User-Agent: Mozilla\r\n" in out
    assert "Referer: https://x.com/\r\n" in out
    assert out.endswith("\r\n")


def test_parse_pad_color_accepts_names_case_and_hex() -> None:
    """Named colors map to BGR tuples (not RGB), matching is case/whitespace
    insensitive, 'gray'/'grey' are synonyms, and #RRGGBB hex is BGR-swizzled."""
    assert _parse_pad_color("black") == (0, 0, 0)
    assert _parse_pad_color("white") == (255, 255, 255)
    assert _parse_pad_color("red") == (0, 0, 255)
    assert _parse_pad_color("blue") == (255, 0, 0)
    assert _parse_pad_color("green") == (0, 255, 0)
    assert _parse_pad_color("BLACK") == (0, 0, 0)
    assert _parse_pad_color(" White ") == (255, 255, 255)
    assert _parse_pad_color("gray") == _parse_pad_color("grey")
    # #FF8800 -> RGB(255, 136, 0) -> BGR(0, 136, 255)
    assert _parse_pad_color("#FF8800") == (0, 136, 255)
    assert _parse_pad_color("#000000") == (0, 0, 0)
    assert _parse_pad_color("#FFFFFF") == (255, 255, 255)


def test_parse_pad_color_rejects_unsupported_and_unknown_values() -> None:
    """'transparent' raises a dedicated 'not supported' error; unknown names
    and malformed hex strings raise 'Unknown pad_color'."""
    with pytest.raises(ValueError, match="not supported"):
        _parse_pad_color("transparent")
    with pytest.raises(ValueError, match="Unknown pad_color"):
        _parse_pad_color("rainbow")
    with pytest.raises(ValueError, match="Unknown pad_color"):
        _parse_pad_color("#XYZ")
    with pytest.raises(ValueError, match="Unknown pad_color"):
        _parse_pad_color("#1234")  # too short


def _make_frame(h: int, w: int, color=(0, 0, 0)) -> np.ndarray:
    """Return a uniformly-colored (h, w, 3) BGR uint8 frame."""
    return np.full((h, w, 3), color, dtype=np.uint8)


def test_apply_transform_noop_and_aspect_preserving_resize() -> None:
    """No output dimensions is an identity no-op; supplying only width or
    only height derives the other dimension keeping aspect ratio."""
    src = _make_frame(100, 200)  # 2:1
    assert _apply_output_transform(src, None, None, (0, 0, 0)) is src

    by_width = _apply_output_transform(
        src, output_width=400, output_height=None, pad_color_bgr=(0, 0, 0)
    )
    assert by_width.shape == (200, 400, 3)

    by_height = _apply_output_transform(
        src, output_width=None, output_height=50, pad_color_bgr=(0, 0, 0)
    )
    assert by_height.shape == (50, 100, 3)


def test_apply_transform_letterboxes_to_target_aspect() -> None:
    """A widescreen source letterboxes top/bottom into a square target; a
    portrait source letterboxes left/right -- both with the requested pad
    color at the borders and the source content centered."""
    widescreen = _make_frame(180, 320)  # 16:9
    out = _apply_output_transform(
        widescreen, output_width=200, output_height=200, pad_color_bgr=(255, 255, 255)
    )
    assert out.shape == (200, 200, 3)
    assert (out[100, :, :] == [0, 0, 0]).all()  # centre band: source color (black)
    assert (out[5, :, :] == [255, 255, 255]).all()  # top band: white pad

    portrait = _make_frame(320, 180)  # tall
    out2 = _apply_output_transform(
        portrait, output_width=200, output_height=200, pad_color_bgr=(0, 0, 255)
    )
    assert out2.shape == (200, 200, 3)
    assert (out2[:, 0, :] == [0, 0, 255]).all()  # left column: red pad


def test_apply_transform_matching_aspect_has_no_padding() -> None:
    """Same aspect ratio source/target scales without ever introducing the
    pad color, and downscaling large frames produces valid uint8 output."""
    src = _make_frame(100, 200)  # 2:1
    out = _apply_output_transform(
        src, output_width=400, output_height=200, pad_color_bgr=(123, 45, 6)
    )
    assert out.shape == (200, 400, 3)
    assert not (out == [123, 45, 6]).all(axis=-1).any()

    large = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
    downscaled = _apply_output_transform(
        large, output_width=480, output_height=270, pad_color_bgr=(0, 0, 0)
    )
    assert downscaled.shape == (270, 480, 3)
    assert downscaled.dtype == np.uint8


def _has_fixture() -> bool:
    """Return True if the committed example video fixture exists and is valid."""
    return os.path.isfile(VIDEO_NO_AUDIO) and is_valid_video_file(VIDEO_NO_AUDIO)


@pytest.mark.skipif(not _has_fixture(), reason="example_converted.mp4 missing")
def test_extract_frames_output_width_height_pad_e2e() -> None:
    """End-to-end: pull frames at an exact letterboxed size, and with only
    output_width (aspect-preserving resize)."""
    padded = list(
        extract_frames(
            VIDEO_NO_AUDIO,
            start_instant=0.0,
            end_instant=0.5,
            frame_step=5,
            output_width=320,
            output_height=320,
            pad_color="black",
        )
    )
    assert len(padded) > 0
    for f in padded:
        assert f.shape == (320, 320, 3)
        assert f.dtype == np.uint8

    width_only = list(
        extract_frames(
            VIDEO_NO_AUDIO, start_instant=0.0, end_instant=0.3, frame_step=5, output_width=640
        )
    )
    assert len(width_only) > 0
    assert width_only[0].shape[1] == 640


@pytest.mark.skipif(not _has_fixture(), reason="example_converted.mp4 missing")
def test_extract_frames_rejects_invalid_output_options_e2e() -> None:
    """extract_frames rejects zero/negative output dimensions and a
    transparent pad_color end to end (not just at the transform-helper
    level -- these are the caller-facing error paths)."""
    with pytest.raises(ValueError, match="output_width"):
        list(
            extract_frames(
                VIDEO_NO_AUDIO,
                start_instant=0.0,
                end_instant=0.1,
                output_width=0,
                output_height=100,
            )
        )
    with pytest.raises(ValueError, match="output_height"):
        list(
            extract_frames(
                VIDEO_NO_AUDIO,
                start_instant=0.0,
                end_instant=0.1,
                output_width=100,
                output_height=-5,
            )
        )
    with pytest.raises(ValueError, match="not supported"):
        list(
            extract_frames(
                VIDEO_NO_AUDIO,
                start_instant=0.0,
                end_instant=0.1,
                output_width=200,
                output_height=200,
                pad_color="transparent",
            )
        )
