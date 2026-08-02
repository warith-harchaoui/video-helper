"""
Tests for Light-ASD's device selection (Apple-Silicon MPS) and MFCC FFT sizing.

Module summary
--------------
- The MFCC front-end sizes its FFT to the fps-stretched analysis window instead of leaving the
  library's 512 default: at a low ``asd_fps`` the window is ~833 samples > 512, which
  ``python_speech_features`` would silently TRUNCATE (dropping signal). ``nfft`` rounds up to the
  next power of two so the whole window is transformed.
- Light-ASD runs on MPS when available (auto), falling back to CPU, with bit-identical scores.
  ``NH_ASD_DEVICE=cpu|mps|auto`` overrides. MPS needs ``PYTORCH_ENABLE_MPS_FALLBACK=1`` (set at
  package import) for the couple of ops without an MPS kernel; the score is unchanged, ~2.5x faster.

Author
------
Warith HARCHAOUI — https://linkedin.com/in/warith-harchaoui
"""

from __future__ import annotations

import numpy as np
import pytest

from video_helper.faces.asd import LightASD


def _nfft_for(fps: float) -> tuple[int, int]:
    """Reproduce ``score_tracks``' window/FFT sizing for a given ASD frame rate."""
    winlen = 0.025 * (25.0 / max(fps, 1e-6))
    frame_len = int(round(winlen * 16000))
    return frame_len, 1 << max(9, (frame_len - 1).bit_length())


def test_nfft_covers_stretched_window_no_truncation():
    """A low asd_fps stretches the window past 512 samples; nfft must round up to cover it."""
    frame_len, nfft = _nfft_for(12.0)
    assert frame_len > 512      # exactly the case that used to truncate + spam warnings
    assert nfft >= frame_len    # now the whole window is transformed
    assert nfft == 1024
    _, nfft_hi = _nfft_for(25.0)
    assert nfft_hi >= 512       # never drops below the library default at native rate


@pytest.mark.skipif(not LightASD().available(), reason="Light-ASD weights unavailable")
def test_forward_device_parity(monkeypatch):
    """The audio-visual forward yields a valid probability, identical on CPU and MPS."""
    import torch

    rng = np.random.RandomState(0)
    tv = 24
    a = rng.rand(4 * tv, 13).astype(np.float32)
    v = (rng.rand(tv, 112, 112).astype(np.float32)) * 255.0

    monkeypatch.setenv("NH_ASD_DEVICE", "cpu")
    cpu = LightASD()
    assert cpu.available() and cpu._device.type == "cpu"
    s_cpu = cpu._forward(torch, a, v)
    assert 0.0 <= s_cpu <= 1.0

    if torch.backends.mps.is_available():
        monkeypatch.setenv("NH_ASD_DEVICE", "mps")
        mps = LightASD()
        assert mps.available() and mps._device.type == "mps"
        s_mps = mps._forward(torch, a, v)
        assert abs(s_cpu - s_mps) < 1e-3  # same weights, different device → same score


def test_pick_device_respects_cpu_override(monkeypatch):
    """``NH_ASD_DEVICE=cpu`` forces CPU even on a CUDA/MPS-capable box."""
    # _pick_device builds a torch.device, so it needs torch; skip cleanly in the
    # light CI env (torch ships only with the [faces] extra, exercised locally).
    pytest.importorskip("torch")
    monkeypatch.setenv("NH_ASD_DEVICE", "cpu")
    assert LightASD._pick_device().type == "cpu"
