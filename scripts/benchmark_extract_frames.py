"""
Per-backend benchmark for ``extract_frames``, with a real cross-axis matrix.

Sweeps:

- **Resolution**     : 360p, 720p, 1080p
- **Codec**          : H.264 (universal), HEVC/H.265 (most platforms)
- **Access pattern** : full sequential, windowed (1s at mid), sparse (12 evenly-spaced)
- **Backend**        : vidgear, pyav, ffmpeg-pipe (subject to availability)
- **Hwaccel**        : None (software), "auto" (VideoToolbox/CUDA/QSV when supported)

For every cell we measure:

- **Wall time**  (``osh.wall_timer``) — what the user sees.
- **CPU time**   (``osh.cpu_timer``)  — actual work done on the CPU (sums
  across threads, excludes GPU/media-engine and subprocess work).

The **CPU/Wall ratio** is the key signal: ~1.0 means the work is on the
CPU; <1 means it's been offloaded (e.g. to VideoToolbox / NVDEC) or
moved into a subprocess (ffmpeg-pipe).

Test clips are generated on the fly via ffmpeg's ``testsrc2`` source so
decode complexity is non-trivial (unlike a pure-black clip whose
intra-frames compress to nothing).

Usage:
    PYTHONPATH=. python scripts/benchmark_extract_frames.py
    PYTHONPATH=. python scripts/benchmark_extract_frames.py --resolutions 720p,1080p --codecs h264
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

import os_helper as osh

import video_helper as vh
from video_helper.main import _have_pyav

osh.verbosity(0)


# ---------------------------------------------------------------------------
# Configuration matrix.
# ---------------------------------------------------------------------------

RESOLUTIONS = {
    "360p": (640, 360),
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "4k": (3840, 2160),  # opt-in via --resolutions: encoding takes ~30-90s
}

# Codec → (ffmpeg encoder, tag for display). HEVC is libx265 (slow encode,
# fast decode); we accept the encode cost once when generating the clip.
CODECS = {
    "h264": ("libx264", "H.264"),
    "hevc": ("libx265", "HEVC/H.265"),
}

CLIP_DURATION_S = 10.0
CLIP_FPS = 30
BENCH_RUNS = 3  # report best of N


@dataclass
class Cell:
    """One measured point of the benchmark matrix.

    A cell fixes every axis (resolution, codec, access pattern, backend,
    hwaccel) and stores the timing results for that combination.

    Attributes
    ----------
    resolution, codec, pattern, backend : str
        The four categorical axes of the matrix.
    hwaccel : str or None
        Hardware-acceleration mode, or ``None`` for pure-software decode.
    wall_ms, cpu_ms : float
        Best wall time and mean CPU time (milliseconds) across the runs.
    frames : int
        Number of frames yielded by the last run.
    """

    resolution: str
    codec: str
    pattern: str
    backend: str
    hwaccel: str | None
    wall_ms: float
    cpu_ms: float
    frames: int

    @property
    def cpu_wall_ratio(self) -> float:
        """Return CPU/wall time ratio (the offload signal).

        Returns
        -------
        float
            ``cpu_ms / wall_ms`` (``0.0`` when wall time is non-positive).
            ~1.0 means CPU-bound; <1 hints at GPU / media-engine offload.
        """
        return self.cpu_ms / self.wall_ms if self.wall_ms > 0 else 0.0

    @property
    def fps(self) -> float:
        """Return throughput in frames per second for this cell.

        Returns
        -------
        float
            ``frames / wall_seconds`` (``0.0`` when wall time is non-positive).
        """
        return self.frames * 1000.0 / self.wall_ms if self.wall_ms > 0 else 0.0


# ---------------------------------------------------------------------------
# Clip generation — animated test pattern, not a black frame.
# ---------------------------------------------------------------------------


def _generate_clip(out_path: Path, width: int, height: int, encoder: str) -> None:
    """Render a 10-second 30fps testsrc2 clip with the given encoder."""
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size={width}x{height}:rate={CLIP_FPS}:duration={CLIP_DURATION_S}",
        "-c:v",
        encoder,
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


# ---------------------------------------------------------------------------
# Bench primitive.
# ---------------------------------------------------------------------------


def _bench_one(make_iter: Callable[[], Iterable]) -> tuple[float, float, int]:
    """Run the iterable BENCH_RUNS times; return (best wall ms, mean cpu ms, frame count of last run)."""
    best_wall = float("inf")
    cpu_totals: list[float] = []
    count = 0
    for _ in range(BENCH_RUNS):
        with osh.wall_timer() as w, osh.cpu_timer() as c:
            count = sum(1 for _ in make_iter())
        if w["milliseconds"] < best_wall:
            best_wall = w["milliseconds"]
        cpu_totals.append(c["milliseconds"])
    return best_wall, sum(cpu_totals) / len(cpu_totals), count


# ---------------------------------------------------------------------------
# Cell builder — for one (clip, pattern, backend, hwaccel) point.
# ---------------------------------------------------------------------------


def _patterns_for(clip: str) -> list[tuple[str, Callable[[str, str, str | None], Iterable]]]:
    """Return [(pattern_name, make_iter(backend, hwaccel, clip))] for this clip."""
    info = vh.video_dimensions(clip)
    total = int(info["duration"] * info["frame_rate"])
    mid_start = info["duration"] / 2.0
    # Twelve evenly-spaced indices across the clip — deterministic (no RNG) so
    # the sparse-access benchmark is reproducible run to run.
    sparse_spaced = list(range(0, total, max(1, total // 12)))[:12]

    return [
        (
            "full",
            lambda backend, hw, c: vh.extract_frames(c, backend=backend, hwaccel=hw),
        ),
        (
            "windowed-1s",
            lambda backend, hw, c: vh.extract_frames(
                c,
                start_instant=mid_start,
                end_instant=mid_start + 1.0,
                backend=backend,
                hwaccel=hw,
            ),
        ),
        (
            "sparse-12",
            lambda backend, hw, c: vh.extract_frames(
                c,
                frame_indices=sparse_spaced,
                backend=backend,
                hwaccel=hw,
            ),
        ),
    ]


def _backends_for(pattern: str) -> list[str]:
    """List the extraction backends that support a given access pattern.

    Parameters
    ----------
    pattern : str
        Access-pattern name (``"full"`` / ``"windowed-1s"`` / ``"sparse-12"``).

    Returns
    -------
    list[str]
        Available backends, filtered by capability and what's installed.
    """
    # vidgear is always present (a core dependency); pyav / ffmpeg-pipe are
    # probed so the matrix only benches what the machine can actually run.
    available = ["vidgear"]
    if _have_pyav():
        available.append("pyav")
    if shutil.which("ffmpeg") is not None:
        available.append("ffmpeg-pipe")
    if pattern.startswith("sparse"):
        # ffmpeg-pipe streams sequentially — it cannot do sparse index access.
        return [b for b in available if b != "ffmpeg-pipe"]
    return available


def _hwaccels_for(backend: str) -> list[str | None]:
    """List the hwaccel modes worth benchmarking for a backend.

    Parameters
    ----------
    backend : str
        Backend name.

    Returns
    -------
    list[str | None]
        ``[None]`` for software-only backends, ``[None, "auto"]`` for those
        that can offload decode to a hardware media engine.
    """
    # Only pyav and ffmpeg-pipe honor hwaccel today; vidgear is software-only,
    # so benching "auto" there would just duplicate the None row.
    if backend in ("pyav", "ffmpeg-pipe"):
        return [None, "auto"]
    return [None]


# ---------------------------------------------------------------------------
# Reporting.
# ---------------------------------------------------------------------------


def _format_cell(c: Cell) -> str:
    """Render one benchmark cell as a fixed-width, human-readable line.

    Parameters
    ----------
    c : Cell
        The measured cell to format.

    Returns
    -------
    str
        Aligned single-line summary (pattern, backend, hwaccel, timings, fps).
    """
    hw = c.hwaccel if c.hwaccel is not None else "-"
    return (
        f"  {c.pattern:<12} {c.backend:<12} {hw:<6}"
        f" wall={c.wall_ms:>7.1f}ms  cpu={c.cpu_ms:>7.1f}ms"
        f"  cpu/wall={c.cpu_wall_ratio:>4.2f}x  ({c.frames:>4d} frames, {c.fps:>7.1f} fps)"
    )


def _emit_block(resolution: str, codec: str, cells: list[Cell]) -> None:
    """Print all cells for one (resolution, codec) block, grouped by pattern.

    Parameters
    ----------
    resolution : str
        Resolution key (e.g. ``"720p"``).
    codec : str
        Codec key (e.g. ``"h264"``).
    cells : list[Cell]
        Measured cells belonging to this block.
    """
    res_wh = RESOLUTIONS[resolution]
    codec_label = CODECS[codec][1]
    print(f"=== {resolution} ({res_wh[0]}x{res_wh[1]}) — {codec_label} ===")
    # Group by pattern for readability.
    by_pattern: dict[str, list[Cell]] = {}
    for c in cells:
        by_pattern.setdefault(c.pattern, []).append(c)
    # We only need the grouped cells; the pattern key itself is unused here
    # (each Cell already carries its ``pattern``), hence ``_pattern``.
    for _pattern, ps in by_pattern.items():
        for c in ps:
            print(_format_cell(c))
    print()


# ---------------------------------------------------------------------------
# Main.
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse CLI arguments, generate fixtures, run the matrix, and print it.

    Drives the whole benchmark: reads ``--resolutions`` / ``--codecs`` /
    ``--torch-device``, generates a test clip per (resolution, codec), then
    sweeps every (pattern, backend, hwaccel) cell and prints one block per
    fixture. Side effects only (stdout); returns nothing.
    """
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    # 4K is opt-in: HEVC encoding at 3840×2160 takes ~30-90 s per fixture.
    default_resolutions = [r for r in RESOLUTIONS if r != "4k"]
    parser.add_argument(
        "--resolutions",
        default=",".join(default_resolutions),
        help=f"comma-separated subset of {list(RESOLUTIONS)} (default skips 4k)",
    )
    parser.add_argument(
        "--codecs", default=",".join(CODECS), help=f"comma-separated subset of {list(CODECS)}"
    )
    parser.add_argument(
        "--torch-device",
        default=None,
        help="If set (cpu|mps|cuda|auto), also bench destination='torch' "
        "with batch_size=16 on the given device.",
    )
    args = parser.parse_args()

    resolutions = [r.strip() for r in args.resolutions.split(",") if r.strip()]
    codecs = [c.strip() for c in args.codecs.split(",") if c.strip()]

    bad_res = [r for r in resolutions if r not in RESOLUTIONS]
    bad_codec = [c for c in codecs if c not in CODECS]
    if bad_res or bad_codec:
        sys.exit(f"unknown resolutions/codecs: {bad_res} / {bad_codec}")

    print(
        f"Bench: {len(resolutions)} resolutions × {len(codecs)} codecs "
        f"× 3 patterns × backends (vidgear/pyav/ffmpeg-pipe) × hwaccels"
    )
    print(f"  resolutions: {resolutions}")
    print(f"  codecs:      {codecs}")
    print(
        f"  clip:        {CLIP_DURATION_S}s @ {CLIP_FPS}fps (testsrc2 — animated, non-trivial decode)"
    )
    print(f"  runs/cell:   {BENCH_RUNS} (best wall, mean cpu)")
    print()

    with tempfile.TemporaryDirectory(prefix="extract-frames-bench-") as tmp:
        tmp_path = Path(tmp)
        for res in resolutions:
            w, h = RESOLUTIONS[res]
            for codec in codecs:
                encoder, label = CODECS[codec]
                clip = tmp_path / f"{res}-{codec}.mp4"
                print(f"[generating] {res} {label} → {clip.name} ...", flush=True)
                _generate_clip(clip, w, h, encoder)

                cells: list[Cell] = []
                for pattern, make_iter in _patterns_for(str(clip)):
                    for backend in _backends_for(pattern):
                        for hw in _hwaccels_for(backend):
                            try:
                                # Bind the loop variables as lambda defaults so
                                # each closure captures the *current* iteration's
                                # values, not the final ones (ruff B023).
                                wall, cpu, frames = _bench_one(
                                    lambda mk=make_iter, b=backend, h=hw, cp=str(clip): mk(b, h, cp)
                                )
                                cells.append(
                                    Cell(
                                        resolution=res,
                                        codec=codec,
                                        pattern=pattern,
                                        backend=backend,
                                        hwaccel=hw,
                                        wall_ms=wall,
                                        cpu_ms=cpu,
                                        frames=frames,
                                    )
                                )
                            except Exception as exc:
                                print(
                                    f"  {pattern:<12} {backend:<12} {hw}: ERROR {type(exc).__name__}: {exc}"
                                )

                # Optional: torch destination cells (PyAV + batch_size=16).
                # We only run this for the 'full' pattern — the wins (or losses)
                # of host→device transfer are most visible there.
                if args.torch_device:
                    for hw in (None, "auto"):
                        label = f"torch[{args.torch_device}, bs=16]"
                        try:
                            # Same B023 guard: capture ``clip`` and ``hw`` for
                            # this iteration via default arguments.
                            wall, cpu, frames = _bench_one(
                                lambda cp=str(clip), h=hw: vh.extract_frames(
                                    cp,
                                    backend="pyav",
                                    hwaccel=h,
                                    destination="torch",
                                    device=args.torch_device,
                                    batch_size=16,
                                )
                            )
                            # `frames` here counts batches, not frames — rescale.
                            cells.append(
                                Cell(
                                    resolution=res,
                                    codec=codec,
                                    pattern="full",
                                    backend=label,
                                    hwaccel=hw,
                                    wall_ms=wall,
                                    cpu_ms=cpu,
                                    frames=frames * 16,
                                )
                            )
                        except Exception as exc:
                            print(f"  full {label} hw={hw}: ERROR {type(exc).__name__}: {exc}")

                _emit_block(res, codec, cells)


if __name__ == "__main__":
    main()
