"""
Functional tests for ``video_helper.flow`` (dense optical flow generator).

Module summary
--------------
Exercises the two zero-dependency backends (``"dis"``, ``"farneback"``) on
synthetic, deterministic frame pairs with a known horizontal shift, checking
the output contract (shape/dtype, zero flow on frame 1, correct flow sign),
the ``clip_flow`` option, and the ``grayscale`` output layout. ``method="raft"``
is exercised only when ``torchvision`` is importable -- it also downloads
pretrained weights on first use, so it is opportunistic like the rest of this
repo's optional-dependency tests (see ``tests/test_asd_device.py``), never
required in CI. ``resize_flow`` (wavelet-based, needs ``PyWavelets``) is
likewise gated with ``pytest.importorskip("pywt")``. Tests drive full
method-by-method scenarios rather than one assertion per parametrized case,
so the suite's size tracks behaviors, not backend/method combinations.

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

_METHODS = ["dis", "farneback"]


def _require(path: str) -> str:
    """Return the fixture path, skipping the test if it does not exist."""
    if not osh.file_exists(path):
        pytest.skip(f"Fixture missing: {path}")
    return path


def _shifted_frame_pair(size: int = 64, shift: int = 4) -> tuple[np.ndarray, np.ndarray]:
    """Build two synthetic BGR frames: a bright block, then shifted right."""
    frame0 = np.zeros((size, size, 3), dtype=np.uint8)
    frame0[20:44, 20:44, :] = 255
    frame1 = np.zeros((size, size, 3), dtype=np.uint8)
    frame1[20:44, 20 + shift : 44 + shift, :] = 255
    return frame0, frame1


def test_output_contract_first_frame_and_shift_recovery() -> None:
    """For both zero-dependency methods: every yielded array is (H, W, 5)
    float32, frame 0 has exactly zero flow and matches the input frame, a
    block shifted right recovers a predominantly positive vx, and
    ``clip_flow`` symmetrically bounds the output without changing shape."""
    for method in _METHODS:
        frame0, frame1 = _shifted_frame_pair()
        out = list(iter_frame_optical_flow(iter([frame0, frame1]), method=method))

        assert len(out) == 2
        for arr in out:
            assert arr.shape == (64, 64, 5)
            assert arr.dtype == np.float32
        np.testing.assert_array_equal(out[0][..., 3:], 0.0)
        np.testing.assert_allclose(out[0][..., :3], frame0.astype(np.float32))

        vx = out[1][20:44, 24:40, 3]  # interior of the moved block, away from edges
        assert vx.mean() > 0.5, method  # moved right -> positive vx

    # clip_flow: bounds both channels without changing shape (dis only, cheap).
    frame0, frame1 = _shifted_frame_pair(size=64, shift=10)
    clipped = list(iter_frame_optical_flow(iter([frame0, frame1]), method="dis", clip_flow=0.5))
    assert clipped[1].shape == (64, 64, 5)
    assert np.abs(clipped[1][..., 3:]).max() <= 0.5 + 1e-6


def test_grayscale_mode_yields_3_channel_arrays_with_correct_flow() -> None:
    """grayscale=True yields (H, W, 3) -- intensity + vx + vy instead of
    (H, W, 5) -- with the same first-frame-zero and shift-recovery guarantees
    as full-color mode, for both zero-dependency methods."""
    for method in _METHODS:
        frame0, frame1 = _shifted_frame_pair(size=64, shift=4)
        out = list(iter_frame_optical_flow(iter([frame0, frame1]), method=method, grayscale=True))
        assert len(out) == 2
        for arr in out:
            assert arr.shape == (64, 64, 3)
            assert arr.dtype == np.float32

        expected_gray = cv2.cvtColor(frame0, cv2.COLOR_BGR2GRAY).astype(np.float32)
        np.testing.assert_allclose(out[0][..., 0], expected_gray)
        np.testing.assert_array_equal(out[0][..., 1:], 0.0)  # frame 0 still zero flow

        vx = out[1][20:44, 24:40, 1]
        assert vx.mean() > 0.5, method  # moved right -> positive vx


def test_dependency_and_input_validation_error_paths(monkeypatch) -> None:
    """Every 'clean error, not a crash' path in this module: an unknown flow
    method, RAFT without torchvision, and resize_flow without PyWavelets each
    raise the right exception type naming the missing/bad thing."""
    frame0, frame1 = _shifted_frame_pair()
    with pytest.raises(ValueError):
        list(iter_frame_optical_flow(iter([frame0, frame1]), method="bogus"))  # type: ignore[arg-type]

    import video_helper.flow as flow_mod

    monkeypatch.setattr(flow_mod, "_have_torchvision", lambda: False)
    with pytest.raises(ImportError, match="torchvision"):
        list(flow_mod.iter_frame_optical_flow(iter([frame0, frame1]), method="raft"))

    monkeypatch.setattr(flow_mod, "_have_pywt", lambda: False)
    with pytest.raises(ImportError, match="PyWavelets"):
        flow_mod.resize_flow(np.zeros((8, 8, 2), dtype=np.float32), output_width=4, output_height=4)


def test_raft_recovers_shift_in_color_and_grayscale_modes() -> None:
    """Opportunistic: only runs when torchvision is importable (downloads
    weights on first use). RAFT still computes flow from the full-color
    pair, but honors grayscale=True on output."""
    pytest.importorskip("torchvision")
    frame0, frame1 = _shifted_frame_pair(size=136, shift=8)  # RAFT needs >= ~128px per side

    color = list(
        iter_frame_optical_flow(
            iter([frame0, frame1]), method="raft", raft_variant="small", device="cpu"
        )
    )
    assert color[1].shape == (136, 136, 5)
    assert color[1].dtype == np.float32
    np.testing.assert_array_equal(color[0][..., 3:], 0.0)
    assert color[1][20:44, 24:40, 3].mean() > 0.5

    gray = list(
        iter_frame_optical_flow(
            iter([frame0, frame1]),
            method="raft",
            raft_variant="small",
            device="cpu",
            grayscale=True,
        )
    )
    assert gray[1].shape == (136, 136, 3)
    assert gray[1][20:44, 24:40, 1].mean() > 0.5


def _step_flow(size: int = 64, magnitude: float = 10.0) -> np.ndarray:
    """A (size, size, 2) flow field with a hard vx discontinuity down the middle."""
    flow = np.zeros((size, size, 2), dtype=np.float32)
    flow[:, size // 2 :, 0] = magnitude
    return flow


def test_resize_flow_shape_dtype_and_identity() -> None:
    """resize_flow produces the requested (H, W, 2) float32 shape, and
    resizing to the same size is a true identity (no interpolation noise)."""
    pytest.importorskip("pywt")
    flow = _step_flow()
    out = resize_flow(flow, output_width=32, output_height=40)
    assert out.shape == (40, 32, 2)
    assert out.dtype == np.float32

    identity = resize_flow(flow, output_width=64, output_height=64)
    np.testing.assert_array_equal(identity, flow)


def test_resize_flow_rescales_magnitude_and_clips_ringing() -> None:
    """An upsampled uniform flow field has its displacement values scaled by
    the same factor as the spatial resize; a downsampled hard-step field
    never rings past the source value range (wavelet reconstruction can
    overshoot at a discontinuity -- must be clipped)."""
    pytest.importorskip("pywt")
    uniform = np.full((32, 32, 2), 5.0, dtype=np.float32)
    upsampled = resize_flow(uniform, output_width=64, output_height=64)
    np.testing.assert_allclose(upsampled, 10.0, atol=1e-3)  # 2x upsample -> 2x magnitude

    step = _step_flow(size=64, magnitude=10.0)
    down = resize_flow(step, output_width=32, output_height=32)
    assert down[..., 0].min() >= 0.0
    assert down[..., 0].max() <= 10.0 + 1e-4


def test_resize_flow_rejects_invalid_input() -> None:
    """resize_flow validates channel count and target-dimension positivity."""
    pytest.importorskip("pywt")
    with pytest.raises(ValueError, match="H, W, 2"):
        resize_flow(np.zeros((8, 8, 3), dtype=np.float32), output_width=4, output_height=4)
    with pytest.raises(ValueError, match="positive"):
        resize_flow(_step_flow(), output_width=0, output_height=4)


def test_iter_frame_optical_flow_output_size_wired_to_resize_flow() -> None:
    """output_width/output_height resize both the image and flow channels via
    resize_flow; omitting one of the pair is a validation error."""
    pytest.importorskip("pywt")
    frame0, frame1 = _shifted_frame_pair(size=64, shift=4)
    out = list(
        iter_frame_optical_flow(
            iter([frame0, frame1]), method="dis", output_width=32, output_height=32
        )
    )
    assert out[0].shape == (32, 32, 5)
    assert out[1].shape == (32, 32, 5)

    with pytest.raises(ValueError, match="output_width and output_height"):
        list(iter_frame_optical_flow(iter([frame0, frame1]), method="dis", output_width=32))


def test_extract_optical_flow_writes_video_and_npy(tmp_path) -> None:
    """Output kind is inferred from the extension: '.mp4' writes a valid
    HSV-visualization video, '.npy' writes the raw (T, H, W, 2) float32 flow
    array whose first frame has zero flow (no previous frame)."""
    video_out = extract_optical_flow(
        _require(VIDEO_FIXTURE),
        str(tmp_path / "flow.mp4"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
    )
    assert video_out == str(tmp_path / "flow.mp4")
    assert is_valid_video_file(video_out)

    npy_out = extract_optical_flow(
        _require(VIDEO_FIXTURE),
        str(tmp_path / "flow.npy"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
    )
    arr = np.load(npy_out)
    assert arr.ndim == 4
    assert arr.shape[-1] == 2
    assert arr.dtype == np.float32
    np.testing.assert_array_equal(arr[0], 0.0)


def test_extract_optical_flow_default_output_path_and_overwrite_skip(tmp_path) -> None:
    """Omitting output_path defaults to '<input>-flow.mp4' next to the
    source; overwrite=False returns the existing path without recomputing."""
    src = tmp_path / "clip.mp4"
    shutil.copy(_require(VIDEO_FIXTURE), src)
    out = extract_optical_flow(str(src), method="dis", frame_step=5, end_instant=1.0)
    assert out == str(tmp_path / "clip-flow.mp4")
    assert is_valid_video_file(out)

    mtime_before = os.stat(out).st_mtime_ns
    result = extract_optical_flow(
        str(src), method="dis", frame_step=5, end_instant=1.0, overwrite=False
    )
    assert result == out
    assert os.stat(out).st_mtime_ns == mtime_before


def test_extract_optical_flow_resizes_both_output_kinds(tmp_path) -> None:
    """output_width/output_height resize the written flow array (.npy) and
    the HSV visualization video (.mp4) identically, and requiring both dims
    together is enforced for the file-level wrapper too."""
    pytest.importorskip("pywt")
    fixture = _require(VIDEO_FIXTURE)

    npy_out = extract_optical_flow(
        fixture,
        str(tmp_path / "flow.npy"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
        output_width=64,
        output_height=64,
    )
    arr = np.load(npy_out)
    assert arr.shape[1:] == (64, 64, 2)

    video_out = extract_optical_flow(
        fixture,
        str(tmp_path / "flow.mp4"),
        method="dis",
        frame_step=5,
        end_instant=1.0,
        output_width=64,
        output_height=64,
    )
    dims = video_dimensions(video_out)
    assert (dims["width"], dims["height"]) == (64, 64)

    with pytest.raises(ValueError, match="output_width and output_height"):
        extract_optical_flow(
            fixture, str(tmp_path / "flow2.mp4"), frame_step=5, end_instant=1.0, output_width=64
        )
