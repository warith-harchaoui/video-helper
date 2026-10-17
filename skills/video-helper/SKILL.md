---
name: video-helper
description: >-
  Transform video files locally with ffmpeg and OpenCV. Validate, probe
  dimensions / fps / duration, re-encode and resize, cut a [start, end] slice,
  two-pass compress to a target file size, synthesize a black clip, loop a
  still image into a clip, concatenate, overlay a watermark, rip or mux an
  audio track, burn subtitles, convert SRT to WebVTT, extract frames as arrays
  or images, and compute optical flow. Use when the user says "convert this mov
  to mp4", "resize to 720p", "trim from 10s to 20s", "get it under 100 MB",
  "shrink this video", "merge these clips", "watermark a logo", "rip the
  audio", "replace the audio track", "burn in subtitles", "srt to vtt", "give
  me the frames", "how long / how big is this video", "optical flow", or names
  `video-helper`, `video-helper-click`, `video-helper-mcp`, `import
  video_helper as vh`. Do NOT use to transcribe speech (vocal-helper),
  download video (youtube-helper), capture a camera (capture-helper), or
  colour-grade.
license: BSD-3-Clause
metadata:
  author: Warith Harchaoui
  package: video-helper
  suite: ai-helpers
  homepage: https://deraison.ai/ai-helpers
---

# video-helper — local ffmpeg video transforms

`video-helper` transforms video **files** and reads or burns subtitle files.
It is local-first and ffmpeg-backed: nothing is uploaded, there is no
telemetry, no account. It does **not** transcribe, download, or colour-grade.
The same operations are reachable five ways (library, two CLIs, HTTP API, MCP,
browser GUI).

## Before anything: verify it is installed

```bash
video-helper --help               # argparse CLI (ships with the package)
python -c "import video_helper"   # library import check
ffmpeg -version                   # hard system dependency
```

Install:

```bash
pip install video-helper                 # core: every ffmpeg operation
pip install 'video-helper[pyav]'         # + the fastest frame-extraction backend
pip install 'video-helper[torch]'        # + extract_frames(destination="torch")
pip install 'video-helper[pil]'          # + extract_frames(destination="pil")
pip install 'video-helper[faces]'        # + face identity + active-speaker detection
pip install 'video-helper[flow]'         # + RAFT optical flow and wavelet resizing
pip install 'video-helper[cli,api,mcp]'  # + click CLI, FastAPI, MCP tools
pip install 'video-helper[all]'          # everything
```

ffmpeg must be on PATH — macOS 🍎 `brew install ffmpeg`, Ubuntu 🐧 `sudo apt
install ffmpeg`, Windows 🪟 `winget install Gyan.FFmpeg`.

## The operations

| Intent | CLI | Library |
|---|---|---|
| Is this a real video | `video-helper validate` | `is_valid_video_file` |
| Dimensions / fps | `video-helper dimensions` | `video_dimensions` |
| Duration in seconds | `video-helper duration` | `video_duration` |
| Re-encode / resize / drop audio | `video-helper convert` | `video_converter` |
| Cut a `[start, end]` slice | `video-helper chunk` | `extract_video_chunk` |
| Compress to a target size | `video-helper compress` | `compress_video` |
| Solid-black filler clip | `video-helper black` | `black_video` |
| Still image → clip | `video-helper image-loop` | `image_loop_to_video` |
| Concatenate clips | `video-helper concat` | `concat_videos` |
| Watermark / badge | `video-helper overlay` | `overlay_image` |
| Rip the audio track | `video-helper extract-audio` | `extract_audio_track` |
| Attach / replace audio | `video-helper mux-audio` | `mux_audio_video` |
| Burn subtitles into frames | `video-helper burn-subs` | `burn_subtitles` |
| SRT → WebVTT (+ CSS) | `video-helper srt2vtt` | `srt2vtt` |
| Frames as arrays or images | `video-helper extract-frames` | `extract_frames`, `dump_frames` |
| Optical flow | `video-helper extract-flow` | `extract_optical_flow` |

Quick examples:

```bash
video-helper convert clip.mov clip.mp4 --height 720
video-helper chunk talk.mp4 cut.mp4 --start 10 --end 20
video-helper compress big.mp4 small.mp4 --target-size-mb 100
video-helper extract-audio talk.mp4 talk.wav
video-helper burn-subs talk.mp4 subbed.mp4 --subtitles talk.srt
```

```python
import video_helper as vh

w, h, fps = vh.video_dimensions("clip.mp4")
for frame in vh.extract_frames("clip.mp4", fps=1):  # BGR uint8 arrays
    ...
```

`vh` is the suite's canonical alias. `extract_frames` is a generator — it
streams, so a long film does not land in RAM; `dump_frames` writes them to
disk instead.

For the full flag matrix and the frame-extraction backends, read
`references/cli-reference.md`. For the HTTP API, MCP tools, the GUI and the
optional face / active-speaker stack, read `references/surfaces.md`. For the
exhaustive trigger list, read `references/triggers.md`.

## Rules of thumb

- **Probe before you transform.** `validate` then `dimensions` costs an
  ffprobe call and prevents a wasted re-encode on a truncated file.
- **`compress` is two-pass and size-targeted.** Ask for a file size
  (`--target-size-mb`), not a bitrate — that is the question users actually
  have ("get it under 100 MB for email").
- **Extracting the audio track is video-helper's job; transforming the result
  is audio-helper's.** Chain them rather than reaching for raw ffmpeg.
- **Frames come out BGR uint8** by default, matching OpenCV and
  capture-helper's `iter_camera_frames`, so code written against one runs
  against the other. `destination="torch"` / `"pil"` need their extras.
- **Subtitles: burn only when they must be pixels.** `srt2vtt` keeps them as a
  selectable track, which is better for the web; `burn-subs` is for platforms
  that strip tracks.
- **Hardware encoders are opt-in via `hw_vcodec`** — the default path is
  deterministic software encoding, which is what reproducible output needs.
- **After running, report the output path plus the new size or duration** —
  do not re-run to confirm.
