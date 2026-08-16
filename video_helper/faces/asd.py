"""
video_helper.faces.asd
=======================

Active-Speaker Detection (ASD): given the on-screen faces during a window and the
concurrent audio, score *which* face is producing the speech.

Two interchangeable engines behind one interface:

- :class:`LipMotionASD` — a zero-weight proxy. Scores the **temporal variance of
  mouth openness** per track, gated by audio activity in the window. Always
  available, fully offline, no download. The graceful-degradation default.
- :class:`LightASD` — the accurate audio-visual cross-attention model (Light-ASD)
  run through PyTorch. Downloaded on first use from the user's mirror; if the
  weights are not hosted yet, :meth:`available` is False and the caller falls back
  to the proxy.

The engine is called **per clip window** (not per whole video): the smart-sampling
harness (:mod:`video_helper.faces.sampling`) picks a small set of windows so this
heavy step runs on a fraction of the footage.
"""

from __future__ import annotations

import os

import numpy as np
import os_helper as osh

from .align import mouth_openness, mouth_roi
from .models import ensure_model
from .track import FaceTrack


def _audio_activity(audio_16k: np.ndarray) -> float:
    """Coarse [0,1] speech-activity gate from windowed RMS energy."""
    if audio_16k is None or audio_16k.size == 0:
        return 1.0  # no audio handed in → don't suppress (harness already gated on VAD)
    rms = float(np.sqrt(np.mean(np.square(audio_16k.astype(np.float32)))))
    # Map a plausible speech RMS range to [0,1]; conservative, monotone.
    return float(np.clip(rms / 0.05, 0.0, 1.0))


class ASDEngine:
    """Interface: score each track's speaking likelihood within one clip window."""

    name = "base"

    def available(self) -> bool:  # pragma: no cover - trivial
        return False

    def score_tracks(
        self,
        frames: list[np.ndarray],
        tracks: list[FaceTrack],
        audio_16k: np.ndarray,
        fps: float,
    ) -> dict[int, float]:
        raise NotImplementedError


class LipMotionASD(ASDEngine):
    """Weights-free proxy: lip-motion variance × audio activity."""

    name = "lip-motion"

    def available(self) -> bool:
        return True

    def score_tracks(
        self,
        frames: list[np.ndarray],
        tracks: list[FaceTrack],
        audio_16k: np.ndarray,
        fps: float,
    ) -> dict[int, float]:
        gate = _audio_activity(audio_16k)
        raw: dict[int, float] = {}
        # Map absolute frame index -> position in the clip's frame list.
        for tr in tracks:
            opens: list[float] = []
            for fidx, face in zip(tr.frame_idx, tr.faces, strict=True):
                if 0 <= fidx < len(frames):
                    opens.append(mouth_openness(frames[fidx], face))
            if len(opens) >= 3:
                # Movement, not absolute opening, signals speech.
                raw[tr.track_id] = float(np.std(opens))
            else:
                raw[tr.track_id] = 0.0
        # Normalise across the faces present so scores are comparable, then gate.
        hi = max(raw.values(), default=0.0)
        if hi <= 1e-6:
            return dict.fromkeys(raw, 0.0)
        return {k: float(v / hi) * gate for k, v in raw.items()}


