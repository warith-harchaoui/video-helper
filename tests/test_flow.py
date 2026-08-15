"""
Tests for ``video_helper.flow`` (dense optical flow generator).

Module summary
--------------
Exercises the two zero-dependency backends (``"dis"``, ``"farneback"``) on
synthetic, deterministic frame pairs with a known horizontal shift, checking
the output contract (shape/dtype, zero flow on frame 1, correct flow sign),
the ``clip_flow`` option, and the ``grayscale`` output layout. ``method="raft"``
is exercised only when ``torchvision`` is importable — it also downloads
pretrained weights on first use, so it is opportunistic like the rest of this
repo's optional-dependency tests (see ``tests/test_asd_device.py``), never
required in CI. ``resize_flow`` (wavelet-based, needs ``PyWavelets``) is
likewise gated with ``pytest.importorskip("pywt")`` per test.

Author
------
Project maintainers.
"""

from __future__ import annotations

import os
import shutil

import cv2
import numpy as np
import os_helper as osh
import pytest

from video_helper import (
    extract_optical_flow,
    is_valid_video_file,
    iter_frame_optical_flow,
    resize_flow,
    video_dimensions,
)

FIXTURES_DIR = osh.join([os.path.dirname(__file__), "..", "video_tests"])
VIDEO_FIXTURE = osh.join([FIXTURES_DIR, "shaky.mp4"])


