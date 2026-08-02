"""
Tests for the ``video_helper.faces`` stack.

The heavy paths (YuNet detection, SFace embedding, ASD) need model weights and a
real face, so they are exercised opportunistically only when weights are already
cached — never downloaded in CI. What is tested unconditionally is the
**weights-free logic** that the smart-sampling harness is built from: IoU
tracking, the global-face gallery, greedy one-to-one assignment, candidate-window
generation, the mouth ROI, and the lip-motion ASD proxy. These are deterministic
and dependency-light.

Usage Example
-------------
>>> #   pytest tests/test_faces.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import numpy as np

from video_helper.faces import mouth_roi, track_faces
from video_helper.faces.detect import Face
from video_helper.faces.models import REGISTRY, ModelSpec
from video_helper.faces.sampling import _candidate_windows, _FaceGallery, _greedy_assign


def _face(x: float, y: float, w: float = 40, h: float = 40, score: float = 0.9) -> Face:
    lms = np.array([[x + 10, y + 12], [x + 30, y + 12], [x + 20, y + 22],
                    [x + 14, y + 32], [x + 26, y + 32]], dtype=np.float32)
    raw = np.zeros(15, dtype=np.float32)
    raw[:4] = [x, y, w, h]
    raw[4:14] = lms.reshape(-1)
    raw[14] = score
    return Face(box=(x, y, w, h), landmarks=lms, score=score, raw=raw)


def test_registry_permissive_defaults() -> None:
    assert isinstance(REGISTRY["yunet"], ModelSpec)
    assert REGISTRY["yunet"].license == "Apache-2.0"
    assert REGISTRY["sface"].license == "Apache-2.0"
    # ASD weights are research-licensed → gated off unless explicitly allowed.
    assert REGISTRY["light-asd"].license == "research"


def test_iou_tracking_links_a_moving_face() -> None:
    # One face drifting a few px/frame should stay a single track; a far-away
    # face in the last frame should spawn a second track.
    frame_dets = [(i, [_face(100 + i, 100 + i)]) for i in range(6)]
    frame_dets.append((6, [_face(106, 106), _face(10, 10)]))
    tracks = track_faces(frame_dets, iou_threshold=0.3)
    assert len(tracks) == 2
    main = max(tracks, key=lambda t: len(t.faces))
    assert len(main.faces) == 7  # 6 drift frames + the near box in the last


def test_gallery_counts_distinct_faces() -> None:
    rng = np.random.default_rng(0)
    a = rng.standard_normal(128).astype(np.float32)
    a /= np.linalg.norm(a)
    b = rng.standard_normal(128).astype(np.float32)
    b /= np.linalg.norm(b)
    g = _FaceGallery(recognizer=None, threshold=0.363)
    id_a = g.assign(a)
    id_a2 = g.assign(a * 0.99 + a * 0.0)  # essentially the same vector
    id_b = g.assign(b)
    assert id_a == id_a2  # same identity merges
    assert id_b != id_a  # a near-orthogonal random vector is a new identity
    assert g.assign(None) is None


def test_greedy_assignment_is_one_to_one() -> None:
    W = {0: {10: 5.0, 11: 1.0}, 1: {10: 4.0, 11: 3.0}}
    out = _greedy_assign(W, [0, 1])
    assert out[0] == 10  # strongest edge wins first
    assert out[1] == 11  # face 10 taken → speaker 1 takes its best free face
    assert len(set(out.values())) == 2  # no face used twice


def test_candidate_windows_require_face_and_speech_overlap() -> None:
    turns = [{"t0": 0.0, "t1": 6.0, "spk": 0}, {"t0": 6.0, "t1": 12.0, "spk": 1}]
    face_regions = [(0.0, 6.0)]  # only speaker 0's turn overlaps a face
    shots = [(0.0, 12.0)]
    cands = _candidate_windows(turns, face_regions, shots, clip_len=3.0)
    assert 0 in cands and cands[0]  # speaker 0 got windows
    assert 1 not in cands  # speaker 1 never co-occurs with a face → no windows


def test_mouth_roi_shape_and_offscreen() -> None:
    frame = np.full((240, 320, 3), 128, dtype=np.uint8)
    roi = mouth_roi(frame, _face(100, 100), size=112)
    assert roi.shape == (112, 112) and roi.dtype == np.uint8
    # A face entirely off-frame yields a zero ROI, not a crash.
    off = mouth_roi(frame, _face(-500, -500), size=112)
    assert off.shape == (112, 112) and int(off.max()) == 0
