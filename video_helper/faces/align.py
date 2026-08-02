"""
video_helper.faces.align
=========================

Mouth-ROI extraction for the active-speaker (lip) stream.

Recognition alignment (the canonical 112×112 face crop) is handled inside
``cv2.FaceRecognizerSF.alignCrop`` — see :mod:`video_helper.faces.recognize`.
What ASD additionally needs is a **stable crop centred on the lips**, derived
here from the two mouth-corner landmarks so the articulatory signal dominates.
"""

from __future__ import annotations

import numpy as np

from .detect import Face


def mouth_roi(
    frame_bgr: np.ndarray, face: Face, *, size: int = 112, pad: float = 1.6
) -> np.ndarray:
    """Crop a square, lip-centred grayscale ROI for the ASD visual stream.

    The crop is centred on the mouth-corner midpoint, sized to ``pad`` times the
    inter-corner distance (so the whole mouth plus a margin is captured), clamped
    to the frame, and resized to ``size``×``size``. Returns a ``(size, size)``
    uint8 grayscale array (zeros if the face falls entirely off-frame).
    """
    import cv2

    h, w = frame_bgr.shape[:2]
    m_right = face.landmarks[3]
    m_left = face.landmarks[4]
    cx, cy = (m_right + m_left) / 2.0
    half = max(pad * float(np.linalg.norm(m_right - m_left)), 24.0)

    x0 = int(round(cx - half))
    y0 = int(round(cy - half))
    x1 = int(round(cx + half))
    y1 = int(round(cy + half))
    x0c, y0c = max(0, x0), max(0, y0)
    x1c, y1c = min(w, x1), min(h, y1)
    if x1c <= x0c or y1c <= y0c:
        return np.zeros((size, size), dtype=np.uint8)

    crop = frame_bgr[y0c:y1c, x0c:x1c]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)


def mouth_openness(frame_bgr: np.ndarray, face: Face) -> float:
    """Cheap vertical-mouth-opening proxy in ``[0, 1]`` (weights-free ASD cue).

    Uses the vertical gradient energy inside the lip ROI, normalised by the ROI
    size, as a stand-in for mouth opening/closing. It is deliberately crude — the
    lip-motion ASD proxy scores *variance over time* of this signal, not its
    absolute value, so only relative movement matters.
    """
    import cv2

    roi = mouth_roi(frame_bgr, face, size=64)
    if roi.max() == 0:
        return 0.0
    gy = cv2.Sobel(roi.astype(np.float32), cv2.CV_32F, 0, 1, ksize=3)
    return float(np.abs(gy).mean() / 255.0)