def _shifted_frame_pair(size: int = 64, shift: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Build two synthetic BGR frames: a bright block, then shifted right.

    Parameters
    ----------
    size : int, default 64
        Frame height and width.
    shift : int, default 4
        Horizontal shift (pixels) applied to the block in the second frame.

    Returns
    -------
    tuple[numpy.ndarray, numpy.ndarray]
        ``(frame0, frame1)``, each ``(size, size, 3)`` BGR uint8.
    """
    frame0 = np.zeros((size, size, 3), dtype=np.uint8)
    frame0[20:44, 20:44, :] = 255
    frame1 = np.zeros((size, size, 3), dtype=np.uint8)
    frame1[20:44, 20 + shift : 44 + shift, :] = 255
    return frame0, frame1


@pytest.mark.parametrize("method", ["dis", "farneback"])
def test_output_contract_and_first_frame_zero_flow(method: str) -> None:
    """Every yielded array is (H, W, 5) float32; frame 0 has exactly zero flow."""
    frame0, frame1 = _shifted_frame_pair()
    out = list(iter_frame_optical_flow(iter([frame0, frame1]), method=method))

    assert len(out) == 2
    for arr in out:
        assert arr.shape == (64, 64, 5)
        assert arr.dtype == np.float32

    np.testing.assert_array_equal(out[0][..., 3:], 0.0)
    np.testing.assert_allclose(out[0][..., :3], frame0.astype(np.float32))


@pytest.mark.parametrize("method", ["dis", "farneback"])
def test_recovers_approximate_rightward_shift(method: str) -> None:
    """A block shifted right should yield a predominantly positive vx over it."""
    frame0, frame1 = _shifted_frame_pair(size=64, shift=4)
    out = list(iter_frame_optical_flow(iter([frame0, frame1]), method=method))

    vx = out[1][20:44, 24:40, 3]  # interior of the moved block, away from edges
    assert vx.mean() > 0.5  # moved right → positive vx


@pytest.mark.parametrize("method", ["dis", "farneback"])
def test_grayscale_mode_yields_3_channel_arrays(method: str) -> None:
    """grayscale=True yields (H, W, 3): intensity + vx + vy, instead of (H, W, 5)."""
    frame0, frame1 = _shifted_frame_pair()
    out = list(iter_frame_optical_flow(iter([frame0, frame1]), method=method, grayscale=True))

    assert len(out) == 2
    for arr in out:
        assert arr.shape == (64, 64, 3)
        assert arr.dtype == np.float32

    expected_gray = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY).astype(np.float32)
    np.testing.assert_allclose(out[0][..., 0], expected_gray)
    np.testing.assert_array_equal(out[0][..., 1:], 0.0)  # frame 0 still has zero flow


def test_grayscale_mode_recovers_approximate_rightward_shift() -> None:
    """The flow channels behave identically in grayscale mode (last 2 channels)."""
    frame0, frame1 = _shifted_frame_pair(size=64, shift=4)
    out = list(iter_frame_optical_flow(iter([frame0, frame1]), method="dis", grayscale=True))

    vx = out[1][20:44, 24:40, 1]  # interior of the moved block, away from edges
    assert vx.mean() > 0.5  # moved right → positive vx


def test_clip_flow_bounds_the_output() -> None:
    """``clip_flow`` symmetrically bounds both channels without changing shape."""
    frame0, frame1 = _shifted_frame_pair(size=64, shift=10)
    out = list(iter_frame_optical_flow(iter([frame0, frame1]), method="dis", clip_flow=0.5))

    assert out[1].shape == (64, 64, 5)
    assert np.abs(out[1][..., 3:]).max() <= 0.5 + 1e-6


def test_unknown_method_raises() -> None:
    frame0, frame1 = _shifted_frame_pair()
    with pytest.raises(ValueError):
        list(iter_frame_optical_flow(iter([frame0, frame1]), method="bogus"))  # type: ignore[arg-type]


def test_raft_requires_torchvision(monkeypatch) -> None:
    """Without torchvision, method='raft' raises a clear ImportError, not an AttributeError."""
    import video_helper.flow as flow_mod

    monkeypatch.setattr(flow_mod, "_have_torchvision", lambda: False)
    frame0, frame1 = _shifted_frame_pair()
    with pytest.raises(ImportError, match="torchvision"):
        list(flow_mod.iter_frame_optical_flow(iter([frame0, frame1]), method="raft"))


def test_raft_recovers_approximate_rightward_shift() -> None:
    """Opportunistic: only runs when torchvision is importable (downloads weights on first use)."""
    pytest.importorskip("torchvision")
    frame0, frame1 = _shifted_frame_pair(size=136, shift=8)  # RAFT needs >= ~128px per side
    out = list(
        iter_frame_optical_flow(
            iter([frame0, frame1]), method="raft", raft_variant="small", device="cpu"
        )
    )

    assert out[1].shape == (136, 136, 5)
    assert out[1].dtype == np.float32
    np.testing.assert_array_equal(out[0][..., 3:], 0.0)
    vx = out[1][20:44, 24:40, 3]
    assert vx.mean() > 0.5


def test_raft_grayscale_mode_yields_3_channel_arrays() -> None:
    """RAFT still computes flow from the full-color pair, but output honors grayscale=True."""
    pytest.importorskip("torchvision")
    frame0, frame1 = _shifted_frame_pair(size=136, shift=8)
    out = list(
        iter_frame_optical_flow(
            iter([frame0, frame1]),
            method="raft",
            raft_variant="small",
            device="cpu",
            grayscale=True,
        )
    )

    assert out[1].shape == (136, 136, 3)
    vx = out[1][20:44, 24:40, 1]
    assert vx.mean() > 0.5


def _step_flow(size: int = 64, magnitude: float = 10.0) -> np.ndarray:
    """A (size, size, 2) flow field with a hard vx discontinuity down the middle."""
    flow = np.zeros((size, size, 2), dtype=np.float32)
    flow[:, size // 2 :, 0] = magnitude
    return flow


def test_resize_flow_shape_and_dtype() -> None:
    pytest.importorskip("pywt")
    flow = _step_flow()
    out = resize_flow(flow, output_width=32, output_height=40)
    assert out.shape == (40, 32, 2)
    assert out.dtype == np.float32


def test_resize_flow_identity_when_size_unchanged() -> None:
    pytest.importorskip("pywt")
    flow = _step_flow()
    out = resize_flow(flow, output_width=64, output_height=64)
    np.testing.assert_array_equal(out, flow)


def test_resize_flow_rescales_magnitude_with_resolution() -> None:
    """A flow field upsampled 2x must have its displacement values ~doubled."""
    pytest.importorskip("pywt")
    flow = np.full((32, 32, 2), 5.0, dtype=np.float32)  # uniform flow, no discontinuity
    out = resize_flow(flow, output_width=64, output_height=64)
    np.testing.assert_allclose(out, 10.0, atol=1e-3)


def test_resize_flow_never_exceeds_source_value_range() -> None:
    """Wavelet reconstruction can ring past the source range at a hard step; must be clipped."""
    pytest.importorskip("pywt")
    flow = _step_flow(size=64, magnitude=10.0)
    down = resize_flow(flow, output_width=32, output_height=32)
    assert down[..., 0].min() >= 0.0
    assert down[..., 0].max() <= 10.0 + 1e-4


def test_resize_flow_rejects_wrong_channel_count() -> None:
    pytest.importorskip("pywt")
    with pytest.raises(ValueError, match="H, W, 2"):
        resize_flow(np.zeros((8, 8, 3), dtype=np.float32), output_width=4, output_height=4)


def test_resize_flow_rejects_nonpositive_target() -> None:
    pytest.importorskip("pywt")
    with pytest.raises(ValueError, match="positive"):
        resize_flow(_step_flow(), output_width=0, output_height=4)


def test_resize_flow_requires_pywt(monkeypatch) -> None:
    """Without PyWavelets, resize_flow raises a clear ImportError, not an AttributeError."""
    import video_helper.flow as flow_mod

    monkeypatch.setattr(flow_mod, "_have_pywt", lambda: False)
    with pytest.raises(ImportError, match="PyWavelets"):
        flow_mod.resize_flow(_step_flow(), output_width=32, output_height=32)


def test_iter_frame_optical_flow_output_size_is_wired_to_resize_flow() -> None:
    """output_width/output_height resize both the image and flow channels."""
    pytest.importorskip("pywt")
    frame0, frame1 = _shifted_frame_pair(size=64, shift=4)
    out = list(
        iter_frame_optical_flow(
            iter([frame0, frame1]), method="dis", output_width=32, output_height=32
        )
    )
    assert out[0].shape == (32, 32, 5)
    assert out[1].shape == (32, 32, 5)


def test_iter_frame_optical_flow_requires_both_output_dims_together() -> None:
    frame0, frame1 = _shifted_frame_pair()
    with pytest.raises(ValueError, match="output_width and output_height"):
        list(iter_frame_optical_flow(iter([frame0, frame1]), method="dis", output_width=32))


def test_extract_optical_flow_writes_a_valid_video(tmp_path) -> None:
    """The default (video) output is a real, valid video file."""
    out = extract_optical_flow(
        VIDEO_FIXTURE,
        str(tmp_path / "flow.mp4"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
    )
    assert out == str(tmp_path / "flow.mp4")
    assert is_valid_video_file(out)


def test_extract_optical_flow_writes_npy_with_flow_only_shape(tmp_path) -> None:
    """A '.npy' output path writes the raw (T, H, W, 2) float32 flow array."""
    out = extract_optical_flow(
        VIDEO_FIXTURE,
        str(tmp_path / "flow.npy"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
    )
    arr = np.load(out)
    assert arr.ndim == 4
    assert arr.shape[-1] == 2
    assert arr.dtype == np.float32
    np.testing.assert_array_equal(arr[0], 0.0)  # first frame has no previous frame


def test_extract_optical_flow_defaults_output_path(tmp_path) -> None:
    """Omitting output_path defaults to '<input>-flow.mp4' next to the source."""
    src = tmp_path / "clip.mp4"
    shutil.copy(VIDEO_FIXTURE, src)
    out = extract_optical_flow(str(src), method="dis", frame_step=5, end_instant=1.0)
    assert out == str(tmp_path / "clip-flow.mp4")
    assert is_valid_video_file(out)


def test_extract_optical_flow_no_overwrite_skips_recompute(tmp_path) -> None:
    """overwrite=False returns the existing path without recomputing."""
    out_path = tmp_path / "flow.mp4"
    extract_optical_flow(VIDEO_FIXTURE, str(out_path), frame_step=5, end_instant=1.0)
    mtime_before = out_path.stat().st_mtime_ns

    result = extract_optical_flow(
        VIDEO_FIXTURE, str(out_path), frame_step=5, end_instant=1.0, overwrite=False
    )
    assert result == str(out_path)
    assert out_path.stat().st_mtime_ns == mtime_before


def test_extract_optical_flow_resizes_npy_output(tmp_path) -> None:
    """output_width/output_height resize the written flow array via resize_flow."""
    pytest.importorskip("pywt")
    out = extract_optical_flow(
        VIDEO_FIXTURE,
        str(tmp_path / "flow.npy"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
        output_width=64,
        output_height=64,
    )
    arr = np.load(out)
    assert arr.shape[1:] == (64, 64, 2)


def test_extract_optical_flow_resizes_video_output(tmp_path) -> None:
    """output_width/output_height resize the HSV visualization video too."""
    pytest.importorskip("pywt")
    out = extract_optical_flow(
        VIDEO_FIXTURE,
        str(tmp_path / "flow.mp4"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
        output_width=64,
        output_height=64,
    )
    dims = video_dimensions(out)
    assert (dims["width"], dims["height"]) == (64, 64)


def test_extract_optical_flow_requires_both_output_dims_together(tmp_path) -> None:
    with pytest.raises(ValueError, match="output_width and output_height"):
        extract_optical_flow(
            VIDEO_FIXTURE,
            str(tmp_path / "flow.mp4"),
            frame_step=5,
            end_instant=1.0,
            output_width=64,
        )
