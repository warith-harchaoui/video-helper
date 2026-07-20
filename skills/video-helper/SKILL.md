---
name: video-helper
description: >-
  Process video files with the `video-helper` toolkit — validate a clip, probe
  its dimensions / duration / fps, re-encode / resize / drop-audio (convert),
  cut a [start, end] slice (chunk), synthesize a solid-black clip, loop a still
  image into a clip, concatenate clips head-to-tail, overlay a watermark image,
  extract the audio track, mux a new audio track on, burn subtitles into the
  frames, convert SRT to WebVTT (+ CSS), and extract frames as images (multi-
  backend dispatcher: VidGear / PyAV / ffmpeg-pipe). Exposed as a Python library
  (`import video_helper as vh`), two CLIs (`video-helper` argparse and
  `video-helper-click`), a FastAPI HTTP surface, an MCP tool set, and a minimal
  browser GUI at `/gui`. Local-first, ffmpeg-backed, no SaaS.

  TRIGGER — any of: the user names a video operation on a file ("convert this mov
  to mp4 / resize to 720p / strip the audio", "re-encode / transcode this video",
  "cut / trim / extract seconds A to B from this clip", "concatenate / join /
  stitch these clips", "make a black / blank video", "turn this image into a
  video / loop this still", "overlay / watermark a logo on this video", "extract
  / rip the audio from this video", "mux / attach / replace the audio track",
  "burn / hardcode subtitles into the video", "convert this SRT to VTT / WebVTT",
  "extract / dump / sample frames from this video", "how long is this video / what
  are its dimensions / is this a valid video"); the user types or references a
  command (`video-helper`, `video-helper-click`, `video-helper-mcp`, subcommands
  `validate|dimensions|duration|convert|chunk|black|image-loop|concat|overlay|
  extract-audio|mux-audio|burn-subs|srt2vtt|extract-frames`) or a library
  function (`extract_frames`, `dump_frames`, `video_converter`, `video_dimensions`,
  `video_duration`, `is_valid_video_file`, `extract_video_chunk`, `black_video`,
  `image_loop_to_video`, `concat_videos`, `overlay_image`, `extract_audio_track`,
  `mux_audio_video`, `burn_subtitles`, `srt2vtt`, `extract_unique_colors`); the
  user points at a video file (`.mp4 .mkv .mov .webm .avi .m4v .mpeg .mpg .ts .3gp`)
  or a subtitle file (`.srt .vtt .ass`) and wants it transformed; the user wants
  the video API/MCP server run, or the drag-and-drop GUI; the user asks to
  install/run video-helper.

  SKIP when: the task is speech-to-text / transcription / caption GENERATION from
  audio (use vocal-helper / a whisper skill — video-helper burns and converts
  subtitle FILES, it does not create them); downloading a video from YouTube or a
  URL (use youtube-helper); DAW / NLE-style non-linear timeline editing, color
  grading, keyframed effects, or motion graphics; deep-learning inference on
  frames (video-helper extracts frames, it does not classify / detect / track);
  audio-only editing with no video in play (use audio-helper). video-helper
  transforms video *files*; it does not transcribe, download, grade, or infer.
---

# video-helper — video file operations toolkit

`video-helper` is a small, local-first Python toolkit for preparing video for
AI and media pipelines. Everything is ffmpeg-backed and file-oriented: you give
it paths, it writes paths (frame extraction yields arrays). The same operations
are reachable five ways (library, two CLIs, HTTP API, MCP, GUI) so an agent can
pick whichever fits.

## Before anything: verify it is installed

```bash
video-helper --version            # argparse CLI (always installed with the pkg)
python -c "import video_helper"   # library import check
```

If missing, install it (ffmpeg is a hard system dependency):

```bash
pip install video-helper                 # core (validate/convert/chunk/frames/…)
pip install 'video-helper[pyav]'         # + PyAV frame backend (best sparse access)
pip install 'video-helper[cli]'          # + click CLI twin
pip install 'video-helper[api,mcp]'      # + FastAPI HTTP surface + MCP tools + GUI
pip install 'video-helper[torch]'        # + destination="torch" frames
pip install 'video-helper[pil]'          # + destination="pil" frames
```

ffmpeg must be on PATH (libass build needed for `burn-subs`):
- macOS 🍎 : `brew install ffmpeg` (install `brew` via [brew.sh](https://brew.sh/))
- Ubuntu 🐧 : `sudo apt install ffmpeg`
- Windows 🪟 : `winget install Gyan.FFmpeg`

## The fourteen operations

Same names across the library, both CLIs, the API, and the MCP tools:

| Operation | CLI | Library function |
|-----------|-----|------------------|
| Validate a video (ffprobe + ext) | `video-helper validate` | `is_valid_video_file` |
| Probe width/height/duration/fps | `video-helper dimensions` | `video_dimensions` |
| Duration in seconds | `video-helper duration` | `video_duration` |
| Re-encode / resize / drop-audio | `video-helper convert` | `video_converter` |
| Extract `[start, end]` slice | `video-helper chunk` | `extract_video_chunk` |
| Synthesize a solid-black clip | `video-helper black` | `black_video` |
| Loop a still image into a clip | `video-helper image-loop` | `image_loop_to_video` |
| Concatenate clips head-to-tail | `video-helper concat` | `concat_videos` |
| Overlay a still image (watermark) | `video-helper overlay` | `overlay_image` |
| Rip the audio track out | `video-helper extract-audio` | `extract_audio_track` |
| Mux a new audio track on | `video-helper mux-audio` | `mux_audio_video` |
| Burn subtitles into frames | `video-helper burn-subs` | `burn_subtitles` |
| SRT → WebVTT (+ CSS) | `video-helper srt2vtt` | `srt2vtt` |
| Extract frames (VidGear/PyAV/ffmpeg) | `video-helper extract-frames` | `extract_frames` |

Quick examples:

```bash
video-helper convert       --input in.mov --output out.mp4 --width 1280 --height 720
video-helper chunk         --input in.mp4 --start 10 --end 20 --output cut.mp4
video-helper concat        --inputs a.mp4 b.mp4 c.mp4 --output final.mp4
video-helper overlay       --input clip.mp4 --image logo.png --output wm.mp4 --x 10 --y 10
video-helper extract-audio --input clip.mp4 --output audio.wav
video-helper burn-subs     --input clip.mp4 --subs subs.srt --output captioned.mp4
video-helper srt2vtt       --input subs.srt
video-helper extract-frames --input clip.mp4 --output-dir frames/ --frame-step 5
```

```python
import video_helper as vh
info = vh.video_dimensions("in.mp4")     # {'width', 'height', 'duration', 'frame_rate', 'has_sound'}
vh.video_converter("in.mov", "out.mp4", width=1280, height=720, without_sound=True)
for frame in vh.extract_frames("in.mp4", frame_step=5):  # BGR HWC uint8 numpy by default
    ...
```

For the full flag matrix and every option, read `references/cli-reference.md`.
For the API / MCP / GUI surfaces (endpoints, ports, the `/gui` bench), read
`references/surfaces.md`. For the exhaustive, auditable trigger list, read
`references/triggers.md`.

## Rules of thumb

- **Pick the operation from the intent, not the file type.** "make it 720p /
  strip audio" → `convert`; "just seconds 10–20" → `chunk`; "stitch these" →
  `concat`; "watermark it" → `overlay`; "hardcode the subtitles" → `burn-subs`;
  "give me frames as images" → `extract-frames`.
- **`extract_frames` yields arrays, not files.** By default BGR `numpy` HWC
  uint8 (OpenCV convention). `destination="torch"` → CHW RGB (needs `[torch]`);
  `destination="pil"` → `PIL.Image` (needs `[pil]`). The API `/extract-frames`
  route zips PNGs for you.
- **Frame backend is auto-selected.** The dispatcher picks VidGear / PyAV /
  ffmpeg-pipe from the access pattern (see `SPEED_ANALYSIS.md`). Install
  `[pyav]` for the best sparse / windowed-sequential path.
- **URLs are valid inputs.** `is_valid_video_file` short-circuits `http(s)://`
  to True; `video_dimensions` / `extract_frames` accept `http_headers=` to pass
  User-Agent / Referer / Cookie for yt-dlp-resolved streams (feed from
  youtube-helper).
- **`burn-subs` needs ffmpeg built with libass.** Without it the burn fails
  with a clear ffmpeg error.
- **After running, report the output path(s)** the tool printed, and hand them
  back — do not re-run unless something failed.
- **Local only.** No network except when the input is itself a URL; never sends
  video to a SaaS.
