"""
video_helper.flow
==================

Optional dense-optical-flow generator that wraps any BGR frame stream.

Module summary
--------------
Exposes a single public generator, :func:`iter_frame_optical_flow`, which takes any
``Iterator[numpy.ndarray]`` of ``(H, W, 3)`` BGR uint8 frames — the same
contract already produced by :func:`video_helper.extract_frames` and by
``capture_helper.iter_camera_frames`` (live camera) — and re-yields each frame
with 2 extra channels: dense optical flow ``vx``/``vy`` relative to the
previous frame. Taking a generic frame iterator rather than a video path is
the deliberate composability point: this module works identically for a video
file or a live camera, without a hard dependency on either. Two output
layouts, picked with ``grayscale``: ``(H, W, 5)`` BGR + flow (default) or
``(H, W, 3)`` grayscale intensity + flow (smaller, motion-focused).

Three interchangeable backends, from zero-dependency classical to optional
deep learning:

- ``method="dis"`` (default) — ``cv2.DISOpticalFlow``, the standard
  best CPU real-time speed/quality trade-off. No new dependency:
  ``opencv-python`` is already a core dependency of video-helper.
- ``method="farneback"`` — ``cv2.calcOpticalFlowFarneback``. Also core cv2,
  no new dependency. Denser/smoother field, a bit slower than DIS.
- ``method="raft"`` — ``torchvision.models.optical_flow.{raft_small,raft_large}``,
  a real deep-learning optical-flow network. Needs the ``[flow]`` extra
  (torch + torchvision). Quality-first, GPU-recommended; not expected to be
  real-time on CPU.

Usage Example
-------------
>>> import video_helper as vh
>>> frames = vh.extract_frames("clip.mp4", frame_step=1)
>>> for flow_frame in vh.iter_frame_optical_flow(frames, method="dis"):
...     # flow_frame.shape == (H, W, 5), float32
...     bgr = flow_frame[..., :3].astype("uint8")
...     vx, vy = flow_frame[..., 3], flow_frame[..., 4]

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Literal

import cv2
import numpy as np
import os_helper as osh

from .main import dump_frames, extract_frames, is_valid_video_file, video_dimensions


def _have_torchvision() -> bool:
    """Return whether the optional ``torchvision`` (``[flow]`` extra) is importable.

    Returns
    -------
    bool
        ``True`` when ``import torchvision`` succeeds, ``False`` otherwise. Used
        to gate ``method="raft"`` without hard-depending on torch/torchvision.
    """
    # Same import-probe strategy as ``video_helper.main._have_torch``.
    try:
        import torchvision  # noqa: F401

        return True
    except ImportError:
        return False


def _dis_preset_flag(preset: Literal["ultrafast", "fast", "medium"]) -> int:
    """Translate a ``dis_preset`` string into the matching ``cv2`` preset constant.

    Parameters
    ----------
    preset : {"ultrafast", "fast", "medium"}
        Speed/quality preset name for :func:`cv2.DISOpticalFlow_create`.

    Returns
    -------
    int
        The corresponding ``cv2.DISOPTICAL_FLOW_PRESET_*`` constant.

    Raises
    ------
    ValueError
        If ``preset`` is not one of the three supported names.

    Examples
    --------
    >>> _dis_preset_flag("fast") == cv2.DISOPTICAL_FLOW_PRESET_FAST
    True
    """
    flags = {
        "ultrafast": cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST,
        "fast": cv2.DISOPTICAL_FLOW_PRESET_FAST,
        "medium": cv2.DISOPTICAL_FLOW_PRESET_MEDIUM,
    }
    if preset not in flags:
        raise ValueError(f"Unknown dis_preset {preset!r}; expected one of {sorted(flags)}")
    return flags[preset]


def _dis_flow(
    prev_gray: np.ndarray,
    gray: np.ndarray,
    estimator: cv2.DISOpticalFlow,
) -> np.ndarray:
    """Compute one DIS optical-flow field between two grayscale frames.

    Parameters
    ----------
    prev_gray : numpy.ndarray
        Previous frame, ``(H, W)`` uint8 grayscale.
    gray : numpy.ndarray
        Current frame, ``(H, W)`` uint8 grayscale.
    estimator : cv2.DISOpticalFlow
        Pre-constructed DIS estimator (built once outside the per-frame loop).

    Returns
    -------
    numpy.ndarray
        Flow field ``(H, W, 2)`` float32, channels ``[vx, vy]``.
    """
    return estimator.calc(prev_gray, gray, None)


def _farneback_flow(prev_gray: np.ndarray, gray: np.ndarray) -> np.ndarray:
    """Compute one Farneback optical-flow field between two grayscale frames.

    Parameters
    ----------
    prev_gray : numpy.ndarray
        Previous frame, ``(H, W)`` uint8 grayscale.
    gray : numpy.ndarray
        Current frame, ``(H, W)`` uint8 grayscale.

    Returns
    -------
    numpy.ndarray
        Flow field ``(H, W, 2)`` float32, channels ``[vx, vy]``.
    """
    # Parameters mirror OpenCV's own documented defaults/examples for
    # calcOpticalFlowFarneback — a reasonable general-purpose setting, not
    # tuned per-use-case (users who need different behaviour should call
    # cv2 directly).
    return cv2.calcOpticalFlowFarneback(prev_gray, gray, None, 0.5, 3, 15, 3, 5, 1.2, 0)


def _pad_to_multiple(frame: np.ndarray, multiple: int) -> tuple[np.ndarray, int, int]:
    """Pad a HWC frame so H and W are both divisible by ``multiple``.

    RAFT (and torchvision's implementation) requires input spatial dims
    divisible by 8; torchvision does not ship the original RAFT repo's
    ``InputPadder`` helper, so video-helper provides its own.

    Parameters
    ----------
    frame : numpy.ndarray
        Frame ``(H, W, C)``, any dtype.
    multiple : int
        Required divisor for both H and W (8 for RAFT).

    Returns
    -------
    tuple[numpy.ndarray, int, int]
        ``(padded_frame, orig_h, orig_w)`` — the padded frame (bottom/right
        replicate-padding) plus the original height/width so callers can crop
        the flow back down with :func:`_unpad_flow`.

    Examples
    --------
    >>> frame = np.zeros((5, 5, 3), dtype=np.uint8)
    >>> padded, h, w = _pad_to_multiple(frame, 8)
    >>> padded.shape
    (8, 8, 3)
    >>> (h, w)
    (5, 5)
    """
    h, w = frame.shape[:2]
    pad_h = (-h) % multiple
    pad_w = (-w) % multiple
    if pad_h == 0 and pad_w == 0:
        return frame, h, w
    padded = cv2.copyMakeBorder(frame, 0, pad_h, 0, pad_w, cv2.BORDER_REPLICATE)
    return padded, h, w


def _unpad_flow(flow: np.ndarray, orig_h: int, orig_w: int) -> np.ndarray:
    """Crop a flow field computed on a padded frame back down to its original size.

    Parameters
    ----------
    flow : numpy.ndarray
        Flow field ``(H_padded, W_padded, 2)``.
    orig_h : int
        Original (pre-padding) frame height.
    orig_w : int
        Original (pre-padding) frame width.

    Returns
    -------
    numpy.ndarray
        Flow field cropped to ``(orig_h, orig_w, 2)``.
    """
    return flow[:orig_h, :orig_w, :]


def _have_pywt() -> bool:
    """Return whether the optional ``PyWavelets`` (``[flow]`` extra) is importable.

    Returns
    -------
    bool
        ``True`` when ``import pywt`` succeeds, ``False`` otherwise. Used to
        gate :func:`resize_flow` without hard-depending on PyWavelets.
    """
    # Same import-probe strategy as ``_have_torchvision``.
    try:
        import pywt  # noqa: F401

        return True
    except ImportError:
        return False


def _wavelet_resize_channel(
    channel: np.ndarray, target_h: int, target_w: int, wavelet: str
) -> np.ndarray:
    """Resize one 2-D float channel via wavelet decomposition, edge-aware.

    Naive bilinear/bicubic resizing linearly blends across a discontinuity
    (e.g. a motion boundary in an optical-flow field), smearing a sharp jump
    into a ramp spread over several pixels. This helper instead does as much
    of the resize as possible in the wavelet domain:

    - **Downsampling**: repeated single-level 2-D DWT, keeping only the ``LL``
      (approximation) subband at each step — the wavelet lowpass has a
      cleaner frequency response than a box filter, reducing the ringing/
      aliasing that naive area-averaging introduces near a step edge.
    - **Upsampling**: repeated single-level 2-D IDWT with the current data as
      the ``LL`` band and **zero** detail (``LH``/``HL``/``HH``) coefficients
      — the standard "wavelet interpolation" construction. On smooth regions
      this reconstructs comparably to bilinear; near a discontinuity it does
      not invent an artificial in-between value the way a linear kernel does.
    - Both loops use ``mode="periodization"`` so each step is an *exact*
      halving / doubling of the array size (no boundary-effect growth).

    Only handles the portion of the resize that is an integer power-of-two
    ratio in both axes. Whatever ratio is left over (always < 2x, and the
    whole resize when the axes need to move in opposite directions, e.g.
    upsampling one axis while downsampling the other) is finished with a
    single **nearest-neighbor** snap to the exact target size — nearest-
    neighbor re-samples existing values without blending, so it cannot
    introduce a new intermediate value at a discontinuity the way linear/
    cubic interpolation would.

    Honest caveat, verified empirically rather than assumed: an orthogonal
    wavelet like ``"db2"`` does **not** avoid the Gibbs phenomenon — right at
    a hard step it rings, overshooting a few percent past the original
    min/max on either side (e.g. dipping slightly negative next to a
    ``[0, 10]`` step). That is worse than bilinear, which is a convex
    combination and can never leave the source range. To get a real net win
    over bilinear at discontinuities — reduced smearing *without* introducing
    out-of-range values — every result is clipped back to ``[channel.min(),
    channel.max()]`` before returning.

    Parameters
    ----------
    channel : numpy.ndarray
        Single channel, ``(H, W)``, any float dtype.
    target_h : int
        Target height in pixels.
    target_w : int
        Target width in pixels.
    wavelet : str
        A PyWavelets wavelet name (e.g. ``"db2"``, ``"haar"``, ``"bior2.2"``).

    Returns
    -------
    numpy.ndarray
        ``(target_h, target_w)`` float32.

    Examples
    --------
    >>> import numpy as np
    >>> step = np.zeros((16, 16)); step[:, 8:] = 10.0  # a hard discontinuity
    >>> out = _wavelet_resize_channel(step, 8, 8, "db2")
    >>> out.shape
    (8, 8)
    """
    import pywt  # lazy — only needed when a resize is actually requested

    lo, hi = float(channel.min()), float(channel.max())
    cur = channel.astype(np.float64)
    cur_h, cur_w = cur.shape

    while cur_h >= 2 * target_h and cur_w >= 2 * target_w and cur_h > 1 and cur_w > 1:
        cur, _ = pywt.dwt2(cur, wavelet, mode="periodization")
        cur_h, cur_w = cur.shape

    while cur_h * 2 <= target_h and cur_w * 2 <= target_w:
        zeros = np.zeros_like(cur)
        cur = pywt.idwt2((cur, (zeros, zeros, zeros)), wavelet, mode="periodization")
        cur_h, cur_w = cur.shape

    if (cur_h, cur_w) != (target_h, target_w):
        cur = cv2.resize(
            cur.astype(np.float32), (target_w, target_h), interpolation=cv2.INTER_NEAREST
        )

    # Orthogonal wavelets ring past the source range at hard discontinuities
    # (Gibbs phenomenon) — clip back so a resize can never invent a flow
    # magnitude the source never had (see the "Honest caveat" above).
    return np.clip(cur, lo, hi).astype(np.float32)


def resize_flow(
    flow: np.ndarray,
    output_width: int,
    output_height: int,
    *,
    wavelet: str = "db2",
) -> np.ndarray:
    """Resize a dense optical-flow field, preserving motion discontinuities.

    Applies :func:`_wavelet_resize_channel` to ``vx`` and ``vy``
    independently, then rescales the displacement *magnitudes* by the same
    factor as the spatial resize — a flow field encodes physical pixel
    displacement, so "5px right" at the original resolution must become
    "10px right" after a 2x upsample, exactly like rescaling a velocity when
    changing units. Skipping this step is a common, silent correctness bug
    in flow-resizing code (frame-only resizing tools like ``cv2.resize``
    don't know to do it, since a plain image has no such physical meaning).

    This is specifically for the 2-channel ``vx``/``vy`` flow itself — for
    the BGR/grayscale image channels, standard interpolation (e.g.
    ``extract_frames``'s own ``output_width``/``output_height``) is the
    right tool; there is no discontinuity-preservation concern for color.

    Parameters
    ----------
    flow : numpy.ndarray
        Flow field ``(H, W, 2)`` float, channels ``[vx, vy]`` — e.g. the last
        2 channels of an :func:`iter_frame_optical_flow` output frame.
    output_width : int
        Target width in pixels.
    output_height : int
        Target height in pixels.
    wavelet : str, default "db2"
        A PyWavelets wavelet name. ``"db2"`` (Daubechies-2) is a reasonable
        default — smoother reconstruction than ``"haar"`` (which is blocky)
        without the longer-filter ringing of higher-order wavelets.

    Returns
    -------
    numpy.ndarray
        ``(output_height, output_width, 2)`` float32, magnitude-rescaled.

    Raises
    ------
    ValueError
        If ``flow`` is not ``(H, W, 2)``, or ``output_width``/``output_height``
        is not a positive integer.
    ImportError
        If ``PyWavelets`` is not installed (install with
        ``pip install "video-helper[flow]"``).

    Examples
    --------
    >>> import numpy as np
    >>> flow = np.zeros((64, 64, 2), dtype=np.float32)
    >>> flow[:, 32:, 0] = 5.0  # a hard motion boundary: 5px/frame rightward
    >>> resized = resize_flow(flow, output_width=32, output_height=32)
    >>> resized.shape
    (32, 32, 2)

    Notes
    -----
    Only the portion of the resize that is an integer power-of-two ratio
    (in both axes together) goes through the wavelet transform; the
    remainder (always < 2x, and the whole resize for a mixed up/down-sample
    across axes) falls back to a single nearest-neighbor snap — see
    :func:`_wavelet_resize_channel` for the full rationale.
    """
    if not _have_pywt():
        raise ImportError(
            "resize_flow requires PyWavelets. Install with: "
            "pip install 'video-helper[flow]' (or bring your own pywt)"
        )
    if flow.ndim != 3 or flow.shape[-1] != 2:
        raise ValueError(f"flow must be (H, W, 2), got shape {flow.shape}")
    if output_width < 1 or output_height < 1:
        raise ValueError(
            f"output_width/output_height must be positive, got {output_width}x{output_height}"
        )

    src_h, src_w = flow.shape[:2]
    if (src_h, src_w) == (output_height, output_width):
        return flow.astype(np.float32, copy=True)

    vx = _wavelet_resize_channel(flow[..., 0], output_height, output_width, wavelet)
    vy = _wavelet_resize_channel(flow[..., 1], output_height, output_width, wavelet)
    vx *= output_width / src_w
    vy *= output_height / src_h
    return np.stack([vx, vy], axis=-1).astype(np.float32)


class _RaftFlowEstimator:
    """Lazily-built, reusable RAFT model + preprocessing transform.

    Constructed once outside the per-frame loop (loading the torchvision
    model and moving it to ``device`` is expensive); each frame pair only
    pays for the forward pass.

    Parameters
    ----------
    variant : {"small", "large"}
        ``raft_small`` (speed-favoring) or ``raft_large`` (quality-favoring).
    device : str
        Torch device string ("cpu", "mps", "cuda", or "auto").

    Attributes
    ----------
    model : torch.nn.Module
        The loaded, eval-mode RAFT network.
    transforms : Callable
        The weights' paired-image preprocessing transform.
    device : torch.device
        Resolved concrete device the model lives on.
    """

    def __init__(self, variant: Literal["small", "large"], device: str) -> None:
        import torch
        from torchvision.models.optical_flow import (
            Raft_Large_Weights,
            Raft_Small_Weights,
            raft_large,
            raft_small,
        )

        from .main import _resolve_torch_device  # lazy — avoid a torch import at module load

        self.device = _resolve_torch_device(device)
        if variant == "small":
            weights = Raft_Small_Weights.DEFAULT
            self.model = raft_small(weights=weights, progress=False)
        elif variant == "large":
            weights = Raft_Large_Weights.DEFAULT
            self.model = raft_large(weights=weights, progress=False)
        else:
            raise ValueError(f"Unknown raft_variant {variant!r}; expected 'small' or 'large'")
        self.model = self.model.to(self.device).eval()
        self.transforms = weights.transforms()
        self._torch = torch

    def flow(self, prev_bgr: np.ndarray, bgr: np.ndarray) -> np.ndarray:
        """Estimate dense optical flow between two padded BGR frames.

        Parameters
        ----------
        prev_bgr : numpy.ndarray
            Previous frame, ``(H, W, 3)`` BGR uint8, H/W divisible by 8.
        bgr : numpy.ndarray
            Current frame, ``(H, W, 3)`` BGR uint8, H/W divisible by 8.

        Returns
        -------
        numpy.ndarray
            Flow field ``(H, W, 2)`` float32, channels ``[vx, vy]``.
        """
        from .main import _bgr_hwc_to_torch_chw_rgb  # lazy — mirrors main.py's own reuse

        torch = self._torch
        img1 = _bgr_hwc_to_torch_chw_rgb(prev_bgr, self.device).unsqueeze(0)
        img2 = _bgr_hwc_to_torch_chw_rgb(bgr, self.device).unsqueeze(0)
        img1, img2 = self.transforms(img1, img2)
        with torch.no_grad():
            list_of_flows = self.model(img1, img2)
        # Last iterative-refinement step is the network's best estimate.
        predicted_flow = list_of_flows[-1][0]  # (2, H, W)
        return predicted_flow.permute(1, 2, 0).contiguous().cpu().numpy().astype(np.float32)


def iter_frame_optical_flow(
    frames: Iterator[np.ndarray],
    *,
    method: Literal["dis", "farneback", "raft"] = "dis",
    dis_preset: Literal["ultrafast", "fast", "medium"] = "fast",
    raft_variant: Literal["small", "large"] = "small",
    device: str = "cpu",
    clip_flow: float | None = None,
    grayscale: bool = False,
    output_width: int | None = None,
    output_height: int | None = None,
    wavelet: str = "db2",
) -> Iterator[np.ndarray]:
    """Re-yield a BGR frame stream with 2 extra dense-optical-flow channels.

    Wraps any ``(H, W, 3)`` BGR uint8 frame iterator — :func:`video_helper.extract_frames`
    output, ``capture_helper.iter_camera_frames`` output, or any other source
    sharing that contract — and yields either ``(H, W, 5)`` float32 arrays
    (default: BGR frame + flow) or ``(H, W, 3)`` float32 arrays
    (``grayscale=True``: single-channel intensity + flow). In both layouts
    the last 2 channels are always per-pixel flow ``vx``/``vy`` relative to
    the previous frame.

    Parameters
    ----------
    frames : Iterator[numpy.ndarray]
        Source frames, each ``(H, W, 3)`` BGR uint8 (OpenCV convention).
    method : {"dis", "farneback", "raft"}, default "dis"
        Optical-flow backend. ``"dis"`` and ``"farneback"`` use only
        ``opencv-python`` (already a core dependency, no extra install).
        ``"raft"`` is a deep-learning estimator that needs the ``[flow]``
        extra (``pip install "video-helper[flow]"``) and is quality-first /
        GPU-recommended — CPU RAFT is not expected to run in real time.
    dis_preset : {"ultrafast", "fast", "medium"}, default "fast"
        Speed/quality preset for ``method="dis"``. Ignored otherwise.
    raft_variant : {"small", "large"}, default "small"
        ``raft_small`` (speed-favoring) or ``raft_large`` (quality-favoring).
        Only used for ``method="raft"``. RAFT's correlation pyramid needs
        feature maps at least 16px wide after an internal 8x downsample, so
        frames smaller than ~128x128 raise inside torchvision — not a
        video-helper limitation, but worth knowing before wrapping small
        crops/thumbnails.
    device : str, default "cpu"
        Torch device for ``method="raft"`` only: ``"cpu"``, ``"mps"``,
        ``"cuda"``, or ``"auto"`` (best available). Ignored for ``"dis"``/
        ``"farneback"``, which are CPU-only OpenCV calls.
    clip_flow : float or None, default None
        When set, symmetrically clip both ``vx`` and ``vy`` to
        ``[-clip_flow, clip_flow]`` pixels — suppresses rare outlier vectors
        (e.g. at scene cuts) without changing the array shape/dtype.
    grayscale : bool, default False
        When ``True``, yield ``(H, W, 3)`` arrays (grayscale intensity + flow)
        instead of the default ``(H, W, 5)`` (BGR + flow) — a smaller,
        motion-focused representation for callers that don't need color
        (e.g. feeding a flow-only model). RAFT still computes flow from the
        full-color frame pair regardless of this flag; it only changes what
        gets written to the non-flow output channel(s).
    output_width : int, optional
        Resize each yielded frame to this width. Must be given together with
        ``output_height`` (no aspect-preserving/padding mode here — for that,
        pre-resize ``frames`` itself via ``extract_frames(output_width=...,
        output_height=...)`` so flow is computed directly at the target
        resolution). This parameter is for the different case of resizing an
        *already-computed* flow field — e.g. computing flow at full quality
        then shrinking for storage, or computing cheaply at low resolution
        and upsampling for display. The image channel(s) are resized with
        standard bilinear interpolation (no discontinuity concern for
        color/intensity); the flow channels go through :func:`resize_flow`
        (wavelet-based, magnitude-rescaled, discontinuity-aware).
    output_height : int, optional
        Resize each yielded frame to this height. See ``output_width``.
    wavelet : str, default "db2"
        PyWavelets wavelet name forwarded to :func:`resize_flow`. Ignored
        unless ``output_width``/``output_height`` are set.

    Yields
    ------
    numpy.ndarray
        ``grayscale=False`` (default): ``(H, W, 5)`` float32 array per input
        frame. ``[..., :3]`` is the BGR frame cast to float32 (values 0-255 —
        ``.astype(np.uint8)`` recovers the plain image); ``[..., 3]`` is
        ``vx``, ``[..., 4]`` is ``vy``. ``grayscale=True``: ``(H, W, 3)``
        float32; ``[..., 0]`` is grayscale intensity, ``[..., 1]`` is ``vx``,
        ``[..., 2]`` is ``vy``. Either way flow is signed pixel displacement,
        and the first yielded frame has zero flow (no previous frame yet),
        keeping frame count 1:1 with ``frames``.

    Raises
    ------
    ValueError
        If ``method``, ``dis_preset``, or ``raft_variant`` is not a supported
        value, or if exactly one of ``output_width``/``output_height`` is
        given without the other.
    ImportError
        If ``method="raft"`` is requested but ``torchvision`` is not
        installed, or if ``output_width``/``output_height`` are requested
        but ``PyWavelets`` is not installed (install either with
        ``pip install "video-helper[flow]"``).

    Examples
    --------
    >>> import video_helper as vh
    >>> frames = vh.extract_frames("clip.mp4", frame_step=1)
    >>> for flow_frame in vh.iter_frame_optical_flow(frames, method="dis"):
    ...     bgr = flow_frame[..., :3].astype("uint8")
    ...     vx, vy = flow_frame[..., 3], flow_frame[..., 4]
    ...     break
    >>> for flow_frame in vh.iter_frame_optical_flow(frames, method="dis", grayscale=True):
    ...     gray = flow_frame[..., 0].astype("uint8")
    ...     vx, vy = flow_frame[..., 1], flow_frame[..., 2]
    ...     break

    Notes
    -----
    Composability is the point: this function takes a generic frame iterator
    rather than a video path, so it works identically wrapping
    ``video_helper.extract_frames(...)`` (file) or
    ``capture_helper.iter_camera_frames(...)`` (live camera) — both already
    share the same ``(H, W, 3)`` BGR uint8 contract.
    """
    if method not in ("dis", "farneback", "raft"):
        raise ValueError(f"Unknown method {method!r}; expected 'dis', 'farneback', or 'raft'")
    if (output_width is None) != (output_height is None):
        raise ValueError(
            "output_width and output_height must be given together (got "
            f"output_width={output_width!r}, output_height={output_height!r})"
        )

    # Build the (potentially expensive) estimator object once, outside the
    # per-frame loop below.
    dis_estimator: cv2.DISOpticalFlow | None = None
    raft_estimator: _RaftFlowEstimator | None = None
    if method == "dis":
        dis_estimator = cv2.DISOpticalFlow_create(_dis_preset_flag(dis_preset))
    elif method == "raft":
        if not _have_torchvision():
            raise ImportError(
                "method='raft' requires torchvision. Install with: "
                "pip install 'video-helper[flow]' (or bring your own torch/torchvision)"
            )
        raft_estimator = _RaftFlowEstimator(raft_variant, device)

    n_channels = 3 if grayscale else 5
    prev_gray: np.ndarray | None = None
    prev_bgr_padded: np.ndarray | None = None
    for frame in frames:
        h, w = frame.shape[:2]
        out = np.empty((h, w, n_channels), dtype=np.float32)
        if grayscale:
            out[..., 0] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        else:
            out[..., :3] = frame.astype(np.float32)

        if method == "raft":
            padded, orig_h, orig_w = _pad_to_multiple(frame, 8)
            if prev_bgr_padded is None:
                out[..., -2:] = 0.0
            else:
                flow = raft_estimator.flow(prev_bgr_padded, padded)
                flow = _unpad_flow(flow, orig_h, orig_w)
                out[..., -2] = flow[..., 0]
                out[..., -1] = flow[..., 1]
            prev_bgr_padded = padded
        else:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            if prev_gray is None:
                out[..., -2:] = 0.0
            else:
                if method == "dis":
                    flow = _dis_flow(prev_gray, gray, dis_estimator)
                else:  # "farneback"
                    flow = _farneback_flow(prev_gray, gray)
                out[..., -2] = flow[..., 0]
                out[..., -1] = flow[..., 1]
            prev_gray = gray

        if clip_flow is not None:
            np.clip(out[..., -2:], -clip_flow, clip_flow, out=out[..., -2:])

        if output_width is not None:
            img = cv2.resize(
                out[..., :-2], (output_width, output_height), interpolation=cv2.INTER_LINEAR
            )
            if img.ndim == 2:  # cv2.resize squeezes a single-channel (H, W, 1) input
                img = img[..., np.newaxis]
            flow_resized = resize_flow(out[..., -2:], output_width, output_height, wavelet=wavelet)
            out = np.concatenate([img, flow_resized], axis=-1)

        yield out


def _flow_to_rgb(vx: np.ndarray, vy: np.ndarray) -> np.ndarray:
    """Render a flow field as an HSV-color-wheel RGB image (OpenCV's standard convention).

    Direction maps to hue, magnitude to value (per-frame min-max normalized),
    saturation is fixed at maximum — the same encoding as OpenCV's own dense
    optical-flow tutorial. Output is RGB (not BGR) so it can be handed
    straight to :func:`video_helper.main.dump_frames`, which expects RGB.

    Parameters
    ----------
    vx : numpy.ndarray
        Horizontal flow component, ``(H, W)`` float32.
    vy : numpy.ndarray
        Vertical flow component, ``(H, W)`` float32.

    Returns
    -------
    numpy.ndarray
        ``(H, W, 3)`` RGB uint8 visualization.
    """
    mag, ang = cv2.cartToPolar(vx, vy)
    hsv = np.zeros((*vx.shape, 3), dtype=np.uint8)
    hsv[..., 0] = ang * (90.0 / np.pi)  # radians -> OpenCV's 0-179 hue range
    hsv[..., 1] = 255
    hsv[..., 2] = cv2.normalize(mag, None, 0, 255, cv2.NORM_MINMAX)
    return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)


def extract_optical_flow(
    input_video: str,
    output_path: str | None = None,
    *,
    method: Literal["dis", "farneback", "raft"] = "dis",
    dis_preset: Literal["ultrafast", "fast", "medium"] = "fast",
    raft_variant: Literal["small", "large"] = "small",
    device: str = "cpu",
    clip_flow: float | None = None,
    start_instant: float | None = None,
    end_instant: float | None = None,
    frame_step: int = 1,
    frame_interval: float | None = None,
    fps: float | None = None,
    output_width: int | None = None,
    output_height: int | None = None,
    wavelet: str = "db2",
    overwrite: bool = True,
) -> str:
    """Compute dense optical flow over a video file and write it to disk.

    File-level convenience wrapper around :func:`iter_frame_optical_flow` for the
    common "just give me flow for this video" case (CLI / API surfaces need a
    single input path and a single output path, not a frame iterator). The
    output kind is inferred from ``output_path``'s extension, mirroring how
    :func:`video_helper.main.video_converter` infers its container:

    - ``.npy`` — the raw flow-only array, ``(T, H, W, 2)`` float32 (``vx``,
      ``vy``), one entry per input frame (frame 1 is all zeros).
    - anything else (default ``.mp4``) — an HSV-color-wheel visualization
      video (direction -> hue, magnitude -> value, see :func:`_flow_to_rgb`),
      viewable directly without loading numpy.

    Parameters
    ----------
    input_video : str
        Path to the source video.
    output_path : str, optional
        Where to write the result. Defaults to ``<input>-flow.mp4`` next to
        the source. Extension controls the output kind (see above).
    method : {"dis", "farneback", "raft"}, default "dis"
        Optical-flow backend — see :func:`iter_frame_optical_flow`.
    dis_preset : {"ultrafast", "fast", "medium"}, default "fast"
        Speed/quality preset for ``method="dis"``. Ignored otherwise.
    raft_variant : {"small", "large"}, default "small"
        RAFT network variant. Only used for ``method="raft"``.
    device : str, default "cpu"
        Torch device for ``method="raft"`` only.
    clip_flow : float or None, default None
        Symmetric pixel clip for outlier suppression — see
        :func:`iter_frame_optical_flow`.
    start_instant : float, optional
        Start time in seconds (forwarded to :func:`video_helper.main.extract_frames`).
    end_instant : float, optional
        End time in seconds (forwarded to :func:`video_helper.main.extract_frames`).
    frame_step : int, default 1
        Take every Nth frame (forwarded to :func:`video_helper.main.extract_frames`).
    frame_interval : float, optional
        Sample one frame every N seconds (forwarded to
        :func:`video_helper.main.extract_frames`; mutually exclusive with
        ``frame_step`` there).
    fps : float, optional
        Frame rate for the ``.mp4`` visualization output. Defaults to the
        source video's probed frame rate divided by ``frame_step`` (ignored
        for ``.npy`` output, and only a rough estimate when ``frame_interval``
        is used instead of ``frame_step``).
    output_width : int, optional
        Resize the flow field (not the source frames) to this width before
        writing — e.g. a smaller ``.npy`` for storage, or a smaller
        visualization video. Must be given together with ``output_height``.
        Goes through :func:`resize_flow` (wavelet-based, magnitude-rescaled,
        discontinuity-aware) rather than plain interpolation.
    output_height : int, optional
        Resize the flow field to this height. See ``output_width``.
    wavelet : str, default "db2"
        PyWavelets wavelet name forwarded to :func:`resize_flow`. Ignored
        unless ``output_width``/``output_height`` are set.
    overwrite : bool, default True
        Overwrite ``output_path`` if it already exists; when False and the
        file already exists, that path is returned as-is with no recompute.

    Returns
    -------
    str
        Path to the written file (``output_path``).

    Raises
    ------
    AssertionError
        If ``input_video`` is not a valid video file.
    ValueError
        If ``method``, ``dis_preset``, or ``raft_variant`` is not supported
        (propagated from :func:`iter_frame_optical_flow`).
    ImportError
        If ``method="raft"`` is requested but ``torchvision`` is not
        installed, or if ``output_width``/``output_height`` are requested
        but ``PyWavelets`` is not installed.

    Examples
    --------
    >>> extract_optical_flow("clip.mp4", "clip-flow.mp4", method="dis")
    'clip-flow.mp4'
    >>> extract_optical_flow("clip.mp4", "clip-flow.npy", method="dis")
    'clip-flow.npy'
    """
    osh.info(f"Extracting optical flow ({method}) from video file:\n\t{input_video}")
    assert is_valid_video_file(input_video), f"Input video file not okay:\n\t{input_video}"

    fi, bi, _ = osh.folder_name_ext(input_video)
    if osh.emptystring(output_path):
        output_path = osh.join([fi, bi + "-flow.mp4"])
    _, _, output_ext = osh.folder_name_ext(output_path)

    if not overwrite and osh.file_exists(output_path):
        osh.info(f"Optical flow output already exists, skipping:\n\t{output_path}")
        return output_path

    frames = extract_frames(
        input_video,
        start_instant=start_instant,
        end_instant=end_instant,
        frame_step=frame_step,
        frame_interval=frame_interval,
    )
    flow_frames = iter_frame_optical_flow(
        frames,
        method=method,
        dis_preset=dis_preset,
        raft_variant=raft_variant,
        device=device,
        clip_flow=clip_flow,
    )

    if (output_width is None) != (output_height is None):
        raise ValueError(
            "output_width and output_height must be given together (got "
            f"output_width={output_width!r}, output_height={output_height!r})"
        )

    flow_channels: list[np.ndarray] = [f[..., -2:] for f in flow_frames]
    if output_width is not None:
        flow_channels = [
            resize_flow(flow, output_width, output_height, wavelet=wavelet)
            for flow in flow_channels
        ]

    if output_ext.lower() == "npy":
        np.save(output_path, np.stack(flow_channels, axis=0))
    else:
        viz_frames = [_flow_to_rgb(flow[..., 0], flow[..., 1]) for flow in flow_channels]
        resolved_fps = (
            fps if fps is not None else video_dimensions(input_video)["frame_rate"] / frame_step
        )
        dump_frames(viz_frames, output_path, fps=round(resolved_fps))

    osh.info(f"Optical flow written:\n\t{output_path}")
    return output_path
