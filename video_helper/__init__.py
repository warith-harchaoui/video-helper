"""
video_helper
============

Multi-backend frame extraction (VidGear / PyAV / ffmpeg-pipe), video
conversion, subtitle muxing, and lightweight image-ops glue for the AI
Helpers suite.

Multi-surface exposure
----------------------
Every public function below is reachable from four surfaces:

- Python library import (this module).
- CLI: ``video-helper`` (always installed).
- FastAPI HTTP: ``video_helper.api`` (needs the ``[api]`` extra), which
  also serves a minimal browser "video bench" GUI at ``GET /gui``.
- MCP: ``video-helper-mcp`` (needs the ``[mcp]`` extra), the same FastAPI
  app with tools auto-published at ``/mcp``.

Usage Example
-------------
>>> import video_helper as vh
>>> for frame in vh.extract_frames("clip.mp4", frame_interval=1.0):
...     # frame.shape == (H, W, 3), BGR uint8 (OpenCV convention)
...     do_something(frame)

See ``EXAMPLES.md`` at the repo root for the full cookbook (sparse
access, torch / pil destinations, batched yields, hwaccel, http_headers
for yt-dlp-resolved sources, scale-fit-and-pad, …).

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

import os as _os

# Enable Apple-Silicon MPS with a CPU fallback for the few ops lacking an MPS kernel (the
# faces/Light-ASD ``max_pool3d``, some RNNs). Must be set BEFORE torch is first imported, so it
# lives at package import — the earliest hook a ``video_helper`` caller runs. With it, Light-ASD
# runs on MPS ~2.5x faster than CPU with bit-identical scores; without it a missing op hard-errors.
# ``setdefault`` lets an explicit ``PYTORCH_ENABLE_MPS_FALLBACK=0`` still win.
_os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# Package-level metadata — kept in sync with pyproject.toml on release.
__author__ = "Warith Harchaoui, Ph.D."
__email__ = "warithmetics@deraison.ai"

# Import the public surface from ``main``. Names re-exported here are
# what downstream callers should rely on; anything not listed in
# ``__all__`` is considered private.
# The timed-text layer is imported eagerly: it is stdlib plus os-helper, so it
# costs nothing, and it is the one part of this package the speech packages of
# the suite reach for.
from .subtitles import (
    ABBREVIATIONS,
    Cue,
    format_timestamp,
    from_centiseconds,
    parse,
    split_sentences,
    vtt2srt,
    write,
    write_srt,
    write_vtt,
)

#: Which module each remaining public name lives in, resolved on first use.
#:
#: Everything in ``main`` and ``flow`` pulls OpenCV, vidgear, ffmpeg-python and
#: numpy, about a second of import time and a hundred megabytes of wheels.
#: That is the right price for decoding video and the wrong one for writing a
#: caption file, and since 2026-10-31 this package holds both: the subtitle
#: layer moved here from ``sprezzature-audio``, so a package whose whole job is
#: speech now imports this one. Reaching ``video_helper.subtitles`` used to run
#: this module's eager imports and pay for OpenCV anyway, which made the
#: promise in that module's docstring false. PEP 562 makes it true.
#:
#: Every name stays reachable exactly as before, by attribute or by
#: ``from video_helper import …``; only the moment of the import changes.
_LAZY_EXPORTS: dict[str, str] = {
    # .main
    "black_video": ".main",
    "burn_subtitles": ".main",
    "compress_video": ".main",
    "concat_videos": ".main",
    "dump_frames": ".main",
    "extract_audio_track": ".main",
    "extract_frames": ".main",
    "extract_unique_colors": ".main",
    "extract_video_chunk": ".main",
    "hw_vcodec": ".main",
    "image_loop_to_video": ".main",
    "is_valid_video_file": ".main",
    "mux_audio_video": ".main",
    "overlay_image": ".main",
    "srt2vtt": ".main",
    "video_converter": ".main",
    "video_dimensions": ".main",
    "video_duration": ".main",
    # .flow
    "extract_optical_flow": ".flow",
    "iter_frame_optical_flow": ".flow",
    "resize_flow": ".flow",
}


def __getattr__(name: str) -> object:
    """Resolve a heavy public name on first use (PEP 562).

    Parameters
    ----------
    name : str
        The attribute asked for.

    Returns
    -------
    object
        The function, imported from its module and then cached in this
        module's namespace so the second access costs nothing.

    Raises
    ------
    AttributeError
        For a name this package does not export, with the same message a
        normal module would give.
    """
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name, __name__), name)
    # Cache in the module namespace: `__getattr__` is only consulted when the
    # normal lookup fails, so this makes every later access a plain dict hit.
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """The public surface, lazy names included, so tab-completion still works."""
    return sorted(set(__all__) | set(globals()))


# Define the public API for the library
__all__ = [
    "iter_frame_optical_flow",
    "extract_optical_flow",
    "resize_flow",
    "extract_unique_colors",
    "srt2vtt",
    "is_valid_video_file",
    "video_dimensions",
    "video_converter",
    "extract_frames",
    "dump_frames",
    "extract_video_chunk",
    "video_duration",
    "compress_video",
    "black_video",
    "image_loop_to_video",
    "concat_videos",
    "overlay_image",
    "extract_audio_track",
    "mux_audio_video",
    "burn_subtitles",
    "hw_vcodec",
    # Subtitles: the format layer
    "Cue",
    "parse",
    "write",
    "write_vtt",
    "write_srt",
    "vtt2srt",
    "format_timestamp",
    "from_centiseconds",
    "split_sentences",
    "ABBREVIATIONS",
]
