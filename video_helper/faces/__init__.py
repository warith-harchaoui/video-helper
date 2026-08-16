"""
video_helper.faces
==================

Audio-only speaker diarization (splitting a recording into "who spoke when")
can tell you a voice cluster exists, but not which visible face on screen
belongs to it: a meeting recording with three people on camera and one voice
active gives no clue, from audio alone, which of the three is talking. This
package answers that question by watching faces instead of just listening:
it detects and tracks faces frame by frame, then scores which tracked face's
lip motion (or, with the heavier model, its full audio-visual correlation)
lines up with a given audio speaker's activity, a task called Active-Speaker
Detection (ASD). The result anchors an audio-only speaker cluster to an
actual face crop, usable as a visual label or fed onward to face recognition.

Reusable, HuggingFace-free computer-vision primitives for face-anchored speaker
identity on video, built on the same local-first ethos as the rest of
video-helper (ffmpeg + OpenCV + PyTorch, no cloud, no HuggingFace at runtime).

Pieces (each usable on its own):

- :class:`FaceDetector`: YuNet detection + 5 landmarks (``detect``), via
  OpenCV's own bundled DNN wrapper (no separate onnxruntime dependency).
- :class:`FaceRecognizer`: SFace 128-d embeddings (``recognize``), same DNN
  wrapper as the detector.
- :func:`track_faces`: IoU/ByteTrack-family tracking into :class:`FaceTrack`
  (linking each detected face across consecutive frames into one continuous
  track, rather than treating every frame's detection as a new, unrelated face).
- :func:`mouth_roi`: lip-centred ROI for the ASD visual stream (``align``).
- :func:`get_engine`: an :class:`ASDEngine` (lip-motion proxy or Light-ASD PyTorch).
- :func:`active_speaker_map`: the **smart-sampling harness** that ties it all
  together: shots + speaker-turns + a cheap face census pick a small set of clips,
  heavy ASD runs only there and grows until every speaker is covered with
  certainty (``sampling``).
- :func:`ensure_model`: the sovereign model downloader (``models``).

Install the extra: ``pip install "video-helper[faces]"`` (adds ``torch``,
``scenedetect`` and ``python_speech_features``; ``opencv-python`` is already
a core dependency).
"""

from __future__ import annotations

from .align import mouth_openness, mouth_roi
from .asd import ASDEngine, LightASD, LipMotionASD, get_engine
from .detect import Face, FaceDetector
from .digest import DigestSegment, build_asd_digest, load_manifest, source_to_digest_window
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
    "build_asd_digest",
    "DigestSegment",
    "load_manifest",
    "source_to_digest_window",
    "ensure_model",
    "model_dir",
    "REGISTRY",
]
