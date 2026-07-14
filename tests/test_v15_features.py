"""
Tests for v1.5.0 features: ``http_headers``, ``output_width`` / ``output_height``,
``pad_color``.

The ``http_headers`` round-trip needs a real HTTP server with header
echoing, which is out of scope for unit tests — we cover the wiring via
direct calls to the internal joiner. The resize+pad path is fully
unit-testable on synthetic frames.
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

# Fixture paths for the end-to-end ``extract_frames`` tests below.
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "video_tests")
VIDEO_NO_AUDIO = os.path.join(FIXTURES_DIR, "example_converted.mp4")


# ---------------------------------------------------------------------------
# _join_http_headers
# ---------------------------------------------------------------------------


def test_join_http_headers_none_returns_none() -> None:
    """_join_http_headers returns None for a None or empty header mapping."""
    assert _join_http_headers(None) is None
    assert _join_http_headers({}) is None


def test_join_http_headers_crlf_format() -> None:
    """_join_http_headers renders headers as CRLF-terminated "K: V" lines."""
    out = _join_http_headers({"User-Agent": "Mozilla", "Referer": "https://x.com/"})
    # ffmpeg / PyAV expect: "K1: V1\r\nK2: V2\r\n" — trailing CRLF.
    assert "User-Agent: Mozilla\r\n" in out
    assert "Referer: https://x.com/\r\n" in out
    assert out.endswith("\r\n")


# ---------------------------------------------------------------------------
# _parse_pad_color
# ---------------------------------------------------------------------------


def test_parse_pad_color_named_colors_bgr() -> None:
    """_parse_pad_color maps named colors to BGR tuples."""
    assert _parse_pad_color("black") == (0, 0, 0)
    assert _parse_pad_color("white") == (255, 255, 255)
    # BGR (not RGB) — verify red/green/blue are correctly swizzled.
    assert _parse_pad_color("red") == (0, 0, 255)
    assert _parse_pad_color("blue") == (255, 0, 0)
    assert _parse_pad_color("green") == (0, 255, 0)


def test_parse_pad_color_case_insensitive() -> None:
    """_parse_pad_color ignores case and surrounding whitespace."""
    assert _parse_pad_color("BLACK") == (0, 0, 0)
    assert _parse_pad_color(" White ") == (255, 255, 255)


def test_parse_pad_color_grey_and_gray_synonyms() -> None:
    """_parse_pad_color treats 'gray' and 'grey' as synonyms."""
    assert _parse_pad_color("gray") == _parse_pad_color("grey")


def test_parse_pad_color_hex() -> None:
    """_parse_pad_color converts #RRGGBB hex strings to BGR tuples."""
    # #FF8800 → RGB(255, 136, 0) → BGR(0, 136, 255)
    assert _parse_pad_color("#FF8800") == (0, 136, 255)
    assert _parse_pad_color("#000000") == (0, 0, 0)
    assert _parse_pad_color("#FFFFFF") == (255, 255, 255)


def test_parse_pad_color_transparent_raises_with_v16_hint() -> None:
    """'transparent' pad color raises ValueError pointing at the v1.6.0 feature."""
    with pytest.raises(ValueError, match="v1.6.0"):
        _parse_pad_color("transparent")


def test_parse_pad_color_unknown_raises() -> None:
    """Unknown names and malformed hex strings raise 'Unknown pad_color'."""
    with pytest.raises(ValueError, match="Unknown pad_color"):
        _parse_pad_color("rainbow")
    with pytest.raises(ValueError, match="Unknown pad_color"):
        _parse_pad_color("#XYZ")
    with pytest.raises(ValueError, match="Unknown pad_color"):
        _parse_pad_color("#1234")  # too short


# ---------------------------------------------------------------------------
# _apply_output_transform — resize-only and resize+pad paths
# ---------------------------------------------------------------------------


def _make_frame(h: int, w: int, color=(0, 0, 0)) -> np.ndarray:
    """Return a uniformly-colored (h, w, 3) BGR uint8 frame."""
    return np.full((h, w, 3), color, dtype=np.uint8)


def test_apply_transform_no_dims_returns_input_unchanged() -> None:
    """With no output dimensions the transform is a no-op returning the same object."""
    src = _make_frame(100, 200)
    out = _apply_output_transform(src, None, None, (0, 0, 0))
    assert out is src  # no-op identity


def test_apply_transform_only_width_preserves_aspect() -> None:
    """Supplying only output_width derives height keeping the aspect ratio."""
    # Source 200x100 → target width=400 → height should be 200 (2:1 aspect kept)
    src = _make_frame(100, 200)
    out = _apply_output_transform(
        src, output_width=400, output_height=None, pad_color_bgr=(0, 0, 0)
    )
    assert out.shape == (200, 400, 3)


