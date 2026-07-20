# TRIGGERS — video-helper

This is the user-facing, exhaustive catalogue of what `video-helper` can do and
the natural-language phrasings, commands, functions, and file types that should
invoke it — whether you call it yourself or drive it as a Claude / OpenCode
**skill** (see [`skills/video-helper/SKILL.md`](skills/video-helper/SKILL.md)
and its [`references/triggers.md`](skills/video-helper/references/triggers.md)).

`video-helper` transforms video **files** (and reads/burns subtitle files). It
is local-first and ffmpeg-backed. It does **not** transcribe, download, colour-
grade, or run models on frames.

## The fourteen operations → how to invoke

| Intent | CLI | Library | API / MCP |
|--------|-----|---------|-----------|
| Validate a video (ext + ffprobe) | `video-helper validate` | `is_valid_video_file` | `POST /validate` |
| Probe dimensions / duration / fps | `video-helper dimensions` | `video_dimensions` | `POST /dimensions` |
| Duration in seconds | `video-helper duration` | `video_duration` | `POST /duration` |
| Re-encode / resize / drop audio | `video-helper convert` | `video_converter` | `POST /convert` |
| Extract a `[start, end]` slice | `video-helper chunk` | `extract_video_chunk` | `POST /chunk` |
| Synthesize a solid-black clip | `video-helper black` | `black_video` | `POST /black` |
| Loop a still image into a clip | `video-helper image-loop` | `image_loop_to_video` | `POST /image-loop` |
| Concatenate clips head-to-tail | `video-helper concat` | `concat_videos` | `POST /concat` |
| Overlay a still image (watermark) | `video-helper overlay` | `overlay_image` | `POST /overlay` |
| Rip the audio track | `video-helper extract-audio` | `extract_audio_track` | `POST /extract-audio` |
| Mux a new audio track on | `video-helper mux-audio` | `mux_audio_video` | `POST /mux-audio` |
| Burn subtitles into frames | `video-helper burn-subs` | `burn_subtitles` | `POST /burn-subs` |
| SRT → WebVTT (+ CSS) | `video-helper srt2vtt` | `srt2vtt` | `POST /srt2vtt` |
| Extract frames as images | `video-helper extract-frames` | `extract_frames` | `POST /extract-frames` |

Every operation is also reachable through the click CLI (`video-helper-click …`,
same flags) and the browser GUI at `GET /gui`.

## Natural-language phrasings that should fire

- **Convert**: "convert this mov to mp4", "resize to 720p", "strip the audio",
  "re-encode / transcode", "change the frame rate".
- **Chunk**: "cut from 10s to 20s", "keep the first minute", "trim / crop".
- **Black**: "make a black / blank clip", "generate a filler / spacer video".
- **Image-loop**: "turn this image into a video", "loop this still", "title card".
- **Concat**: "merge / join / stitch these clips", "combine into one".
- **Overlay**: "watermark a logo", "add a badge in the corner".
- **Extract-audio / mux-audio**: "rip the audio", "attach / replace the audio track".
- **Burn-subs / srt2vtt**: "hardcode the subtitles", "SRT to WebVTT".
- **Extract-frames**: "sample frames as images", "one frame every N", "keyframes".
- **Probe**: "how long is this", "what resolution / fps", "is this a valid video".
- **Surfaces**: "run the video API / MCP server", "open the video GUI", "install
  video-helper".

## File types it accepts

- **Video**: `.mp4 .mkv .mov .webm .avi .m4v .mpeg .mpg .ts .3gp .ogv .flv …`
  (and `http(s)://` URLs for `validate` / `dimensions` / `extract-frames`).
- **Subtitles**: `.srt .vtt .ass .ssa` (for `burn-subs` / `srt2vtt`).
- **Stills**: `.png .jpg .jpeg .webp` (for `image-loop` / `overlay`).

## When NOT to use video-helper (SKIP)

- Transcription / caption generation from audio / speech-to-text → use
  `vocal-helper` / a whisper skill (video-helper burns/converts subtitle FILES).
- Downloading a video from YouTube or a URL → use `youtube-helper`.
- NLE / DAW timeline editing, colour grading, keyframed effects, motion graphics.
- Deep-learning inference on frames (classify / detect / track) — video-helper
  extracts frames, it does not run models on them.
- Audio-only editing with no video in play → use `audio-helper`.

## See also

- [`README.md`](README.md) — features, install, quick start.
- [`EXAMPLES.md`](EXAMPLES.md) — runnable recipes.
- [`GUI.md`](GUI.md) — the shipped minimal `/gui` bench + the roadmap for a
  richer Recipe-Canvas product.
- [`LANDSCAPE.md`](LANDSCAPE.md) — how video-helper compares with moviepy, PyAV,
  torchvision.io, VidGear, OpenCV, and friends.
- [`skills/README.md`](skills/README.md) — installing this as an agent skill.
