"""
video_helper.faces
==================

Reusable, HuggingFace-free computer-vision primitives for face-anchored speaker
identity on video, built on the same local-first ethos as the rest of
video-helper (ffmpeg + OpenCV + ONNX, no cloud, no HuggingFace at runtime).

Pieces (each usable on its own):

- :class:`FaceDetector` — YuNet detection + 5 landmarks (``detect``).
- :class:`FaceRecognizer` — SFace 128-d embeddings (``recognize``).
- :func:`track_faces` — IoU/ByteTrack-family tracking into :class:`FaceTrack`.
- :func:`mouth_roi` — lip-centred ROI for the ASD visual stream (``align``).
- :func:`get_engine` — an :class:`ASDEngine` (lip-motion proxy or Light-ASD ONNX).
- :func:`active_speaker_map` — the **smart-sampling harness** that ties it all
  together: shots + speaker-turns + a cheap face census pick a small set of clips,
  heavy ASD runs only there and grows until every speaker is covered with
  certainty (``sampling``).
- :func:`ensure_model` — the sovereign model downloader (``models``).

Install the extra: ``pip install "video-helper[faces]"`` (adds onnxruntime +
scenedetect; opencv-python is already a core dependency).
"""

from __future__ import annotations

from .align import mouth_openness, mouth_roi
from .asd import ASDEngine, LightASD, LipMotionASD, get_engine
from .detect import Face, FaceDetector
from .models import REGISTRY, ensure_model, model_dir
from .recognize import FaceRecognizer
from .sampling import SpeakerFaceAssignment, active_speaker_map
from .track import FaceTrack, track_faces

__all__ = [
    "Face",
    "FaceDetector",
    "FaceRecognizer",
    "FaceTrack",
    "track_faces",
    "mouth_roi",
    "mouth_openness",
    "ASDEngine",
    "LipMotionASD",
    "LightASD",
    "get_engine",
    "active_speaker_map",
    "SpeakerFaceAssignment",
    "ensure_model",
    "model_dir",
    "REGISTRY",
]
