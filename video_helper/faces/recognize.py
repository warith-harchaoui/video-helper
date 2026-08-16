"""
video_helper.faces.recognize
=============================

Face-recognition embeddings via OpenCV's SFace (``cv2.FaceRecognizerSF``),
Apache-2.0, HuggingFace-free. SFace emits a **128-d** embedding (not 512-d);
downstream stores must size themselves from :attr:`FaceRecognizer.emb_dim`, not a
hard-coded constant.

Alignment is delegated to ``cv2.FaceRecognizerSF.alignCrop``, which consumes the
raw YuNet detector row (5 landmarks) to similarity-transform each face to the
canonical 112×112 template, so detection and recognition share one landmark
source and there is no second alignment implementation to keep in sync.
"""

from __future__ import annotations

import numpy as np
import os_helper as osh

from .detect import Face
from .models import ensure_model

# SFace embedding dimensionality (fixed by the model).
SFACE_DIM = 128


def l2(v: np.ndarray) -> np.ndarray:
    """L2-normalise a single vector (matches identity.py's convention)."""
    v = np.asarray(v, dtype=np.float32)
    return v / (np.linalg.norm(v) + 1e-9)


class FaceRecognizer:
    """Lazy, reusable SFace embedder.

    Attributes
    ----------
    emb_dim : int
        Embedding dimensionality (128 for SFace). Read this rather than assuming.
    """

    def __init__(self) -> None:
        self.emb_dim = SFACE_DIM
        self._rec = None

    def _ensure(self) -> bool:
        if self._rec is not None:
            return True
        import cv2

        path = ensure_model("sface")
        if path is None:
            osh.warning("faces.recognize: SFace weights unavailable — recognition disabled")
            return False
        self._rec = cv2.FaceRecognizerSF.create(path, "")
        return True

    def embed(self, frame_bgr: np.ndarray, face: Face) -> np.ndarray | None:
        """Return the L2-normalised 128-d embedding for one face, or None.

        The face is aligned+cropped from ``frame_bgr`` using its raw YuNet row,
        then run through SFace. Returns ``None`` on any failure so callers can
        skip a bad crop rather than poison an average.
        """
        if not self._ensure():
            return None
        try:
            aligned = self._rec.alignCrop(frame_bgr, face.raw)
            feat = self._rec.feature(aligned)  # (1, 128) float32
            vec = np.asarray(feat, dtype=np.float32).reshape(-1)
            if vec.shape[0] != self.emb_dim or not np.isfinite(vec).all():
                return None
            return l2(vec)
        except Exception as exc:  # noqa: BLE001 — one bad crop must not sink the track
            osh.warning(f"faces.recognize: embed failed ({exc})")
            return None

    def embed_track(
        self, frames: list[np.ndarray], faces: list[Face], *, top_k: int = 12
    ) -> np.ndarray | None:
        """Aggregate one persistent embedding for a face track.

        Quality-gates the crops (highest detector score first — the face analogue
        of picking the longest, most-confident turns for a voiceprint), embeds up
        to ``top_k`` of them, and returns the L2-normalised mean. ``None`` if no
        crop yields a usable embedding.
        """
        order = sorted(range(len(faces)), key=lambda i: faces[i].score, reverse=True)
        vecs: list[np.ndarray] = []
        for i in order[: max(top_k * 2, top_k)]:
            v = self.embed(frames[i], faces[i])
            if v is not None:
                vecs.append(v)
            if len(vecs) >= top_k:
                break
        if not vecs:
            return None
        return l2(np.stack(vecs).mean(axis=0)).astype(np.float32)
