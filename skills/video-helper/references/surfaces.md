# video-helper non-CLI surfaces

`video-helper` exposes the same fourteen operations through five surfaces. The
Python library and argparse CLI are always available; the others live behind
optional extras.

## 1. Python library (default)

```python
import video_helper as vh

vh.is_valid_video_file(path)                     # -> bool (http(s):// short-circuits True)
vh.video_dimensions(path, http_headers=None)     # -> {width, height, duration, frame_rate, has_sound}
vh.video_duration(path)                          # -> float seconds
vh.video_converter(inp, out=None, frame_rate=None, width=None, height=None, without_sound=False)
vh.extract_video_chunk(inp, sample_start, sample_end, output_video)
vh.black_video(duration, width, height, output_video, frame_rate=30)
vh.image_loop_to_video(image, duration, output_video, frame_rate=30, width=None, height=None)
vh.concat_videos([a, b, c], output_video, reencode=True, frame_rate=None)
vh.overlay_image(inp, image, output_video, x="0", y="0", scale_width=None)
vh.extract_audio_track(inp, output_audio, sample_rate=44100, channels=2, encoding="pcm_s16le")
vh.mux_audio_video(inp, input_audio, output_video, audio_codec="aac", audio_bitrate="192k", shortest=False)
vh.burn_subtitles(inp, subtitles_file, output_video, force_style=None)
vh.srt2vtt(srt_path, vtt_path=None, css_path=None)
vh.extract_unique_colors(srt_path)               # -> set[str]
for frame in vh.extract_frames(path, frame_step=1, backend="auto", ...):  # BGR HWC uint8 by default
    ...
vh.dump_frames(frames_list, output_movie, fps=30)
```

The public API is fixed via `video_helper.__all__`; sibling repos (youtube-helper)
depend on these names — treat them as stable.

## 2. CLI — argparse (default) and click

- **argparse** `video-helper <sub> …` — ships with the base package, zero extra
  deps. Primary surface. See `cli-reference.md`.
- **click** `video-helper-click <sub> …` — install `video-helper[cli]`. Same
  subcommands and flag names; nicer `--help`, shell completion.

## 3. HTTP API — FastAPI (`video-helper[api]`)

```bash
pip install 'video-helper[api]'
uvicorn video_helper.api:app --host 0.0.0.0 --port 8000
# OpenAPI docs: http://localhost:8000/docs
```

Endpoints (multipart `file` upload unless noted):
- `GET  /health` — liveness probe → `{"status":"ok"}`.
- `GET  /` — redirects to `/gui`.
- `GET  /gui` — the single-page GUI (see below).
- `POST /validate` — → JSON `{"valid": …}`.
- `POST /dimensions` — → JSON `{width, height, duration, frame_rate, has_sound}`.
- `POST /duration` — → JSON `{"duration_seconds": …}`.
- `POST /convert` — fields `output_format frame_rate width height without_sound` → file.
- `POST /chunk` — fields `start end output_format` → file.
- `POST /black` — fields `duration width height frame_rate output_format` (no upload) → file.
- `POST /image-loop` — `image` upload + `duration frame_rate width height output_format` → file.
- `POST /concat` — repeated `files` (≥2) + `reencode frame_rate output_format` → file.
- `POST /overlay` — `file` + `image` uploads + `x y scale_width output_format` → file.
- `POST /extract-audio` — fields `output_format sample_rate channels encoding` → file.
- `POST /mux-audio` — `file` + `audio` uploads + `audio_codec audio_bitrate shortest output_format` → file.
- `POST /burn-subs` — `file` + `subs` uploads + `force_style output_format` → file.
- `POST /srt2vtt` — `file` (.srt) upload → **zip** of `.vtt` + `.css`.
- `POST /extract-frames` — `file` + `frame_step frame_interval start end backend` → **zip** of PNGs.

Uploads stream to a temp file; temp dirs are cleaned via `BackgroundTasks`. The
FastAPI `version` field is read from installed package metadata, so it always
matches `pyproject.toml`.

## 4. MCP server — FastAPI-MCP (`video-helper[api,mcp]`)

```bash
pip install 'video-helper[api,mcp]'
video-helper-mcp                 # serves FastAPI + MCP on :8000
# or: python -m video_helper.mcp
```

Wraps the exact FastAPI app with `fastapi_mcp` — the same endpoints become MCP
tools (`convert`, `chunk`, `concat`, `burn-subs`, `extract-frames`, …) for any
MCP-aware host. Host via `VIDEO_HELPER_HOST` / `VIDEO_HELPER_PORT` env vars.

## 5. GUI — minimal video bench (`GET /gui`)

Served by the FastAPI app; no build step, no framework — a single self-contained
HTML page (Tailwind via CDN + vanilla ES-module JS) defined in
`video_helper/gui.py`.

Workflow: drop/pick a video → choose an operation → fill only the fields (and
any extra file inputs — a second clip for `concat`, an image for `overlay`, an
audio track for `mux-audio`, a subtitle file for `burn-subs`) that operation
needs → **Run** (POSTs to the same `/convert`, `/chunk`, … routes) → preview
**input vs output** (a `<video>` player for clips, an `<img>` for stills, an
`<audio>` player for `extract-audio`, a JSON dump for the read-only probes) and
download the result (a single file, or a `.zip` for `extract-frames` / `srt2vtt`).

```bash
uvicorn video_helper.api:app --port 8000
# open http://localhost:8000/gui  (or just http://localhost:8000/)
```

This page mirrors the AI Helpers suite's canonical minimal-GUI template (see
audio-helper's audition bench): same plumbing — drop zone, op→fields sync,
fetch → player/zip/JSON rendering — adapted to the video verbs. `GUI.md` at the
repo root sketches the more ambitious Recipe-Canvas product this minimal bench
is a stepping stone toward.
