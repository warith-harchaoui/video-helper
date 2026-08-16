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

import os

import numpy as np
import os_helper as osh
import pytest

from video_helper import black_video, is_valid_video_file, video_duration
from video_helper.faces import (
    active_speaker_map,
    build_asd_digest,
    load_manifest,
    mouth_roi,
    track_faces,
)
from video_helper.faces.detect import Face, FaceDetector
from video_helper.faces.digest import source_to_digest_window
from video_helper.faces.models import REGISTRY, ModelSpec, model_dir
from video_helper.faces.recognize import FaceRecognizer
from video_helper.faces.sampling import _candidate_windows, _FaceGallery, _greedy_assign

osh.verbosity(0)


def _weights_cached(name: str) -> bool:
    """Return True without touching the network -- checks the on-disk cache
    only, so these tests never trigger a download in CI (see module
    docstring)."""
    spec = REGISTRY[name]
    return os.path.isfile(os.path.join(model_dir(), spec.filename))


def _face(x: float, y: float, w: float = 40, h: float = 40, score: float = 0.9) -> Face:
    lms = np.array(
        [[x + 10, y + 12], [x + 30, y + 12], [x + 20, y + 22], [x + 14, y + 32], [x + 26, y + 32]],
        dtype=np.float32,
    )
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


@pytest.mark.skipif(not _weights_cached("yunet"), reason="YuNet weights not cached locally")
def test_face_detector_runs_real_yunet_inference() -> None:
    """Opportunistic (real cached weights, never downloaded in CI): the real
    ``cv2.FaceDetectorYN`` loads and runs on a real frame without crashing,
    returning a (possibly empty) list of :class:`Face`. Exercises the actual
    model-construction + inference path that the weights-free tests above
    cannot reach."""
    detector = FaceDetector(score_threshold=0.5)
    frame = np.random.default_rng(0).integers(0, 256, (240, 320, 3), dtype=np.uint8)
    faces = detector.detect(frame)
    assert isinstance(faces, list)
    for f in faces:
        assert isinstance(f, Face)
        assert f.landmarks.shape == (5, 2)


@pytest.mark.skipif(not _weights_cached("sface"), reason="SFace weights not cached locally")
def test_face_recognizer_embeds_a_real_unit_norm_vector() -> None:
    """Opportunistic (real cached weights, never downloaded in CI): the real
    ``cv2.FaceRecognizerSF`` aligns a crop from a raw YuNet-shaped detector
    row and embeds it, returning a genuine L2-normalised 128-d vector --
    exercises the actual ONNX inference path, not just the gallery/tracking
    logic that consumes its output."""
    frame = np.random.default_rng(1).integers(0, 256, (240, 240, 3), dtype=np.uint8)
    recognizer = FaceRecognizer()
    vec = recognizer.embed(frame, _face(60, 60, w=80, h=80))
    assert vec is not None
    assert vec.shape == (recognizer.emb_dim,)
    assert vec.dtype == np.float32
    assert abs(float(np.linalg.norm(vec)) - 1.0) < 1e-4


def test_build_asd_digest_end_to_end(tmp_path) -> None:
    """Real ffmpeg pipeline, no model weights needed: a 20s clip with a close
    pair of anchors (fused) plus a far one yields several non-overlapping
    digest windows, a valid concatenated video, and a manifest whose two
    timelines (digest <-> source) invert each other via ``to_source_time``/
    ``source_to_digest_window`` -- the bookkeeping every ASD consumer relies
    on to map a digest-time result back onto the original recording."""
    src = str(tmp_path / "source.mp4")
    black_video(20.0, 64, 64, src, frame_rate=10)
    out = str(tmp_path / "digest.mp4")

    segments = build_asd_digest(src, [3.0, 3.5, 12.0], out, window=2.0, merge_gap=1.0)

    assert len(segments) >= 2  # the close pair fuses; the far anchor stays separate
    assert is_valid_video_file(out)
    digest_dur = video_duration(out)
    expected = sum(s.digest_end - s.digest_start for s in segments)
    assert abs(digest_dur - expected) < 1.0  # final re-encode preserves total length

    manifest_path = f"{out}.manifest.json"
    assert os.path.isfile(manifest_path)
    reloaded = load_manifest(manifest_path)
    assert [(s.digest_start, s.digest_end) for s in reloaded] == [
        (s.digest_start, s.digest_end) for s in segments
    ]

    for seg in segments:
        # digest -> source -> digest round-trips through the segment's own offset.
        # Cuts snap to the nearest frame boundary (0.1s at this clip's 10fps), so
        # allow slack wider than one frame rather than asserting exact equality.
        assert seg.to_source_time(seg.digest_start) == pytest.approx(seg.source_start, abs=0.2)
        assert seg.to_source_time(seg.digest_end) == pytest.approx(seg.source_end, abs=0.2)
        mapped = source_to_digest_window(segments, seg.source_start, seg.source_end)
        assert mapped == pytest.approx((seg.digest_start, seg.digest_end), abs=0.2)

    # A span outside every window (the 20s tail, far past the last anchor's
    # window) was never anchor-driven into the digest -- callers must fall
    # back to the original source for it.
    assert source_to_digest_window(segments, 19.5, 19.9) is None


@pytest.mark.skipif(not _weights_cached("yunet"), reason="YuNet weights not cached locally")
def test_active_speaker_map_returns_empty_without_any_face() -> None:
    """Opportunistic (real cached weights, never downloaded in CI): a plain
    black clip has no face for YuNet to find, so the real census (real
    decode + real detection, no mocking) comes back empty and the whole
    harness degrades to 'no face anchoring possible' rather than crashing --
    exercising the orchestration function's setup + early-exit path that no
    other test reaches (engine/detector/recognizer construction, shot
    detection, the census loop itself)."""
    with osh.temporary_folder(prefix="asd-map-test") as tmp_dir:
        src = osh.join(tmp_dir, "source.mp4")
        black_video(6.0, 64, 64, src, frame_rate=10)
        turns = [{"t0": 0.0, "t1": 3.0, "spk": 0}, {"t0": 3.0, "t1": 6.0, "spk": 1}]
        results = active_speaker_map(
            src, None, turns, asd_engine="lip-motion", clip_len=1.5, clip_budget=4
        )
    assert results == []
