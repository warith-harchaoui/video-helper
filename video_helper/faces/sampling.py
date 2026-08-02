"""
video_helper.faces.sampling
============================

The **smart-sampling harness** — the piece that makes Active-Speaker Detection
affordable on a full recording.

Heavy ASD is never run over the whole video. Instead:

1. **Shots** — PySceneDetect segments the video into shots (cheap; skipped
   gracefully if scenedetect is absent → one shot).
2. **Face census** — a cheap low-fps YuNet-only pass counts faces and records
   *where* (which time regions) faces appear. No ASD here.
3. **Candidate windows** — for each audio speaker cluster, short windows are
   proposed where that cluster speaks **and** a face is on screen, spread across
   distinct shots for diversity.
4. **Iterative ASD** — heavy ASD runs only on a small batch of windows; per-face
   speaking scores vote each cluster onto a **global face identity** (tracks are
   stitched across windows/shots by face embedding, which also *counts the faces*
   along the video). After each round the assignment is checked for **certainty**
   (vote margin + coverage); clusters still uncertain get *more* windows, up to a
   hard clip budget.

Output: per cluster, the assigned global face, its coverage and certainty margin,
and the best crops collected (so the caller can embed the face without decoding
the video again).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np
import os_helper as osh

from .asd import ASDEngine, get_engine
from .detect import Face, FaceDetector
from .recognize import FaceRecognizer
from .track import track_faces

_SR = 16000  # audio sample rate the harness expects for slicing

# Cap the working resolution of the faces pipeline. Face detection (YuNet) and the
# ASD mouth-crop pipeline gain nothing from 4K frames: a reasonable max height
# keeps faces well-resolved while cutting decode memory and detection/ASD compute.
# Every extracted frame is downscaled to this height (aspect preserved, never
# upscaled) BEFORE detection, so all downstream stages — detection, tracking, ASD,
# recognition, and the emitted crops — share one reduced, self-consistent
# coordinate space. Override with NH_FACES_MAX_HEIGHT (e.g. 1080 for more detail).
_MAX_FACE_HEIGHT = int(os.environ.get("NH_FACES_MAX_HEIGHT", "720"))


def _cap_frame(frame: np.ndarray, max_height: int = _MAX_FACE_HEIGHT) -> np.ndarray:
    """Downscale a BGR frame to ``max_height``, preserving aspect; never upscale.

    Returns the frame untouched when it is already short enough. ``INTER_AREA`` is
    the correct interpolation for shrinking (it avoids the aliasing a linear
    resize introduces), which matters for the small facial features YuNet and the
    ASD mouth-ROI rely on.

    Parameters
    ----------
    frame : np.ndarray
        A ``(H, W, 3)`` BGR uint8 frame.
    max_height : int, optional
        Maximum output height in pixels (default :data:`_MAX_FACE_HEIGHT`).

    Returns
    -------
    np.ndarray
        The frame, downscaled to ``max_height`` rows when it was taller.
    """
    h = frame.shape[0]
    if h <= max_height:
        return frame
    import cv2

    # Scale width by the same factor so the aspect ratio is preserved exactly.
    scale = max_height / float(h)
    new_w = max(1, int(round(frame.shape[1] * scale)))
    return cv2.resize(frame, (new_w, max_height), interpolation=cv2.INTER_AREA)


@dataclass
class SpeakerFaceAssignment:
    """The face assigned to one diarization cluster.

    Attributes
    ----------
    speaker : int
        Diarization cluster label.
    face_id : int
        Global face identity (stable across the whole video).
    coverage : float
        Fraction of the cluster's *sampled* speech during which the assigned face
        was on screen and scored as speaking. Drives the fusion "face vs voice".
    margin : float
        Vote margin over the runner-up face in ``[0, 1]`` — the certainty signal.
    crops : list[tuple[np.ndarray, Face]]
        Best ``(frame_bgr, Face)`` samples of the assigned face, for embedding.
    """

    speaker: int
    face_id: int
    coverage: float
    margin: float
    crops: list[tuple[np.ndarray, Face]] = field(default_factory=list)


def _detect_shots(video_path: str, *, frame_skip: int = 2) -> list[tuple[float, float]]:
    """Return shot ``(t0, t1)`` spans, or a single whole-video span on failure.

    PySceneDetect decodes the whole file, so on a long recording this is the
    heaviest pre-ASD step. Two cheap speed-ups keep it bounded: ``auto_downscale``
    (analyse a downsized frame — plenty for a cut/no-cut decision) and
    ``frame_skip`` (test every Nth frame). Shots only steer *sampling diversity*,
    so the small loss in boundary precision from skipping is immaterial here.
    """
    try:
        from scenedetect import ContentDetector, SceneManager, open_video

        video = open_video(video_path)
        sm = SceneManager()
        sm.auto_downscale = True
        sm.add_detector(ContentDetector())
        sm.detect_scenes(video, frame_skip=frame_skip)
        scenes = sm.get_scene_list()
        if scenes:
            return [(s.get_seconds(), e.get_seconds()) for s, e in scenes]
    except Exception as exc:  # noqa: BLE001 — scenedetect optional / decode hiccup
        osh.warning(f"faces.sampling: shot detection unavailable ({exc}) — one shot")
    return [(0.0, 0.0)]  # sentinel single shot; end filled by caller


def _shot_of(t: float, shots: list[tuple[float, float]]) -> int:
    for i, (a, b) in enumerate(shots):
        if a <= t < b or (b == 0.0 and i == 0):
            return i
    return 0


def _census(
    video_path: str, detector: FaceDetector, *, period: float, duration: float
) -> list[tuple[float, float]]:
    """Cheap low-fps face census → merged time regions that contain ≥1 face."""
    from .. import extract_frames

    regions: list[tuple[float, float]] = []
    try:
        frames = extract_frames(video_path, frame_interval=period, destination="numpy")
        for k, frame in enumerate(frames):
            # Cap resolution before YuNet: the census only needs to know a face is
            # present, so full 4K frames would waste decode + detection time.
            frame = _cap_frame(frame)
            t = k * period
            if detector.detect(frame):
                regions.append((max(0.0, t - period / 2), t + period / 2))
    except Exception as exc:  # noqa: BLE001
        osh.warning(f"faces.sampling: census failed ({exc}) — assuming faces present")
        return [(0.0, duration)]
    return _merge_spans(regions)


def _merge_spans(spans: list[tuple[float, float]], gap: float = 0.75) -> list[tuple[float, float]]:
    if not spans:
        return []
    spans = sorted(spans)
    out = [list(spans[0])]
    for a, b in spans[1:]:
        if a <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _candidate_windows(
    turns: list[dict],
    face_regions: list[tuple[float, float]],
    shots: list[tuple[float, float]],
    *,
    clip_len: float,
) -> dict[int, list[tuple[float, float, int]]]:
    """Per cluster, propose ``(t0, t1, shot)`` windows where it speaks over a face.

    Windows are ordered to spread across distinct shots first, so a small initial
    batch already samples diverse viewpoints rather than one continuous take.
    """
    cands: dict[int, list[tuple[float, float, int]]] = {}
    for turn in turns:
        spk = int(turn.get("spk", turn.get("speaker", -1)))
        t0, t1 = float(turn["t0"]), float(turn["t1"])
        for reg in face_regions:
            ov = _overlap((t0, t1), reg)
            if ov < min(0.6, clip_len / 2):
                continue
            lo = max(t0, reg[0])
            hi = min(t1, reg[1])
            # Slice the overlap into clip_len windows.
            t = lo
            while t < hi - 0.3:
                w0, w1 = t, min(t + clip_len, hi)
                cands.setdefault(spk, []).append((w0, w1, _shot_of(w0, shots)))
                t = w1
    # Diversity ordering: round-robin over shots within each speaker.
    for spk, wins in cands.items():
        wins.sort(key=lambda w: (w[2], w[0]))
        seen: dict[int, int] = {}
        keyed = []
        for w in wins:
            rank = seen.get(w[2], 0)
            seen[w[2]] = rank + 1
            keyed.append((rank, w[2], w[0], w))
        keyed.sort()
        cands[spk] = [k[3] for k in keyed]
    return cands


class _FaceGallery:
    """Global face identities: assign each track embedding to a face id.

    New embeddings beyond the SFace same-identity cosine threshold spawn a new
    face id — this is what "counts the faces along the video" and stitches tracks
    split by a person leaving and re-entering frame.
    """

    def __init__(self, recognizer: FaceRecognizer, threshold: float = 0.363) -> None:
        self.rec = recognizer
        self.threshold = threshold
        self.embs: list[np.ndarray] = []
        self.counts: list[int] = []

    def assign(self, emb: np.ndarray | None) -> int | None:
        if emb is None:
            return None
        best_id, best_cos = None, self.threshold
        for i, g in enumerate(self.embs):
            c = float(emb @ g)
            if c >= best_cos:
                best_id, best_cos = i, c
        if best_id is None:
            self.embs.append(emb)
            self.counts.append(1)
            return len(self.embs) - 1
        # Running mean keeps the prototype stable.
        n = self.counts[best_id]
        self.embs[best_id] = (self.embs[best_id] * n + emb) / (n + 1)
        self.embs[best_id] /= np.linalg.norm(self.embs[best_id]) + 1e-9
        self.counts[best_id] += 1
        return best_id


def active_speaker_map(
    video_path: str,
    audio_16k: np.ndarray | None,
    speaker_turns: list[dict],
    *,
    asd_engine: str = "auto",
    clip_len: float = 3.0,
    asd_fps: float = 12.0,
    census_period: float = 1.0,
    clip_budget: int = 24,
    per_round: int = 6,
    margin_tau: float = 0.35,
    coverage_floor: float = 0.3,
    asd_tau: float = 0.4,
    rescue_budget: int | None = None,
) -> list[SpeakerFaceAssignment]:
    """Assign each diarization cluster to a global on-screen face via sampled ASD.

    Parameters mirror the design knobs in ``.private/face.md`` §4/§7: ``clip_len``
    and ``asd_fps`` bound per-window cost; ``clip_budget`` caps total heavy work;
    ``margin_tau``/``coverage_floor`` define per-cluster *certainty*; clusters
    below it pull *more* windows until certain or the budget is spent.

    ``rescue_budget`` adds a last-chance pass: if the shared ``clip_budget`` runs out
    while some clusters are still uncertain, resume ASD on just those, drawing from
    their remaining candidate windows, until each is certain, out of windows, or clearly
    not improving (a no-progress guard drops a genuinely off-screen speaker rather than
    burning the machine on it). ``None`` (the default) lets the rescue run until the
    finite window pool or the no-progress guard stops it; an int caps the extra windows.

    Returns one :class:`SpeakerFaceAssignment` per cluster that cleared the vote
    floor. Clusters left uncertain are logged and omitted (caller falls back to
    voiceprint for those).
    """
    import contextlib

    from .. import extract_frames, video_duration

    duration = 0.0
    with contextlib.suppress(Exception):
        duration = float(video_duration(video_path))

    detector = FaceDetector()
    recognizer = FaceRecognizer()
    engine: ASDEngine = get_engine(asd_engine)
    gallery = _FaceGallery(recognizer)

    shots = _detect_shots(video_path)
    if shots == [(0.0, 0.0)]:
        shots = [(0.0, max(duration, 1e9))]
    face_regions = _census(video_path, detector, period=census_period, duration=duration)
    if not face_regions:
        osh.warning("faces.sampling: no faces found in census — no face anchoring possible")
        return []

    candidates = _candidate_windows(speaker_turns, face_regions, shots, clip_len=clip_len)
    speakers = sorted(candidates.keys())
    if not speakers:
        osh.info("faces.sampling: no speaker/face co-occurrence windows — nothing to do")
        return []

    # Vote mass W[spk][face_id], covered speaking time, sampled speech time.
    W: dict[int, dict[int, float]] = {s: {} for s in speakers}
    covered: dict[int, dict[int, float]] = {s: {} for s in speakers}
    sampled: dict[int, float] = dict.fromkeys(speakers, 0.0)
    best_crops: dict[int, list[tuple[float, np.ndarray, Face]]] = {}

    spent = 0
    cursor: dict[int, int] = dict.fromkeys(speakers, 0)
    certain: dict[int, bool] = dict.fromkeys(speakers, False)

    def _process_window(spk: int, w0: float, w1: float) -> None:
        nonlocal spent
        try:
            # Cap the working resolution once, here: detection, tracking, ASD
            # mouth-crops and recognition all run on these frames, so a single
            # aspect-preserving downscale bounds the whole window's compute and
            # memory. Coordinates stay self-consistent (every stage sees the same
            # reduced frames), and the emitted crops are these same frames.
            frames = [
                _cap_frame(fr)
                for fr in extract_frames(
                    video_path,
                    start_instant=w0,
                    end_instant=w1,
                    frame_interval=1.0 / asd_fps,
                    destination="numpy",
                )
            ]
        except Exception as exc:  # noqa: BLE001
            osh.warning(f"faces.sampling: decode window [{w0:.1f},{w1:.1f}] failed ({exc})")
            return
        if not frames:
            return
        frame_dets = [(i, detector.detect(fr)) for i, fr in enumerate(frames)]
        tracks = track_faces(frame_dets)
        if not tracks:
            return
        a = (
            audio_16k[int(w0 * _SR) : int(w1 * _SR)]
            if audio_16k is not None and audio_16k.size
            else np.array([], dtype=np.float32)
        )
        scores = engine.score_tracks(frames, tracks, a, asd_fps)
        dur = w1 - w0
        sampled[spk] += dur
        spent += 1
        # Two tracks in one window can map to the SAME global face (a split track, or
        # the same person in a picture-in-picture). Aggregate per global face id FIRST —
        # taking that face's best speaking score this window — so one window contributes
        # at most `dur` to a face's coverage (else coverage could exceed 1.0).
        per_fid_score: dict[int, float] = {}
        for tr in tracks:
            tr_frames = [frames[j] for j in tr.frame_idx]
            emb = recognizer.embed_track(tr_frames, tr.faces)
            fid = gallery.assign(emb)
            if fid is None:
                continue
            s = float(scores.get(tr.track_id, 0.0))
            per_fid_score[fid] = max(per_fid_score.get(fid, 0.0), s)
            # Keep best crops of this face for the final embedding.
            bucket = best_crops.setdefault(fid, [])
            for j, face in zip(tr.frame_idx, tr.faces, strict=True):
                bucket.append((face.score, frames[j], face))
            bucket.sort(key=lambda x: x[0], reverse=True)
            del bucket[15:]
        for fid, s in per_fid_score.items():
            W[spk][fid] = W[spk].get(fid, 0.0) + dur * s
            if s >= asd_tau:
                covered[spk][fid] = covered[spk].get(fid, 0.0) + dur

    def _assess() -> tuple[dict[int, bool], dict[int, float]]:
        """Per-speaker (is_certain, vote_margin) from the current votes, via a greedy assignment."""
        assignment = _greedy_assign(W, speakers)
        is_certain: dict[int, bool] = {}
        margins: dict[int, float] = {}
        for spk in speakers:
            fid = assignment.get(spk)
            if fid is None:
                is_certain[spk], margins[spk] = False, 0.0
                continue
            votes = W[spk]
            top = votes.get(fid, 0.0)
            second = max((v for k, v in votes.items() if k != fid), default=0.0)
            margin = (top - second) / (top + 1e-9) if top > 0 else 0.0
            cov = min(1.0, covered[spk].get(fid, 0.0) / (sampled[spk] + 1e-9))
            is_certain[spk] = margin >= margin_tau and cov >= coverage_floor and top > 0
            margins[spk] = margin
        return is_certain, margins

    # --- iterative rounds -------------------------------------------------
    round_no = 0
    while spent < clip_budget:
        round_no += 1
        picked = 0
        for spk in speakers:
            if certain[spk]:
                continue
            wins = candidates[spk]
            take = 0
            while cursor[spk] < len(wins) and take < max(1, per_round // max(1, len(speakers))) + 1:
                if spent >= clip_budget:
                    break
                w0, w1, _shot = wins[cursor[spk]]
                cursor[spk] += 1
                _process_window(spk, w0, w1)
                take += 1
                picked += 1
        if picked == 0:
            break  # no windows left to try

        # Re-assess certainty with a greedy one-to-one assignment on current votes.
        certain, _ = _assess()
        if all(certain[s] for s in speakers):
            break

    # --- last-chance rescue: doubt still remains after the shared budget --
    # A cluster may be uncertain only because the common budget ran out before it converged.
    # Resume ASD on just the still-uncertain clusters, drawing from their remaining candidate
    # windows, until each is certain, out of windows, or clearly not improving. The no-progress
    # guard drops a cluster whose margin has not improved for two rescue rounds — a genuinely
    # off-screen speaker never converges, however many windows we add, so we stop burning on it.
    # Bounded by the finite window pool; ``rescue_budget`` caps the extra work when set.
    _, best_margin = _assess()
    stalls: dict[int, int] = dict.fromkeys(speakers, 0)
    gave_up: set[int] = set()
    rescue_start = spent
    while not all(certain[s] or s in gave_up for s in speakers):
        if rescue_budget is not None and spent - rescue_start >= rescue_budget:
            break
        picked = 0
        for spk in speakers:
            if certain[spk] or spk in gave_up or cursor[spk] >= len(candidates[spk]):
                continue
            if rescue_budget is not None and spent - rescue_start >= rescue_budget:
                break
            w0, w1, _shot = candidates[spk][cursor[spk]]
            cursor[spk] += 1
            _process_window(spk, w0, w1)
            picked += 1
        if picked == 0:
            break  # every still-uncertain cluster is out of windows
        certain, margins = _assess()
        for spk in speakers:
            if certain[spk] or spk in gave_up:
                continue
            if margins[spk] > best_margin[spk] + 1e-3:
                best_margin[spk] = margins[spk]
                stalls[spk] = 0
            else:
                stalls[spk] += 1
                if stalls[spk] >= 2:  # no progress on two consecutive rescue rounds → give up
                    gave_up.add(spk)
    if spent > rescue_start:
        osh.info(
            f"faces.sampling: last-chance rescue used {spent - rescue_start} extra ASD windows; "
            f"{sum(1 for s in speakers if not certain[s])} cluster(s) still uncertain (voice anchors)"
        )

    # --- finalise ---------------------------------------------------------
    assignment = _greedy_assign(W, speakers)
    results: list[SpeakerFaceAssignment] = []
    for spk in speakers:
        fid = assignment.get(spk)
        if fid is None or W[spk].get(fid, 0.0) <= 0:
            osh.info(f"faces.sampling: speaker {spk} left face-less (voice will anchor)")
            continue
        votes = W[spk]
        top = votes[fid]
        second = max((v for k, v in votes.items() if k != fid), default=0.0)
        margin = (top - second) / (top + 1e-9)
        cov = min(1.0, covered[spk].get(fid, 0.0) / (sampled[spk] + 1e-9))
        if cov < coverage_floor:
            osh.info(f"faces.sampling: speaker {spk} coverage {cov:.2f} < floor — face not trusted")
            continue
        crops = [(fr, face) for _s, fr, face in best_crops.get(fid, [])]
        results.append(
            SpeakerFaceAssignment(
                speaker=spk, face_id=fid, coverage=float(cov), margin=float(margin), crops=crops
            )
        )
    osh.info(
        f"faces.sampling: {len(results)}/{len(speakers)} clusters face-anchored "
        f"in {spent} ASD windows ({round_no} rounds)"
    )
    return results


def _greedy_assign(W: dict[int, dict[int, float]], speakers: list[int]) -> dict[int, int]:
    """Greedy one-to-one cluster→face assignment maximising vote mass.

    Small matrices, so a greedy pass over the sorted (speaker, face, vote) triples
    is both sufficient and dependency-free (no scipy in video-helper).
    """
    triples: list[tuple[float, int, int]] = []
    for spk in speakers:
        for fid, v in W[spk].items():
            if v > 0:
                triples.append((v, spk, fid))
    triples.sort(reverse=True)
    used_spk: set[int] = set()
    used_face: set[int] = set()
    out: dict[int, int] = {}
    for _v, spk, fid in triples:
        if spk in used_spk or fid in used_face:
            continue
        out[spk] = fid
        used_spk.add(spk)
        used_face.add(fid)
    return out