def test_apply_transform_only_height_preserves_aspect() -> None:
    """Supplying only output_height derives width keeping the aspect ratio."""
    src = _make_frame(100, 200)
    out = _apply_output_transform(src, output_width=None, output_height=50, pad_color_bgr=(0, 0, 0))
    assert out.shape == (50, 100, 3)


def test_apply_transform_both_dims_pad_top_and_bottom() -> None:
    """Widescreen source (16:9) → square target → padded top/bottom."""
    src = _make_frame(180, 320)  # 16:9
    out = _apply_output_transform(
        src, output_width=200, output_height=200, pad_color_bgr=(255, 255, 255)
    )
    assert out.shape == (200, 200, 3)
    # Scale fit: scale = min(200/320, 200/180) = 0.625; new = (320*0.625, 180*0.625) = (200, 112.5) → (200, 113 or 112)
    # Top/bottom pad with white, centre = source color (black).
    # The middle horizontal band has the source content.
    middle_band = out[100, :, :]  # any row at the centre vertically
    assert (middle_band == [0, 0, 0]).all()  # source was black
    # Top band is white (pad).
    top_band = out[5, :, :]
    assert (top_band == [255, 255, 255]).all()


def test_apply_transform_both_dims_pad_left_and_right() -> None:
    """Portrait source (9:16) → square target → padded left/right."""
    src = _make_frame(320, 180)  # tall
    out = _apply_output_transform(
        src, output_width=200, output_height=200, pad_color_bgr=(0, 0, 255)
    )
    assert out.shape == (200, 200, 3)
    # Scale fit: scale = min(200/180, 200/320) = 0.625; new = (180*0.625, 320*0.625) = (113, 200)
    # The centre column is source (black). Outermost columns are red pad.
    left_band = out[:, 0, :]
    assert (left_band == [0, 0, 255]).all()  # red pad


def test_apply_transform_target_matches_source_no_pad() -> None:
    """Same aspect ratio source/target → scale only, no pad."""
    src = _make_frame(100, 200)  # 2:1
    out = _apply_output_transform(
        src, output_width=400, output_height=200, pad_color_bgr=(123, 45, 6)
    )
    assert out.shape == (200, 400, 3)
    # No padding bands → no pixel should ever equal the pad color.
    assert not (out == [123, 45, 6]).all(axis=-1).any()


def test_apply_transform_downscale_uses_inter_area_no_corruption() -> None:
    """Just sanity: downscaling produces valid uint8 of the right shape."""
    src = np.random.randint(0, 256, (1080, 1920, 3), dtype=np.uint8)
    out = _apply_output_transform(src, output_width=480, output_height=270, pad_color_bgr=(0, 0, 0))
    assert out.shape == (270, 480, 3)
    assert out.dtype == np.uint8


# ---------------------------------------------------------------------------
# End-to-end via extract_frames on the existing fixture
# (imports and fixture paths are declared at the top of the module)
# ---------------------------------------------------------------------------


def _has_fixture() -> bool:
    """Return True if the committed example video fixture exists and is valid."""
    return os.path.isfile(VIDEO_NO_AUDIO) and is_valid_video_file(VIDEO_NO_AUDIO)


@pytest.mark.skipif(not _has_fixture(), reason="example_converted.mp4 missing")
def test_extract_frames_output_width_height_pad_e2e() -> None:
    """End-to-end: pull a few frames at an exact size with letterbox padding."""
    frames = list(
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
    assert len(frames) > 0
    for f in frames:
        assert f.shape == (320, 320, 3)
        assert f.dtype == np.uint8


@pytest.mark.skipif(not _has_fixture(), reason="example_converted.mp4 missing")
def test_extract_frames_output_width_only_preserves_aspect_e2e() -> None:
    """End-to-end: output_width alone resizes frames keeping aspect ratio."""
    frames = list(
        extract_frames(
            VIDEO_NO_AUDIO,
            start_instant=0.0,
            end_instant=0.3,
            frame_step=5,
            output_width=640,  # height derived
        )
    )
    assert len(frames) > 0
    assert frames[0].shape[1] == 640


@pytest.mark.skipif(not _has_fixture(), reason="example_converted.mp4 missing")
def test_extract_frames_rejects_negative_output_dimensions() -> None:
    """extract_frames rejects zero/negative output_width or output_height."""
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


@pytest.mark.skipif(not _has_fixture(), reason="example_converted.mp4 missing")
def test_extract_frames_rejects_transparent_pad_color_in_v15() -> None:
    """extract_frames rejects a transparent pad_color in v1.5 (v1.6.0 hint)."""
    with pytest.raises(ValueError, match="v1.6.0"):
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
