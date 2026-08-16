"""
video_helper.faces.detect
==========================

Per-frame face detection with 5-point landmarks via OpenCV's YuNet
(``cv2.FaceDetectorYN``). Tiny, fast, Apache-2.0, HuggingFace-free.

The 5 landmarks (right eye, left eye, nose tip, right mouth corner, left mouth
corner) are what the recognition aligner and the ASD mouth-ROI both need, so the
raw detector row is carried through on each :class:`Face` for downstream reuse
(``cv2.FaceRecognizerSF.alignCrop`` consumes it directly, no re-derivation).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import os_helper as osh

from .models import ensure_model

# Landmark row order emitted by YuNet, after the (x, y, w, h) box.
_LANDMARK_NAMES = ("right_eye", "left_eye", "nose", "mouth_right", "mouth_left")


@dataclass
class Face:
    """One detected face in one frame.

    Attributes
    ----------
    box : tuple[float, float, float, float]
        ``(x, y, w, h)`` in pixels.
    landmarks : np.ndarray
        ``(5, 2)`` float array — see :data:`_LANDMARK_NAMES`.
    score : float
        Detector confidence in ``[0, 1]``.
    raw : np.ndarray
        The full 15-float YuNet row (box + 10 landmark coords + score), kept so
        ``cv2.FaceRecognizerSF.alignCrop`` can be fed the exact detector output.
    """

    box: tuple[float, float, float, float]
    landmarks: np.ndarray
    score: float
    raw: np.ndarray


class FaceDetector:
    """Lazy, reusable YuNet detector.

    The underlying ``cv2.FaceDetectorYN`` is created on first use and its input
    size is reset per frame (YuNet requires the exact frame dimensions).
    Construction never downloads; the first :meth:`detect` does.
    """

    def __init__(self, *, score_threshold: float = 0.6, min_size: int = 40) -> None:
        self.score_threshold = score_threshold
        self.min_size = min_size
        self._det = None
        self._model_path: str | None = None

    def _ensure(self) -> bool:
        if self._det is not None:
            return True
        import cv2

        path = ensure_model("yunet")
        if path is None:
            osh.warning("faces.detect: YuNet weights unavailable — detection disabled")
            return False
        # input_size is a placeholder; reset per frame in detect().
        self._det = cv2.FaceDetectorYN.create(path, "", (320, 320), self.score_threshold, 0.3, 5000)
        self._model_path = path
        return True

    def detect(self, frame_bgr: np.ndarray) -> list[Face]:
        """Detect faces in a single BGR uint8 frame (OpenCV convention)."""
        if not self._ensure():
            return []
        h, w = frame_bgr.shape[:2]
        self._det.setInputSize((w, h))
        _, rows = self._det.detect(frame_bgr)
        if rows is None:
            return []
        faces: list[Face] = []
        for row in rows:
            row = np.asarray(row, dtype=np.float32)
            score = float(row[14])
            bw, bh = float(row[2]), float(row[3])
            if score < self.score_threshold or min(bw, bh) < self.min_size:
                continue
            lms = row[4:14].reshape(5, 2)
            faces.append(
                Face(
                    box=(float(row[0]), float(row[1]), bw, bh),
                    landmarks=lms,
                    score=score,
                    raw=row,
                )
            )
        return faces
