"""
video_helper.faces.track
=========================

Lightweight multi-face tracking: greedy association by intersection-over-union
(IoU, how much two boxes overlap divided by how much space they cover together,
1.0 for a perfect match, 0.0 for no overlap at all), in the style of SORT/
ByteTrack, pure NumPy, no model weights. Meeting / talking-head video moves
slowly, so IoU linking with a short "coast" through missed frames is enough to
build coherent face **tracks**: the unit ASD and recognition actually operate on.

Face-embedding-based *stitching* of tracks that a person split by leaving and
re-entering frame is handled one level up (in the resolver, where embeddings are
already computed): the face analogue of voiceprint re-identification.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .detect import Face


def _iou(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    x0, y0 = max(ax, bx), max(ay, by)
    x1, y1 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
    inter = max(0.0, x1 - x0) * max(0.0, y1 - y0)
    union = aw * ah + bw * bh - inter
    return inter / union if union > 0 else 0.0


@dataclass
class FaceTrack:
    """A temporally coherent sequence of one face's detections.

    Attributes
    ----------
    track_id : int
        Stable id across the video (subject to stitching upstream).
    frame_idx : list[int]
        Absolute frame indices where the face was seen.
    faces : list[Face]
        The per-frame detection at each ``frame_idx``.
    """

    track_id: int
    frame_idx: list[int] = field(default_factory=list)
    faces: list[Face] = field(default_factory=list)

    def add(self, frame_idx: int, face: Face) -> None:
        self.frame_idx.append(frame_idx)
        self.faces.append(face)

    @property
    def last_box(self) -> tuple[float, float, float, float]:
        return self.faces[-1].box

    def span(self, fps: float) -> tuple[float, float]:
        """Track time span ``(t0, t1)`` in seconds given the sampling ``fps``."""
        return (self.frame_idx[0] / fps, self.frame_idx[-1] / fps)


def track_faces(
    frame_dets: list[tuple[int, list[Face]]],
    *,
    iou_threshold: float = 0.3,
    max_gap: int = 15,
) -> list[FaceTrack]:
    """Link per-frame detections into tracks by greedy IoU association.

    Parameters
    ----------
    frame_dets : list[tuple[int, list[Face]]]
        ``(frame_idx, faces)`` in increasing frame order.
    iou_threshold : float, optional
        Minimum IoU to attach a detection to an existing track.
    max_gap : int, optional
        How many frames a track may coast unmatched before it is retired (lets a
        track survive a brief miss / occlusion).

    Returns
    -------
    list[FaceTrack]
        All tracks discovered, in creation order.
    """
    tracks: list[FaceTrack] = []
    active: list[tuple[FaceTrack, int]] = []  # (track, last_seen_frame_idx)
    next_id = 0

    for frame_idx, faces in frame_dets:
        # Retire tracks that have coasted past max_gap.
        active = [(t, seen) for (t, seen) in active if frame_idx - seen <= max_gap]

        assigned: set[int] = set()
        for tr, _seen in active:
            best_j, best_iou = -1, iou_threshold
            for j, f in enumerate(faces):
                if j in assigned:
                    continue
                v = _iou(tr.last_box, f.box)
                if v >= best_iou:
                    best_j, best_iou = j, v
            if best_j >= 0:
                tr.add(frame_idx, faces[best_j])
                assigned.add(best_j)

        # Refresh last-seen for tracks that matched this frame.
        seen_now = {id(t): (t, frame_idx) for (t, _s) in active if t.frame_idx[-1] == frame_idx}
        active = [seen_now.get(id(t), (t, s)) for (t, s) in active]

        # New tracks for unmatched detections.
        for j, f in enumerate(faces):
            if j in assigned:
                continue
            tr = FaceTrack(track_id=next_id)
            tr.add(frame_idx, f)
            next_id += 1
            tracks.append(tr)
            active.append((tr, frame_idx))

    return tracks
