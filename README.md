# Video Helper

[🇫🇷](LISEZMOI.md) · [🇬🇧](README.md)

[![CI](https://github.com/warith-harchaoui/video-helper/actions/workflows/ci.yml/badge.svg)](https://github.com/warith-harchaoui/video-helper/actions/workflows/ci.yml) [![License: BSD-3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](LICENSE) [![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue.svg)](#)

`Video Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

[🌍 AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](assets/logo.png)](https://harchaoui.org/warith/ai-helpers)

Video Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats.

# Installation

## Install Package

We recommend using Python environments. Check this link if you're unfamiliar with setting one up:

[🥸 Tech tips](https://harchaoui.org/warith/4ml/#install)

## Install `ffmpeg` 
To use Video Helper, you must install `ffmpeg`:

- For macOS 🍎
  
  Get [brew](https://brew.sh)
  ```bash
  brew install ffmpeg
  ```
- For Ubuntu 🐧
  ```bash
  sudo apt install ffmpeg
  ```
- For Windows 🪟
  Go to the [FFmpeg website](https://ffmpeg.org/download.html) and follow the instructions for downloading FFmpeg. You'll need to manually add FFmpeg to your system PATH.
  

finally we still discuss between different python package managers and try to support as much as possible

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/video-helper.git@v1.5.1
```

# Usage

For the full catalog of recipes, see [📋 EXAMPLES.md](EXAMPLES.md).

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

# Features
- **Video validation**: `is_valid_video_file` — extension + `ffmpeg.probe` round-trip.
- **Conversion**: `video_converter` — re-encode, resample fps, resize (aspect-preserving), strip audio.
- **Frame access**: `extract_frames` (generator with time/index range, stabilization, sampling) and `dump_frames` (list → video).
- **Temporal crop**: `extract_video_chunk`, `video_duration`.
- **Pipeline primitives**: `black_video`, `image_loop_to_video`, `concat_videos`, `overlay_image`, `extract_audio_track`, `mux_audio_video`, `burn_subtitles`.
- **Subtitles**: `srt2vtt` (with companion CSS), `extract_unique_colors`.

# API Reference

| Function | Signature | Description |
| --- | --- | --- |
| `is_valid_video_file` | `(video_file: str) -> bool` | True iff the file exists, has a known video extension, and `ffmpeg.probe` finds a video stream. |
| `video_dimensions` | `(video_file: str) -> dict` | Returns `{width, height, duration, frame_rate, has_sound}` via `ffmpeg.probe`. |
| `video_duration` | `(input_video: str) -> float` | Duration in seconds (thin wrapper over `video_dimensions`). |
| `video_converter` | `(input_video, output_video=None, frame_rate=None, width=None, height=None, without_sound=False)` | Re-encode with optional fps, resize (aspect-preserving black padding when both width and height are given), and audio stripping. |
| `extract_frames` | `(video_path, start_index=None, end_index=None, start_instant=None, end_instant=None, stabilize=False, frame_step=1, frame_interval=None, frame_indices=None, frame_times=None, backend="auto", hwaccel=None, http_headers=None, output_width=None, output_height=None, pad_color="black", destination="numpy", device="cpu", batch_size=None, layout="image") -> Iterator` | Multi-backend dispatcher (VidGear / PyAV / ffmpeg-pipe). `destination`: `"numpy"` (HWC BGR), `"torch"` (CHW RGB), or `"pil"` (PIL.Image RGB, `size=(W, H)`). `batch_size`+`layout` yields NHWC/NCHW or THWC/CTHW. `frame_indices`/`frame_times` = sparse access via PyAV keyframe-seek. `http_headers` forwards User-Agent/Referer/Cookie to PyAV / ffmpeg-pipe (needed for yt-dlp-resolved YouTube live, members-only, age-gated). `output_width`+`output_height` → exact size with `pad_color`-padded letterbox/pillarbox; one of them alone → aspect-preserving scale. `pad_color="transparent"` → v1.6.0. See [SPEED_ANALYSIS.md](SPEED_ANALYSIS.md) and [EXAMPLES.md](EXAMPLES.md#frame-access). |
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

By default frames are BGR `numpy.ndarray` of shape `(H, W, 3)` with pixel values in `[0, 255]`. See [EXAMPLES.md → Destination](EXAMPLES.md#destination-numpy-torch-or-pil) for the full shape × colorspace table including torch (CHW/NCHW/CTHW RGB) and PIL (RGB, `size=(W, H)`).

# Author
 - [Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui)

# Acknowledgements
Special thanks to [Mohamed Chelali](https://mchelali.github.io) and [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug) for fruitful discussions.
