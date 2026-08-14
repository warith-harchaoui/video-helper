"""
video_helper.faces.digest
==========================

Build a short, dense **digest video** — a handful of small clips lifted from a long
recording and concatenated end-to-end — so a heavy per-frame model (Active Speaker
Detection, or anything else that wants "the interesting moments" rather than the
whole file) runs once on a compact file instead of many separate seeks into the
original.

Two problems this solves at once:

1. **Cost.** ASD-class models are expensive per frame. Most of a long recording is
   redundant for the purpose of anchoring a diarization cluster to a face: once a
   speaker/face pairing is well-sampled, more footage of the same pairing adds
   little. A digest built from *anchor moments* (see below) concentrates the heavy
   model's attention on the frames that actually matter.
2. **Seek robustness.** Many small independent seeks into one large source file are
   the exact pattern that has triggered real decoder instability on long recordings
   (multithreaded PyAV decode contexts closed mid-stream; see
   :func:`video_helper.main.extract_frames`'s ``_extract_via_pyav`` notes). Building
   the digest is still several seeks into the original, but every later stage (ASD,
   face tracking, re-scoring, human review) reads only the small, uniformly-encoded
   digest file — one open, no further seeking into the fragile long original.

Anchor-driven window selection
-------------------------------
The caller supplies ``anchor_times``: timestamps (seconds) where something
diarization-worthy happens — typically the union of raw (unnamed) diarization
speaker-change instants and shot-change instants, merged and sorted by the caller.
This module is deliberately agnostic about *where* anchors come from: it knows
nothing about diarization or scene detection, only about timestamps.

From the anchors, two complementary window families are built around each fused
anchor ``F[i]`` (anchors closer than ``merge_gap`` seconds collapse to their
midpoint first):

- **Boundary windows** ``[F[i] - window, F[i] + window]`` — centred *on* the
  anchor, where a speaker or shot change is happening and the speaker/face
  identity most needs (re-)confirming.
- **Mid-segment windows** ``[mid - window, mid + window]``, where ``mid`` is the
  midpoint between two consecutive fused anchors (and, at the two ends of the
  timeline, between the start/end of the video and the nearest anchor) — a calm,
  representative sample of an already-established segment, away from any cut.

Overlapping windows are merged (min start, max end) before extraction, so dense
anchor clusters do not produce redundant, near-duplicate clips.

The digest manifest
--------------------
:func:`build_asd_digest` returns (and optionally writes to disk) a list of
:class:`DigestSegment`, one per clip actually placed in the digest, each carrying
both its position **in the digest** (``digest_start``/``digest_end``) and its
corresponding position **in the original source video**
(``source_start``/``source_end``). Any consumer that runs a per-frame model on the
digest and gets a result at digest-time ``t`` maps it back to the original
recording's timeline via the manifest — this is the only way the two timelines are
ever reconciled, so treat it as required bookkeeping, not an optional extra.

Splice-boundary caveat for consumers
-------------------------------------
The digest is a concatenation of clips from *different, non-contiguous* parts of
the source video. Anything that tracks continuity frame-to-frame (face tracking by
IoU, an ASD model's temporal context) **must be reset at every segment boundary**
in the manifest — a face that happens to land in a similar position right after a
splice is coincidence, not continuity. This module does not run any such tracking
itself, so it cannot enforce the reset; it only guarantees the manifest gives every
splice point precisely, in ``digest_start`` order.

Engine independence
--------------------
Nothing here is specific to any Active Speaker Detection engine (Light-ASD, LR-ASD,
a future replacement, or the zero-weight lip-motion proxy in
:mod:`video_helper.faces.asd`). This module only builds a video file and a
timestamp mapping; whichever :class:`~video_helper.faces.asd.ASDEngine` a caller
later runs against the digest is an orthogonal choice.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import os_helper as osh

from ..main import (
    concat_videos,
    extract_video_chunk,
    to_editing_intermediate,
    video_converter,
    video_dimensions,
    video_duration,
)

__all__ = ["DigestSegment", "build_asd_digest"]


@dataclass(frozen=True)
class DigestSegment:
    """One clip placed in the digest, with its two timelines reconciled.

    Attributes
    ----------
    digest_start : float
        Start time (seconds) of this clip within the **digest** video.
    digest_end : float
        End time (seconds) of this clip within the **digest** video.
    source_start : float
        Start time (seconds) of this clip within the **original** source video.
    source_end : float
        End time (seconds) of this clip within the **original** source video.
    """

    digest_start: float
    digest_end: float
    source_start: float
    source_end: float

    def to_source_time(self, digest_time: float) -> float | None:
        """Map a timestamp inside this segment's digest span back to source time.

        Parameters
        ----------
        digest_time : float
            A timestamp (seconds), in the digest's own timeline.

        Returns
        -------
        float or None
            The corresponding source-video timestamp, or ``None`` when
            ``digest_time`` does not fall inside this segment.

        Examples
        --------
        >>> seg = DigestSegment(digest_start=0.0, digest_end=12.0,
        ...                     source_start=340.0, source_end=352.0)
        >>> seg.to_source_time(3.0)
        343.0
        >>> seg.to_source_time(99.0) is None
        True
        """
        if not (self.digest_start <= digest_time <= self.digest_end):
            return None
        return self.source_start + (digest_time - self.digest_start)


def _fuse_anchors(anchor_times: list[float], merge_gap: float) -> list[float]:
    """Collapse anchors closer than ``merge_gap`` seconds to their group midpoint.

    Parameters
    ----------
    anchor_times : list of float
        Sorted, deduplicated anchor timestamps (seconds).
    merge_gap : float
        Two consecutive anchors closer than this collapse into the same group.

    Returns
    -------
    list of float
        One midpoint per group, in increasing order.

    Examples
    --------
    >>> _fuse_anchors([10.0, 11.0, 40.0], merge_gap=12.0)
    [10.5, 40.0]
    """
    if not anchor_times:
        return []
    groups: list[list[float]] = [[anchor_times[0]]]
    for t in anchor_times[1:]:
        if t - groups[-1][-1] < merge_gap:
            groups[-1].append(t)
        else:
            groups.append([t])
    return [sum(g) / len(g) for g in groups]


def _candidate_ranges(
    fused: list[float], duration: float, window: float
) -> list[tuple[float, float]]:
    """Boundary + mid-segment windows around fused anchors, clipped to the video.

    Parameters
    ----------
    fused : list of float
        Fused anchor timestamps (see :func:`_fuse_anchors`), increasing order.
    duration : float
        Total video duration (seconds) — windows are clipped to ``[0, duration]``.
    window : float
        Half-width (seconds): each window is ``[centre - window, centre + window]``.

    Returns
    -------
    list of (float, float)
        Unmerged, clipped ``(start, end)`` windows: one boundary window per fused
        anchor, plus one mid-segment window between every consecutive pair of
        fused anchors AND between the video's start/end and the nearest anchor
        (so the very first and last stretches of the video are not left unsampled
        just because no anchor happens to be close by).
    """
    centres: list[float] = list(fused)
    # Mid-segment points: between consecutive fused anchors...
    for a, b in zip(fused, fused[1:], strict=False):
        centres.append((a + b) / 2.0)
    # ...and between the timeline's own start/end and the nearest anchor, so the
    # opening and closing stretches of the video get a mid-segment sample too.
    if fused:
        centres.append(fused[0] / 2.0)
        centres.append((fused[-1] + duration) / 2.0)
    else:
        centres.append(duration / 2.0)  # no anchors at all: one sample, mid-video

    ranges = []
    for c in centres:
        start = max(0.0, c - window)
        end = min(duration, c + window)
        if end > start:
            ranges.append((start, end))
    return ranges


def _merge_overlapping(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Merge overlapping/touching ``(start, end)`` ranges (min start, max end).

    Parameters
    ----------
    ranges : list of (float, float)
        Unsorted candidate ranges.

    Returns
    -------
    list of (float, float)
        Sorted, non-overlapping ranges.

    Examples
    --------
    >>> _merge_overlapping([(0.0, 5.0), (4.0, 9.0), (20.0, 22.0)])
    [(0.0, 9.0), (20.0, 22.0)]
    """
    if not ranges:
        return []
    ordered = sorted(ranges)
    merged = [list(ordered[0])]
    for start, end in ordered[1:]:
        if start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def build_asd_digest(
    video_path: str,
    anchor_times: list[float],
    output_video: str,
    *,
    window: float = 6.0,
    merge_gap: float = 12.0,
) -> list[DigestSegment]:
    """Build a compact digest video from anchor-driven windows of ``video_path``.

    See the module docstring for the full design (why a digest, how windows are
    chosen, the splice-boundary caveat for consumers). In short: fuse nearby
    anchors to their midpoint, form a boundary window around each fused anchor and
    a mid-segment window between consecutive anchors (and at the two ends of the
    timeline), merge overlapping windows, then build the digest in three phases:

    1. **Transcode once** — :func:`~video_helper.main.to_editing_intermediate`
       turns the source into an all-keyframe (GOP 1), PCM-audio intermediate.
       Every timestamp in it is a valid, lossless, frame-accurate cut point.
    2. **Cut + concat on the intermediate** — each window is lifted with
       :func:`~video_helper.main.extract_video_chunk` (``copy=True``, pure
       stream-copy, no re-encode) and the clips are stitched with
       :func:`~video_helper.main.concat_videos` (``reencode=False``), safe
       because every chunk shares the intermediate's exact codec/timebase.
    3. **Final encode** — the stitched intermediate (huge, all-keyframe/PCM) is
       re-encoded once via :func:`~video_helper.main.video_converter` down to a
       normal delivery-sized file, audio included.

    Doing the heavy per-window work as stream-copy and re-encoding only once, at
    the end, keeps the digest audio-safe and avoids paying a re-encode cost per
    window (see :func:`~video_helper.main.concat_videos` for why re-encoding a
    concat directly, `reencode=True`, used to silently drop audio).

    Parameters
    ----------
    video_path : str
        Path to the source video.
    anchor_times : list of float
        Timestamps (seconds) where something diarization-worthy happens — the
        caller's merged, sorted union of e.g. raw diarization speaker-change
        instants and shot-change instants. This function does not know or care
        where they came from.
    output_video : str
        Path to write the concatenated digest video (with audio).
    window : float, optional
        Half-width in seconds of every extracted window (default 6.0 — a full
        window is then ``2 * window`` = 12s, comfortably covering the 1-6s
        duration range LR-ASD's own evaluation methodology uses for reliability).
    merge_gap : float, optional
        Anchors closer than this (seconds) fuse to one midpoint before windows
        are formed (default 12.0).

    Returns
    -------
    list of DigestSegment
        One entry per clip actually placed in the digest, in digest-time order.
        Also written alongside ``output_video`` as ``<output_video>.manifest.json``
        (a JSON array of ``{digest_start, digest_end, source_start, source_end}``).

    Raises
    ------
    AssertionError
        If ``video_path`` is not a valid video, or no windows could be formed.

    Notes
    -----
    Splice boundaries (every ``digest_start``/``digest_end`` pair in the returned
    manifest) are real discontinuities: any frame-to-frame continuity assumption
    (face tracking, an ASD model's own temporal context) must be reset there by
    the caller. This function only builds the video and the mapping; it runs no
    tracking or detection itself, so it has no opinion on which engine consumes
    the digest — Light-ASD, LR-ASD, or anything else conforming to
    :class:`video_helper.faces.asd.ASDEngine`.

    Examples
    --------
    >>> segs = build_asd_digest(  # doctest: +SKIP
    ...     "meeting.mp4", anchor_times=[12.0, 340.0, 341.0, 900.0],
    ...     output_video="digest.mp4",
    ... )
    >>> segs[0].source_start  # doctest: +SKIP
    0.0
    """
    from .. import is_valid_video_file  # local: avoid a package-init cycle

    assert is_valid_video_file(video_path), f"Not a valid video: {video_path}"
    duration = video_duration(video_path)

    fused = _fuse_anchors(sorted(set(anchor_times)), merge_gap)
    ranges = _merge_overlapping(_candidate_ranges(fused, duration, window))
    assert ranges, f"build_asd_digest: no windows could be formed for {video_path}"

    segments: list[DigestSegment] = []
    chunk_paths: list[str] = []
    with osh.temporary_folder(prefix="asd-digest") as tmp_dir:
        # Phase 1: transcode once to an edit-friendly, all-keyframe/PCM intermediate
        # — every timestamp in it is a safe, frame-accurate, lossless cut point.
        intermediate = osh.join(tmp_dir, "intermediate.mp4")
        to_editing_intermediate(video_path, intermediate)

        # Phase 2: cut each window and concat, both as pure stream-copy on the
        # intermediate — no per-window re-encode cost, audio carried through as-is.
        cursor = 0.0
        for i, (src_start, src_end) in enumerate(ranges):
            chunk_path = osh.join(tmp_dir, f"chunk_{i:04d}.mp4")
            extract_video_chunk(intermediate, src_start, src_end, chunk_path, copy=True)
            chunk_dur = video_duration(chunk_path)
            segments.append(
                DigestSegment(
                    digest_start=cursor,
                    digest_end=cursor + chunk_dur,
                    source_start=src_start,
                    source_end=src_end,
                )
            )
            chunk_paths.append(chunk_path)
            cursor += chunk_dur

        concat_intermediate = osh.join(tmp_dir, "concat_intermediate.mp4")
        concat_videos(chunk_paths, concat_intermediate, reencode=False)

        # Phase 3: one final encode pass down to a normal delivery-sized file.
        # Passing frame_rate forces video_converter's real transcode path (rather
        # than its same-container stream-copy shortcut), so audio is re-encoded
        # (AAC) and carried through rather than silently dropped.
        fps = video_dimensions(concat_intermediate)["frame_rate"]
        video_converter(concat_intermediate, output_video, frame_rate=fps)

    manifest_path = f"{output_video}.manifest.json"
    _write_manifest(segments, manifest_path)
    osh.info(
        f"faces.digest: built {output_video} from {len(segments)} window(s) "
        f"({sum(s.digest_end - s.digest_start for s in segments):.1f}s digest "
        f"from a {duration:.1f}s source) — manifest at {manifest_path}"
    )
    return segments


