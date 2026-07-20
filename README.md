# Video Helper

[🇫🇷](https://github.com/warith-harchaoui/video-helper/blob/main/LISEZMOI.md) · [🇬🇧](https://github.com/warith-harchaoui/video-helper/blob/main/README.md)

[![CI](https://github.com/warith-harchaoui/video-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/video-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://github.com/warith-harchaoui/video-helper/blob/main/LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#) [![Local-first](https://img.shields.io/badge/privacy-local--first-2f6f5e.svg)](#the-promise)

`Video Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](https://raw.githubusercontent.com/warith-harchaoui/video-helper/main/assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

Video Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats.

## The Promise

**Local-first by design.** video-helper runs entirely on your machine. Everything is processed locally with open-source tooling (ffmpeg) — your data is never uploaded to a third-party service, no telemetry, no account, no cloud lock-in. You own the whole pipeline. Part of the [AI Helpers](https://github.com/warith-harchaoui/ai-helpers) suite: sovereignty over your data through local-first Open Source.

## Documentation

[💻 Documentation](https://harchaoui.org/warith/ai-helpers/docs/video-helper-doc/)

[📋 Examples](https://github.com/warith-harchaoui/video-helper/blob/main/EXAMPLES.md)

## Installation

**Prerequisites** — **Python 3.10–3.13** and **git**, **ffmpeg**, cross-platform:

- 🍎 **macOS** ([Homebrew](https://brew.sh)): `brew install python git ffmpeg`
- 🐧 **Ubuntu/Debian**: `sudo apt update && sudo apt install -y python3 python3-pip git ffmpeg`
- 🪟 **Windows** (PowerShell): `winget install Python.Python.3.12 Git.Git Gyan.FFmpeg`

We recommend using Python environments. Check this link if you're unfamiliar with setting one up: [🥸 Tech tips](https://harchaoui.org/warith/4ml/#install).

### From PyPI (recommended)

```bash
# Core video utilities (library + argparse CLI)
pip install video-helper

# Optional surfaces and backends
pip install "video-helper[pyav]"      # PyAV frame backend
pip install "video-helper[cli]"       # click-based CLI twin
pip install "video-helper[api]"       # FastAPI HTTP surface
pip install "video-helper[api,mcp]"   # MCP tools over FastAPI
```

### From source (no PyPI)

```bash
# Core video utilities (library + argparse CLI)
pip install "git+https://github.com/warith-harchaoui/video-helper.git@v1.6.5"

# Optional surfaces and backends
pip install "video-helper[pyav] @ git+https://github.com/warith-harchaoui/video-helper.git@v1.6.5"
pip install "video-helper[cli] @ git+https://github.com/warith-harchaoui/video-helper.git@v1.6.5"
pip install "video-helper[api] @ git+https://github.com/warith-harchaoui/video-helper.git@v1.6.5"
pip install "video-helper[api,mcp] @ git+https://github.com/warith-harchaoui/video-helper.git@v1.6.5"
```

## Usage

For the full catalog of recipes, see [📋 EXAMPLES.md](https://github.com/warith-harchaoui/video-helper/blob/main/EXAMPLES.md).

Here’s an example of how to use Video Helper to load, convert, and extract frames from a video file:

```python
import video_helper as vh

# Check if the video file is valid
video_file = "example.mp4"
valid = vh.is_valid_video_file(video_file) # True or False

# Get video dimensions and details
details = vh.video_dimensions(video_file)
print(details)
# {'width': 1920, 'height': 1080, 'duration': 10.0, 'frame_rate': 30.0, 'has_sound': True}

# Convert the video file to a different format
output_video = "video_tests/example_converted.mp4"
vh.video_converter(video_file, output_video,
                   frame_rate=30, width=640, without_sound = True)

# The images will never be distorted:
# aspect ratios are kept even for arbitrary width and height thanks to black padding if necessary

# Extract frames from the video

start_instant=5 # seconds
# it corresponds to start_index = start_instant * frame_rate = 5 * 30 = 150th frame

end_instant=10 # seconds
# it corresponds to end_index = end_instant * frame_rate = 10 * 30 = 300th frame

frame_step=5 # take one frame every 5
# which corresponds to 1 frame every 5 / frame_rate = 5 / 30 = 0.17 second

# This means that in the video we take 1 frame every 5 from the 150th to the 300th

# List example
frames = list(
    vh.extract_frames(video_file, start_instant=start_instant, end_instant=end_instant, frame_step=frame_step)
)

# For loop example
for frame in vh.extract_frames(
    video_file,
    start_instant=start_instant,
    end_instant=end_instant,
    frame_step=frame_step):
    pass # Replace with your frame processing logic

# Each frame is a numpy array with shape (height, width, channels)
# with pixel values between 0 and 255.

```

Another example is about subtitles

Convert SRT subtitles to WebVTT with color preservation:

```python
import video_helper as vh

srt_file = "subtitles.srt"
vtt_file = "subtitles.vtt"
css_file = "subtitles.css"

vh.srt2vtt(srt_file, vtt_file, css_file)
```

## Multi-surface exposure

Every public function is reachable from five surfaces, all
systematically wired (nothing is CLI-only or library-only):

| Surface | Install | Entry point |
| --- | --- | --- |
| Python library | `pip install video-helper` | `import video_helper as vh` |
| Argparse CLI (stdlib) | `pip install video-helper` | `video-helper --help` |
| Click CLI | `pip install 'video-helper[cli]'` | `video-helper-click --help` |
| FastAPI HTTP + GUI | `pip install 'video-helper[api]'` | `uvicorn video_helper.api:app` |
| MCP server | `pip install 'video-helper[api,mcp]'` | `video-helper-mcp` |

The FastAPI app also serves a **minimal browser GUI** ("video bench") at
`GET /gui` (and `GET /` redirects there): drop a clip, pick one operation,
run it against the same HTTP endpoints, preview input vs output in an
in-browser `<video>` / `<img>` player, and download the result. It is a
single self-contained page (Tailwind via CDN + vanilla JS, no build step)
defined in `video_helper/gui.py`.

```bash
pip install 'video-helper[api]'
uvicorn video_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)
```

The `Dockerfile` at the repo root ships `.[api,mcp,pyav]` by default on
`python:3.11-slim` with `ffmpeg` and `libass` — one `docker build && docker run -p 8000:8000` gives you the HTTP + MCP + GUI surfaces immediately.

For the exhaustive catalogue of what triggers each operation (natural-language
phrasings, commands, functions, file types), see
[TRIGGERS.md](https://github.com/warith-harchaoui/video-helper/blob/main/TRIGGERS.md).
`video-helper` also ships as a Claude / OpenCode **agent skill** — see
[skills/README.md](https://github.com/warith-harchaoui/video-helper/blob/main/skills/README.md).

See [GUI.md](https://github.com/warith-harchaoui/video-helper/blob/main/GUI.md) for the roadmap toward a richer GUI (Recipe
Canvas + frame-first comparator + batch drop zone — the minimal `/gui` bench
above is the first step) and [LANDSCAPE.md](https://github.com/warith-harchaoui/video-helper/blob/main/LANDSCAPE.md) for how `video-helper` compares with
moviepy, PyAV, decord, torchvision.io, VidGear, OpenCV, and friends.

## Features
- **Video validation**: `is_valid_video_file` — extension + `ffmpeg.probe` round-trip.
- **Conversion**: `video_converter` — re-encode, resample fps, resize (aspect-preserving), strip audio.
- **Frame access**: `extract_frames` (generator with time/index range, stabilization, sampling) and `dump_frames` (list → video).
- **Temporal crop**: `extract_video_chunk`, `video_duration`.
- **Pipeline primitives**: `black_video`, `image_loop_to_video`, `concat_videos`, `overlay_image`, `extract_audio_track`, `mux_audio_video`, `burn_subtitles`.
- **Subtitles**: `srt2vtt` (with companion CSS), `extract_unique_colors`.

## API Reference

| Function | Signature | Description |
| --- | --- | --- |
| `is_valid_video_file` | `(video_file: str) -> bool` | True iff the file exists, has a known video extension, and `ffmpeg.probe` finds a video stream. |
| `video_dimensions` | `(video_file: str) -> dict` | Returns `{width, height, duration, frame_rate, has_sound}` via `ffmpeg.probe`. |
| `video_duration` | `(input_video: str) -> float` | Duration in seconds (thin wrapper over `video_dimensions`). |
| `video_converter` | `(input_video, output_video=None, frame_rate=None, width=None, height=None, without_sound=False)` | Re-encode with optional fps, resize (aspect-preserving black padding when both width and height are given), and audio stripping. |
| `extract_frames` | `(video_path, start_index=None, end_index=None, start_instant=None, end_instant=None, stabilize=False, frame_step=1, frame_interval=None, frame_indices=None, frame_times=None, backend="auto", hwaccel=None, http_headers=None, output_width=None, output_height=None, pad_color="black", destination="numpy", device="cpu", batch_size=None, layout="image") -> Iterator` | Multi-backend dispatcher (VidGear / PyAV / ffmpeg-pipe). `destination`: `"numpy"` (HWC BGR), `"torch"` (CHW RGB), or `"pil"` (PIL.Image RGB, `size=(W, H)`). `batch_size`+`layout` yields NHWC/NCHW or THWC/CTHW. `frame_indices`/`frame_times` = sparse access via PyAV keyframe-seek. `http_headers` forwards User-Agent/Referer/Cookie to PyAV / ffmpeg-pipe (needed for yt-dlp-resolved YouTube live, members-only, age-gated). `output_width`+`output_height` → exact size with `pad_color`-padded letterbox/pillarbox; one of them alone → aspect-preserving scale. `pad_color="transparent"` → v1.6.0. See [SPEED_ANALYSIS.md](https://github.com/warith-harchaoui/video-helper/blob/main/SPEED_ANALYSIS.md) and [EXAMPLES.md](https://github.com/warith-harchaoui/video-helper/blob/main/EXAMPLES.md#frame-access). |
| `dump_frames` | `(frames_list, output_movie, fps=30)` | Write a list of BGR frames (OpenCV convention, same as `extract_frames` yields) to a video file. |
| `extract_video_chunk` | `(input_video, sample_start, sample_end, output_video)` | Temporal crop from `sample_start` to `sample_end` (seconds). |
| `black_video` | `(duration, width, height, output_video, frame_rate=30)` | Generate a silent solid-black video. Odd dimensions are rounded down. |
| `image_loop_to_video` | `(image, duration, output_video, frame_rate=30, width=None, height=None)` | Loop a still image into a silent video; optional letterboxing. |
| `concat_videos` | `(input_videos, output_video, reencode=True, frame_rate=None)` | Concatenate clips end-to-end via the ffmpeg concat demuxer. |
| `overlay_image` | `(input_video, image, output_video, x="0", y="0", scale_width=None)` | Overlay a PNG/JPG (alpha supported); `x` / `y` accept ffmpeg expressions for time-varying motion. |
| `extract_audio_track` | `(input_video, output_audio, sample_rate=44100, channels=2, encoding="pcm_s16le")` | Pull the audio stream out of a video file. |
| `mux_audio_video` | `(input_video, input_audio, output_video, audio_codec="aac", audio_bitrate="192k", shortest=False)` | Replace the audio track of a (typically silent) video. |
| `burn_subtitles` | `(input_video, subtitles_file, output_video, force_style=None)` | Burn `.srt` / `.vtt` / `.ass` / `.ssa` into the video frames (requires ffmpeg built with libass). |
| `srt2vtt` | `(srt_file_path, vtt_file_path=None, css_file_path=None)` | Convert SRT → WebVTT, lifting `<font color>` tags into a sidecar CSS file. |
| `extract_unique_colors` | `(srt_file_path: str) -> Set[str]` | Set of unique hex colors found in `<font color>` tags of an SRT. |

By default frames are BGR `numpy.ndarray` of shape `(H, W, 3)` with pixel values in `[0, 255]`. See [EXAMPLES.md → Destination](https://github.com/warith-harchaoui/video-helper/blob/main/EXAMPLES.md#destination-numpy-torch-or-pil) for the full shape × colorspace table including torch (CHW/NCHW/CTHW RGB) and PIL (RGB, `size=(W, H)`).

## Author
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

## Acknowledgements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.

## License

This project is licensed under the BSD-3-Clause License — see the [LICENSE](LICENSE) file for details.