class LightASD(ASDEngine):
    """Light-ASD (Junhua-Liao et al., CVPR 2023) via **PyTorch** — accurate engine.

    Loads the pretrained weights (``light_asd.pth``, research license) into the
    vendored :mod:`._lightasd` model and scores each face track with the model's
    own audio-visual head. No ONNX: a faithful ONNX export of the MFCC front-end
    is fragile, so we run the real network. Degrades to *unavailable* (the
    harness swaps in the lip-motion proxy) if torch or the weights are missing.

    Preprocessing matches the original exactly: audio → 13-cepstrum MFCC with
    fps-adjusted windows; visual → 112x112 grayscale mouth crops fed RAW (the
    model normalises ``(x/255 - 0.4161)/0.1688`` internally — feeding an already
    /255 array would double-divide). Audio runs at ~4x the visual frame rate, so
    we align to ``4 * T_visual`` MFCC frames; the two front-ends reduce to a
    common length, and we min-clip to be safe.
    """

    name = "light-asd"

    def __init__(self) -> None:
        self._net = None
        self._checked = False
        self._device = None  # torch.device, resolved on first load

    @staticmethod
    def _pick_device():
        """GPU-select for Light-ASD: NVIDIA **CUDA** or Apple-Silicon **MPS**, else CPU.

        ``NH_ASD_DEVICE=cpu|cuda|mps|auto`` (default ``auto``) overrides, handy for
        benchmarking and for forcing CPU if a driver misbehaves. The net is tiny, but a
        GPU still cuts the per-window forward markedly, and the ASD pass is the heavy step.
        In ``auto`` a discrete CUDA GPU is preferred, then MPS, then CPU. An explicit
        request for an unavailable backend warns and falls back to auto-selection.
        """
        import torch

        want = os.environ.get("NH_ASD_DEVICE", "auto").strip().lower()
        if want == "cpu":
            return torch.device("cpu")
        # Honour an explicit device when its backend is actually present.
        if want == "cuda":
            if torch.cuda.is_available():
                return torch.device("cuda")
            osh.warning("faces.asd: NH_ASD_DEVICE=cuda but CUDA is unavailable — auto-selecting")
        if want == "mps":
            if torch.backends.mps.is_available():
                return torch.device("mps")
            osh.warning("faces.asd: NH_ASD_DEVICE=mps but MPS is unavailable — auto-selecting")
        # Auto: prefer a discrete NVIDIA GPU, then Apple-Silicon MPS, then CPU.
        if torch.cuda.is_available():
            return torch.device("cuda")
        if torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def _ensure(self) -> bool:
        if self._checked:
            return self._net is not None
        self._checked = True
        path = ensure_model("light-asd")
        if path is None:
            return False
        try:
            import torch
            import torch.nn as nn

            from ._lightasd.loss import lossAV, lossV
            from ._lightasd.model import ASD_Model

            class _ASD(nn.Module):
                """Wrapper matching the checkpoint prefixes (model./lossAV./lossV.)."""

                def __init__(self) -> None:
                    super().__init__()
                    self.model = ASD_Model()
                    self.lossAV = lossAV()
                    self.lossV = lossV()

            net = _ASD()
            state = torch.load(path, map_location="cpu", weights_only=False)
            net.load_state_dict(state, strict=True)
            net.eval()
            self._device = self._pick_device()
            if self._device.type == "mps":
                # Light-ASD's temporal encoder (GRU) has no MPS kernel on some torch builds; let
                # PyTorch run just those ops on CPU instead of raising, keeping the rest on GPU.
                os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
            net.to(self._device)
            self._net = net
            osh.info(f"faces.asd: Light-ASD on {self._device.type}")
        except Exception as exc:  # noqa: BLE001 — missing torch / bad weights → proxy
            osh.warning(f"faces.asd: Light-ASD torch load failed ({exc}) — using proxy")
            self._net = None
        return self._net is not None

    def available(self) -> bool:
        return self._ensure()

    def score_tracks(
        self,
        frames: list[np.ndarray],
        tracks: list[FaceTrack],
        audio_16k: np.ndarray,
        fps: float,
    ) -> dict[int, float]:
        if not self._ensure():
            return LipMotionASD().score_tracks(frames, tracks, audio_16k, fps)
        import torch
        from python_speech_features import mfcc as _mfcc

        # MFCC with the original's fps-adjusted windows (audio ~4x visual rate).
        ratio = 25.0 / max(float(fps), 1e-6)
        winlen = 0.025 * ratio
        # Size the FFT to the (fps-stretched) window instead of leaving the 512 default: at low
        # asd_fps the window is ~833 samples > 512, which python_speech_features would TRUNCATE
        # (dropping signal + spamming warnings). Round up to the next power of two, floor 512.
        frame_len = int(round(winlen * 16000))
        nfft = 1 << max(9, (frame_len - 1).bit_length())
        try:
            audio_mfcc = _mfcc(
                np.asarray(audio_16k, dtype=np.float32),
                16000,
                numcep=13,
                winlen=winlen,
                winstep=0.010 * ratio,
                nfft=nfft,
            ).astype(np.float32)
        except Exception:  # noqa: BLE001
            audio_mfcc = None

        scores: dict[int, float] = {}
        for tr in tracks:
            vis = [
                mouth_roi(frames[f], face, size=112)
                for f, face in zip(tr.frame_idx, tr.faces, strict=True)
                if 0 <= f < len(frames)
            ]
            if not vis or audio_mfcc is None:
                scores[tr.track_id] = 0.0
                continue
            tv = len(vis)
            v = np.stack(vis).astype(np.float32)  # [T,112,112] RAW 0-255
            ta = 4 * tv
            a = audio_mfcc[:ta]
            if a.shape[0] < ta:  # pad a short tail
                a = np.pad(a, ((0, ta - a.shape[0]), (0, 0)))
            try:
                scores[tr.track_id] = self._forward(torch, a, v)
            except Exception as exc:  # noqa: BLE001
                # A device (e.g. MPS) hiccup: demote the whole engine to CPU once and retry, so
                # one unsupported op never silently zeroes every score.
                if self._device is not None and self._device.type != "cpu":
                    osh.warning(f"faces.asd: {self._device.type} forward failed ({exc}) — CPU")
                    self._device = torch.device("cpu")
                    self._net.to(self._device)
                    try:
                        scores[tr.track_id] = self._forward(torch, a, v)
                        continue
                    except Exception as exc2:  # noqa: BLE001
                        exc = exc2
                osh.warning(f"faces.asd: Light-ASD forward failed ({exc})")
                scores[tr.track_id] = 0.0
        return scores

    def _forward(self, torch, a: np.ndarray, v: np.ndarray) -> float:
        """One audio-visual window → speaking probability, on ``self._device``."""
        with torch.no_grad():
            af = torch.from_numpy(a[None, ...]).to(self._device)  # [1, Ta, 13]
            vf = torch.from_numpy(v[None, ...]).to(self._device)  # [1, Tv, 112, 112]
            ae = self._net.model.forward_audio_frontend(af)
            ve = self._net.model.forward_visual_frontend(vf)
            n = min(ae.shape[1], ve.shape[1])
            outs = self._net.model.forward_audio_visual_backend(ae[:, :n], ve[:, :n])
            # lossAV(labels=None) already returns a detached CPU numpy array (device transfer
            # handled inside), so no .cpu() dance is needed here.
            pred = np.asarray(self._net.lossAV(outs, labels=None), dtype=np.float32)
            prob = 1.0 / (1.0 + np.exp(-pred))
            return float(np.clip(prob.mean(), 0.0, 1.0))


def get_engine(name: str = "auto") -> ASDEngine:
    """Return an ASD engine by name, degrading to the proxy when needed.

    ``"auto"`` prefers Light-ASD when its weights are hosted, else the proxy.
    ``"light-asd"`` forces the accurate engine (still falls back if unavailable).
    ``"lip-motion"`` forces the proxy.
    """
    if name == "lip-motion":
        return LipMotionASD()
    if name in ("auto", "light-asd"):
        light = LightASD()
        if light.available():
            osh.info("faces.asd: using Light-ASD")
            return light
        osh.info("faces.asd: Light-ASD unavailable — using lip-motion proxy")
        return LipMotionASD()
    osh.warning(f"faces.asd: unknown engine {name!r} — using lip-motion proxy")
    return LipMotionASD()