def source_to_digest_window(
    segments: list[DigestSegment], source_start: float, source_end: float
) -> tuple[float, float] | None:
    """Map a ``[source_start, source_end]`` span back into digest-time, if covered.

    The reverse of :meth:`DigestSegment.to_source_time`: a caller with a window in
    the *original* video's timeline (e.g. an ASD candidate window) uses this to
    find where — if anywhere — that span landed in the digest, so it can read
    frames from the small digest file instead of seeking into the original.

    Parameters
    ----------
    segments : list of DigestSegment
        The digest's manifest, as returned by :func:`build_asd_digest`.
    source_start, source_end : float
        A time span (seconds) in the **source** video's timeline.

    Returns
    -------
    (float, float) or None
        The corresponding ``(digest_start, digest_end)`` span, or ``None`` when no
        single digest segment fully covers ``[source_start, source_end]`` — this
        happens whenever the requested span was not anchor-driven into the digest
        (e.g. it falls between digest windows, or straddles a splice boundary).
        Callers should fall back to reading the original video in that case.

    Examples
    --------
    >>> segs = [DigestSegment(0.0, 12.0, 340.0, 352.0)]
    >>> source_to_digest_window(segs, 342.0, 345.0)
    (2.0, 5.0)
    >>> source_to_digest_window(segs, 400.0, 403.0) is None
    True
    """
    for seg in segments:
        if seg.source_start <= source_start and source_end <= seg.source_end:
            offset = seg.digest_start - seg.source_start
            return (source_start + offset, source_end + offset)
    return None


def _write_manifest(segments: list[DigestSegment], path: str) -> None:
    """Write ``segments`` as a JSON array to ``path`` (see :func:`build_asd_digest`)."""
    import json

    payload = [
        {
            "digest_start": s.digest_start,
            "digest_end": s.digest_end,
            "source_start": s.source_start,
            "source_end": s.source_end,
        }
        for s in segments
    ]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def load_manifest(path: str) -> list[DigestSegment]:
    """Read back a manifest written by :func:`build_asd_digest`.

    Parameters
    ----------
    path : str
        Path to a ``<output_video>.manifest.json`` file.

    Returns
    -------
    list of DigestSegment
        The segments, in the order they were written (digest-time order).
    """
    import json

    with open(path, encoding="utf-8") as fh:
        payload = json.load(fh)
    return [DigestSegment(**row) for row in payload]
