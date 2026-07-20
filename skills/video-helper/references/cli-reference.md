# video-helper CLI reference

Full command surface for the `video-helper` skill. The argparse CLI
(`video-helper`) ships with the base package; the click twin
(`video-helper-click`, `[cli]` extra) mirrors the exact same subcommand and
flag names, so anything below works for both by swapping the program name.

## Subcommands

| Subcommand | Purpose | Notable flags |
|------------|---------|---------------|
| `validate` | Probe a video file / URL for validity (boolean) | `--input` |
| `dimensions` | Dump width/height/duration/frame_rate/has_sound (JSON) | `--input --header` |
| `duration` | Print duration in seconds | `--input` |
| `convert` | Re-encode / resize / drop audio | `--input --output --frame-rate --width --height --without-sound` |
| `chunk` | Extract a `[start, end]` slice | `--input --start --end --output` |
| `black` | Synthesize a silent solid-black clip | `--duration --width --height --output --frame-rate` |
| `image-loop` | Loop a still image into a silent clip | `--image --duration --output --frame-rate --width --height` |
| `concat` | Concatenate clips head-to-tail | `--inputs A B C --output --reencode/--no-reencode --frame-rate` |
| `overlay` | Overlay a still image (watermark / cursor) | `--input --image --output --x --y --scale-width` |
| `extract-audio` | Dump the audio track of a video | `--input --output --sample-rate --channels --encoding` |
| `mux-audio` | Mux a separate audio track onto a video | `--input --audio --output --audio-codec --audio-bitrate --shortest` |
| `burn-subs` | Burn `.srt` / `.vtt` / `.ass` into frames | `--input --subs --output --force-style` |
| `srt2vtt` | SRT → WebVTT with color-preserving CSS | `--input --output --css` |
| `extract-frames` | Stream frames to disk (one PNG per sampled frame) | `--input --output-dir --frame-step --frame-interval --start --end --backend` |

`video-helper --version` and `video-helper <sub> --help` work for every
subcommand. The click twin is `video-helper-click <sub> …` with identical flags
(click uses `--reencode/--no-reencode` and `--without-sound` toggles and
repeated `--inputs`).

## Flag details

### convert
- `--frame-rate` target fps (default: keep source).
- `--width` / `--height` target size in pixels. When **both** are given the
  output is padded (aspect-preserving black letterbox/pillarbox) so frames are
  never distorted; one alone → aspect-preserving scale.
- `--without-sound` drops the audio stream.
- Output container is chosen from the `--output` extension.

### chunk
- `--start` / `--end` in seconds (floats). Temporal crop.

### black
- `--duration` seconds (float, required). `--width` / `--height` required
  (odd dimensions are rounded down). `--frame-rate` default `30`.

### image-loop
- `--image` a still (PNG/JPG/…). `--duration` seconds. `--width` / `--height`
  optional letterbox target. Produces a silent video.

### concat
- `--inputs` takes 2+ paths **in order** (argparse: `--inputs a b c`; click:
  repeat `--inputs a --inputs b`). Order is the concatenation order.
- `--reencode` (default) re-encodes via libx264 for mixed inputs;
  `--no-reencode` stream-copies (inputs must be bit-identical containers).

### overlay
- `--image` overlay still (PNG with alpha typical).
- `--x` / `--y` pixel offset **or** an ffmpeg overlay expression
  (e.g. `main_w-overlay_w-10` for bottom-right), enabling time-varying motion.
- `--scale-width` scale the overlay to this width before compositing.

### extract-audio
- `--output` extension picks the container. `--sample-rate` default `44100`,
  `--channels` default `2`, `--encoding` default `pcm_s16le`.

### mux-audio
- Replaces the video's audio with `--audio`. `--audio-codec` default `aac`,
  `--audio-bitrate` default `192k`. `--shortest` ends output with the shorter
  stream.

### burn-subs
- `--subs` a `.srt` / `.vtt` / `.ass` / `.ssa`. `--force-style` an ASS style
  override string. Requires ffmpeg built with libass.

### srt2vtt
- `--input` an `.srt`. `--output` / `--css` default to siblings of the input.
  Lifts `<font color>` tags into a sidecar CSS file.

### extract-frames
- `--frame-step` take one frame every N (default `1`). `--frame-interval`
  seconds between frames (alternative to `--frame-step`). `--start` / `--end`
  instants in seconds. `--backend` one of `auto vidgear pyav ffmpeg-pipe`
  (default `auto`; the dispatcher picks from the access pattern — see
  `SPEED_ANALYSIS.md`).

## Output contract (for scripting)

- `validate` prints `true` / `false`. `dimensions` prints a JSON object.
  `duration` prints seconds.
- `convert` / `chunk` / `black` / `image-loop` / `concat` / `overlay` /
  `extract-audio` / `mux-audio` / `burn-subs` write to `--output` and print it.
- `srt2vtt` writes the `.vtt` (+ `.css`) siblings.
- `extract-frames` writes one PNG per sampled frame into `--output-dir`.

## Supported inputs

Common video containers (`mp4 mkv mov webm avi m4v mpeg mpg ts 3gp …`), subtitle
files (`srt vtt ass ssa`) for `burn-subs` / `srt2vtt`, and stills (`png jpg …`)
for `image-loop` / `overlay`. `http(s)://` URLs are accepted where noted
(`validate`, `dimensions`, `extract-frames`), with `--header` for authenticated
streams.
