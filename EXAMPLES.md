# Video Helper Examples

Practical recipes for the public surface of `video-helper`. Every
snippet assumes:

```python
import video_helper as vh
import os_helper as osh
```

and that `ffmpeg` is installed and on `PATH`. The `burn_subtitles`
recipe additionally requires ffmpeg to be built with `libass`.

---

## Table of Contents

1. [Setup](#setup)
2. [Probe & Validate](#probe--validate)
3. [Convert & Resize](#convert--resize)
4. [Frame Access](#frame-access)
   - [Iterate Frames](#iterate-frames)
   - [Sparse / Random Access](#sparse--random-access)
   - [Choosing a Backend](#choosing-a-backend)
   - [Hardware Acceleration](#hardware-acceleration)
   - [Destination: numpy or torch tensors](#destination-numpy-or-torch-tensors)
   - [Dump Frames to a Video](#dump-frames-to-a-video)
5. [Temporal Crop](#temporal-crop)
6. [Pipeline Primitives](#pipeline-primitives)
   - [Black Video](#black-video)
   - [Image Loop](#image-loop)
   - [Concatenate](#concatenate)
   - [Overlay Image](#overlay-image)
   - [Extract / Mux Audio](#extract--mux-audio)
   - [Burn Subtitles](#burn-subtitles)
7. [Subtitle Tools](#subtitle-tools)
   - [SRT → VTT + CSS](#srt--vtt--css)
   - [Unique Colors](#unique-colors)

---

## Setup

```bash
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/video-helper.git@v1.4.0
```

Optional faster backends for [`extract_frames`](#frame-access):

```bash
# PyAV — lowest-overhead sequential decode, supports hardware acceleration.
pip install --force-reinstall --no-cache-dir \
  "video-helper[pyav] @ git+https://github.com/warith-harchaoui/video-helper.git@v1.4.0"

# decord — fastest sparse / random-access reads. Not in extras: as of mid-2026
# PyPI wheels don't cover Python 3.13 / Apple Silicon, and upstream
# (https://github.com/dmlc/decord) recommends building from source. Install
# manually after cloning + cmake; the dispatcher falls back to PyAV otherwise.
```

You also need `ffmpeg`. macOS: `brew install ffmpeg`. Linux: `apt install ffmpeg`. Windows: see the [ffmpeg site](https://ffmpeg.org/download.html).

To use [`burn_subtitles`](#burn-subtitles), the ffmpeg build must include
`libass`. Verify with `ffmpeg -filters | grep subtitles` — if missing on
macOS, try `brew uninstall ffmpeg && brew install ffmpeg --HEAD`.

## Probe & Validate

```python
if vh.is_valid_video_file("clip.mp4"):
    info = vh.video_dimensions("clip.mp4")
    print(info)
    # {'width': 1920, 'height': 1080, 'duration': 12.34,
    #  'frame_rate': 30.0, 'has_sound': True}

duration_seconds = vh.video_duration("clip.mp4")
```

`is_valid_video_file` rejects fake `.mp4` files (no video stream) **and**
valid videos with non-video extensions.

## Convert & Resize

`video_converter` re-encodes a video with optional sample-rate, fps,
and dimension changes. Default container behaviour: same-container
inputs are stream-copied; cross-container inputs are transcoded to
H.264 / AAC.

```python
# Strip sound + downscale + halve fps.
vh.video_converter(
    "in.mp4",
    "out.mp4",
    frame_rate=15,
    width=640,
    height=360,
    without_sound=True,
)
```

Pass only `width` or only `height` to preserve the aspect ratio.

## Frame Access

### Iterate Frames

`extract_frames` is a generator. Pick the range by index OR by time
(seconds); sample density via `frame_step` (every Nth frame) or
`frame_interval` (seconds between frames). All backends yield BGR uint8
arrays of shape `(H, W, 3)` — the OpenCV convention.

```python
for frame in vh.extract_frames(
    "clip.mp4",
    start_instant=5.0,
    end_instant=10.0,
    frame_interval=0.5,   # one frame every 0.5 s
):
    pass
```

### Sparse / Random Access

Need a handful of frames at specific times? Pass `frame_indices` or
`frame_times` instead of a range — the dispatcher routes to decord (when
installed; fastest for this pattern) and falls back to PyAV otherwise.

```python
frames = list(vh.extract_frames("clip.mp4", frame_times=[1.5, 12.0, 47.0]))
frames = list(vh.extract_frames("clip.mp4", frame_indices=[0, 150, 900]))
```

For long videos with a few sparse picks this is **dramatically** faster
than the range API — backends keyframe-seek instead of decoding
everything from t=0.

### Choosing a Backend

| Backend | Best for | Notes |
|---|---|---|
| `vidgear` | Stabilization (`stabilize=True`) | Only path with software stabilizer. Decodes from t=0; slowest for narrow windows. |
| `pyav` | Sequential time-range reads | Default when installed. Lowest Python overhead, supports `hwaccel`. |
| `decord` | Sparse / random-access reads | Fastest for `frame_indices` / `frame_times`. Manual install on Py3.13+. |
| `ffmpeg-pipe` | Sequential, no PyAV available | Subprocess + raw bgr24 pipe. Honors `hwaccel`. No sparse support. |

```python
# Let the dispatcher decide (default).
frames = list(vh.extract_frames("clip.mp4", start_instant=0, end_instant=2))

# Force a specific backend (useful for benchmarking or debugging).
frames = list(vh.extract_frames("clip.mp4", start_instant=0, end_instant=2,
                                backend="pyav"))

# Stabilization always forces VidGear:
frames = list(vh.extract_frames("clip.mp4", stabilize=True))
```

### Hardware Acceleration

`hwaccel="auto"` (the default) picks the best decoder block exposed by
your local ffmpeg build:

- macOS → `videotoolbox` (Apple's media engine — fast, very low-power,
  great on Apple Silicon for H.264 / HEVC / VP9; M3+ adds AV1).
- Linux + NVIDIA → `cuda` (NVDEC).
- Linux + Intel iGPU → `qsv` (QuickSync).
- Otherwise → software decode.

Realistic speedup is ~2-3× for HD/4K H.264-HEVC on CPU+hwaccel paths
(the bottleneck moves to the device → host frame copy). Bigger wins
come from **keeping frames on GPU** for a downstream ML pipeline, which
is outside this function's scope.

```python
# Explicitly disable hwaccel (useful for benchmarking or buggy drivers).
frames = list(vh.extract_frames("clip.mp4", backend="pyav", hwaccel=None))

# Force a specific accelerator.
frames = list(vh.extract_frames("clip.mp4", backend="pyav", hwaccel="videotoolbox"))
```

`hwaccel` is ignored by `vidgear` (OpenCV doesn't surface it cleanly).

### Destination: numpy or torch tensors

By default, `extract_frames` yields BGR uint8 `numpy.ndarray` of shape
`(H, W, 3)` — same convention as OpenCV. For ML pipelines you can
yield `torch.Tensor` directly (lazy torch import; raises `ImportError`
if torch isn't installed):

```python
import torch

# Per-frame torch tensors on Apple Silicon GPU.
for frame in vh.extract_frames(
    "clip.mp4",
    destination="torch", device="mps",
):
    # frame.shape == (H, W, 3); BGR uint8; on MPS
    ...
```

For maximum throughput, **batch the transfer**: one host→device copy
per batch instead of one per frame.

```python
for batch in vh.extract_frames(
    "clip.mp4",
    destination="torch", device="mps", batch_size=32,
):
    # batch.shape == (N, H, W, 3); N == 32 for all but the last batch
    embeddings = model(batch)
```

`device="auto"` resolves to cuda → mps → cpu in that order.

The same `batch_size` kwarg works with `destination="numpy"` — yields
`(N, H, W, 3)` ndarrays:

```python
for batch in vh.extract_frames("clip.mp4", batch_size=16):
    # batch.shape == (16, H, W, 3) numpy uint8 BGR
    ...
```

**Honest performance note:** at the time of v1.4.0, the torch path
materializes each frame as numpy before stacking and shipping to
device. That's one round-trip per batch, not zero-copy. A future C++
extension (planned for v1.5+) will let VideoToolbox / NVDEC hand
frames directly to torch on-device without the numpy intermediate —
see `SPEED_ANALYSIS.md` for the latest measurements. The current
batched path is already a 5-20× win over manually wrapping each frame
in `torch.from_numpy(...).to(device)`.

### Dump Frames to a Video

`dump_frames` is the inverse: a list of frames → video file.

```python
import numpy as np
frames = [np.zeros((72, 128, 3), dtype=np.uint8) for _ in range(30)]
vh.dump_frames(frames, "buffer.mp4", fps=15)
```

## Temporal Crop

`extract_video_chunk(input, start_s, end_s, output)` cuts a `[start, end]`
slice. Out-of-range bounds raise `AssertionError`. The output container
is dictated by the output extension.

```python
vh.extract_video_chunk("podcast.mp4", 60.0, 75.0, "highlight.mp4")
```

## Pipeline Primitives

### Black Video

```python
vh.black_video(0.5, 1920, 1080, "buffer.mp4", frame_rate=30)
```

Useful as a breathing clip between two visuals or as a placeholder for a
missing asset.

### Image Loop

Loop a still into a silent video. Pass both `width` and `height` for
aspect-preserving letterboxing (black padding).

```python
vh.image_loop_to_video(
    "title.png", 3.0, "title.mp4",
    frame_rate=30, width=1920, height=1080,
)
```

### Concatenate

End-to-end concat via the ffmpeg `concat` demuxer (the only safe path
for clips with different codecs / framerates).

```python
vh.concat_videos(
    ["intro.mp4", "body.mp4", "outro.mp4"],
    "final.mp4",
    reencode=True,        # default; only set False if all inputs are bit-identical containers
    frame_rate=30,
)
```

### Overlay Image

Overlay a PNG (alpha supported). `x` / `y` accept plain integers OR
ffmpeg expressions for time-varying motion.

```python
vh.overlay_image(
    "clip.mp4", "cursor.png", "out.mp4",
    x="if(lt(t,2),100,400)",   # move at t=2s
    y="200",
    scale_width=24,
)
```

### Extract / Mux Audio

```python
# Pull the audio out of a video.
vh.extract_audio_track("interview.mp4", "interview.wav")
vh.extract_audio_track("interview.mp4", "interview.mp3",
                       encoding="libmp3lame", sample_rate=22050)

# Replace a video's audio track with a separate file.
vh.mux_audio_video("silent.mp4", "voice.wav", "final.mp4")
```

The video stream is copied (no re-encode) — fast and lossless on the
video side.

### Burn Subtitles

Permanently bake subtitles into the video frames. Accepts `.srt`, `.vtt`,
`.ass`, `.ssa`. Requires ffmpeg with `libass`.

```python
# Plain SRT, default style.
vh.burn_subtitles("clip.mp4", "subs.srt", "captioned.mp4")

# Colored WebVTT (cue classes carry their own colors).
vh.burn_subtitles("clip.mp4", "subs.vtt", "captioned.mp4")

# Force a font + size on top of any source format.
vh.burn_subtitles(
    "clip.mp4", "subs.vtt", "captioned.mp4",
    force_style="FontName=Helvetica,FontSize=28,Outline=2",
)
```

## Subtitle Tools

### SRT → VTT + CSS

`srt2vtt` lifts `<font color="#RRGGBB">…</font>` SRT tags into WebVTT
`<c.rrggbb>…</c>` cue classes and writes a companion CSS file with one
`::cue(.rrggbb)` rule per color.

```python
vh.srt2vtt("subs.srt")                       # → subs.vtt + subs.css
vh.srt2vtt("subs.srt", "out.vtt", "out.css") # explicit paths
```

### Unique Colors

`extract_unique_colors` returns the set of hex colors found in `<font
color>` tags of an SRT. Useful for previewing the palette before a
conversion.

```python
print(vh.extract_unique_colors("subs.srt"))
# {'#FF0000', '#00FF00', '#0000FF'}
```
