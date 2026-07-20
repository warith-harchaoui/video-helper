# video-helper skill — exhaustive trigger catalogue

Auditable superset of the `description:` TRIGGER clause in `SKILL.md` (the
description is what a host model sees before loading; this file is the
human-reviewable full list). Keep the two in sync, and mirror the repo-root
`TRIGGERS.md`.

## Fire (positive triggers)

**Validate / probe**
- "is this a valid video / does this file open", "check this clip"
- "how long is this video", "what's the duration", "get the fps / dimensions"
- "does this video have sound", "what resolution is this"

**Convert / resize / re-encode**
- "convert this mov to mp4 / webm / mkv", "re-encode / transcode this video"
- "resize to 720p / 1080p / 640×480", "downscale / make it smaller"
- "change the frame rate to 30 / 24", "strip / remove / drop the audio"

**Chunk / trim**
- "cut from 10s to 20s", "trim / crop the clip", "keep just this segment"
- "extract seconds A to B", "grab the first N seconds"

**Black / blank**
- "make a black / blank video", "generate a solid-black spacer clip"
- "I need a filler / buffer clip of N seconds"

**Image-loop**
- "turn this image into a video", "loop this still for N seconds"
- "make a title card / intro slide from this PNG"

**Concat**
- "join / merge / stitch / concatenate these clips", "combine into one video"
- "put a intro before / an outro after this clip"

**Overlay**
- "overlay / watermark a logo on this video", "add a watermark / cursor / badge"
- "put this PNG in the corner", "burn an image onto the frames"

**Extract-audio / mux-audio**
- "extract / rip / pull the audio out of this video", "get the soundtrack"
- "attach / add / replace the audio track", "mux this narration onto the video"
- "swap the audio", "put this music under the video"

**Burn-subs / srt2vtt**
- "burn / hardcode / bake the subtitles into the video", "open captions"
- "convert this SRT to VTT / WebVTT", "make web-playable subtitles"
- "keep the subtitle colors as CSS"

**Extract-frames**
- "extract / dump / sample frames from this video", "one frame every N / every X seconds"
- "give me the frames as images / PNGs", "screenshots throughout the clip"
- "sample frames to build a dataset", "keyframes / thumbnails from the video"

**Explicit command / function mentions**
- `video-helper`, `video-helper-click`, `video-helper-mcp`
- subcommands `validate dimensions duration convert chunk black image-loop
  concat overlay extract-audio mux-audio burn-subs srt2vtt extract-frames`
- functions `extract_frames dump_frames video_converter video_dimensions
  video_duration is_valid_video_file extract_video_chunk black_video
  image_loop_to_video concat_videos overlay_image extract_audio_track
  mux_audio_video burn_subtitles srt2vtt extract_unique_colors`

**Surfaces**
- "run the video API / video-helper server", "expose these as HTTP / MCP tools"
- "open the video GUI / drag-and-drop bench", "video bench"
- "how do I install / run video-helper"

**File-type cues** (with a transform intent)
- video: `.mp4 .mkv .mov .webm .avi .m4v .mpeg .mpg .ts .3gp .ogv .flv`
- subtitles: `.srt .vtt .ass .ssa`
- stills (for image-loop / overlay): `.png .jpg .jpeg .webp`

## Do NOT fire (SKIP)

- **Transcription / caption GENERATION from audio / speech-to-text** →
  vocal-helper / a whisper skill. video-helper burns and converts subtitle
  *files*; it does not create them from speech.
- **Downloading a video from YouTube / a URL** → youtube-helper.
- **NLE / DAW timeline editing**, color grading, keyframed effects, motion
  graphics, transitions → not this skill (cuts happen via `chunk` + `concat`,
  not on a linear ruler).
- **Deep-learning inference on frames** (classify / detect / track / caption
  the content) → video-helper extracts frames, it does not run models on them.
- **Audio-only editing** with no video in play → audio-helper.

## Enforcement checklist

A trigger is "enforced" when (1) it is represented in `SKILL.md`'s
`description` TRIGGER clause so the host sees it pre-load; (2) the SKIP clause is
present so the skill does not over-fire; (3) this catalogue lists the positive
and negative buckets so a human can audit coverage against the description.
