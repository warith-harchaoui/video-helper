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
- Argparse CLI: ``video-helper`` (stdlib-only, always installed).
- Click CLI: ``video-helper-click`` (needs the ``[cli]`` extra).
- FastAPI HTTP: ``video_helper.api`` (needs the ``[api]`` extra).
- MCP server: ``video-helper-mcp`` (needs the ``[api,mcp]`` extras).

Usage Example
-------------
>>> import video_helper as vh
>>> for frame in vh.extract_frames("clip.mp4", frame_interval=1.0):
...     # frame.shape == (H, W, 3) — BGR uint8 (OpenCV convention)
...     do_something(frame)

See ``EXAMPLES.md`` at the repo root for the full cookbook (sparse
access, torch / pil destinations, batched yields, hwaccel, http_headers
for yt-dlp-resolved sources, scale-fit-and-pad, …).

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

# Package-level metadata — kept in sync with pyproject.toml on release.
__author__ = "Warith Harchaoui, Ph.D."
__email__ = "warithmetics@deraison.ai"

# Import the public surface from ``main``. Names re-exported here are
# what downstream callers should rely on; anything not listed in
# ``__all__`` is considered private.
from .main import (
    extract_unique_colors,
    srt2vtt,
    is_valid_video_file,
    video_dimensions,
    video_converter,
    extract_frames,
    dump_frames,
    extract_video_chunk,
    video_duration,
    black_video,
    image_loop_to_video,
    concat_videos,
    overlay_image,
    extract_audio_track,
    mux_audio_video,
    burn_subtitles,
)

# Define the public API for the library
__all__ = [
    'extract_unique_colors',
    'srt2vtt',
    'is_valid_video_file',
    'video_dimensions',
    'video_converter',
    'extract_frames',
    'dump_frames',
    'extract_video_chunk',
    'video_duration',
    'black_video',
    'image_loop_to_video',
    'concat_videos',
    'overlay_image',
    'extract_audio_track',
    'mux_audio_video',
    'burn_subtitles',
]
