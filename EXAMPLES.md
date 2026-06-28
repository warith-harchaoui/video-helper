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
# Core only — vidgear + opencv + ffmpeg-python (no optional backends).
pip install --force-reinstall --no-cache-dir \
  git+https://github.com/warith-harchaoui/video-helper.git@v1.4.1
```

Optional extras (mix and match, or install `[all]`):

```bash
# [pyav]  — best windowed-sequential + sparse decoder. Honors hwaccel.
# [torch] — destination="torch" (NCHW / CTHW RGB on cpu / mps / cuda).
# [pil]   — destination="pil" (PIL.Image, RGB, size=(W, H)).
# [all]   — everything (pyav + torch + pillow).

pip install --force-reinstall --no-cache-dir \
  "video-helper[all] @ git+https://github.com/warith-harchaoui/video-helper.git@v1.4.1"
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
`frame_times` instead of a range — the dispatcher routes to PyAV
(keyframe-seek) and falls back to VidGear (decode-all then filter) if
PyAV isn't installed.

```python
frames = list(vh.extract_frames("clip.mp4", frame_times=[1.5, 12.0, 47.0]))
frames = list(vh.extract_frames("clip.mp4", frame_indices=[0, 150, 900]))
```

For long videos with a few sparse picks this is **dramatically** faster
than the range API — PyAV keyframe-seeks instead of decoding everything
from t=0.

### Choosing a Backend

| Backend | Best for | Notes |
|---|---|---|
| `vidgear` | Full sequential ≤ 720p, and **only** path for `stabilize=True` | OpenCV + producer thread. Decodes from t=0; pays a tax on windowed / sparse reads. |
| `pyav` | Windowed sequential, sparse access, any `destination="torch"` + GPU | libav direct bindings. Lowest Python overhead, supports `hwaccel`. |
| `ffmpeg-pipe` | Sequential when PyAV isn't installed | Subprocess + raw bgr24 pipe. Honors `hwaccel`. No sparse support. ~10-20× slower than PyAV — keep only as fallback. |

A decord backend was prototyped during v1.4 development and dropped —
see [`SPEED_ANALYSIS.md`](SPEED_ANALYSIS.md) for the numbers (PyAV
beat decord ~30 % on its own sweet spot in our bench).

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

Default is `hwaccel=None` (software decode). Opt in via `hwaccel="auto"`
or an explicit value (`"videotoolbox"`, `"cuda"`, `"qsv"`). `"auto"`
resolves to:

- macOS → `videotoolbox` (Apple's media engine — fast, very low-power,
  great on Apple Silicon for H.264 / HEVC / VP9; M3+ adds AV1).
- Linux + NVIDIA → `cuda` (NVDEC).
- Linux + Intel iGPU → `qsv` (QuickSync).
- Otherwise → software decode.

```python
# Opt into the platform-appropriate hardware decoder.
frames = list(vh.extract_frames("clip.mp4", hwaccel="auto"))

# Force a specific accelerator.
frames = list(vh.extract_frames("clip.mp4", hwaccel="videotoolbox"))
```

`hwaccel` is ignored by `vidgear` (OpenCV doesn't surface it cleanly).

**Honest performance note** (see [SPEED_ANALYSIS.md](SPEED_ANALYSIS.md)):
hwaccel **does** offload decode to the media engine (CPU/Wall ratio
drops from ~4× to ~0.8× — CPU is mostly idle), **but** wall time is
2-3× *worse* for `destination="numpy"` because the frames still need a
GPU→CPU + swscale roundtrip to land as BGR numpy arrays. So with
`destination="numpy"`, hwaccel is a **power / parallelism win**, not a
latency win — useful for batch jobs on battery, or to free the CPU for
downstream work. For `destination="torch"` + GPU device, the dispatcher
auto-enables hwaccel: the host→device transfer is unavoidable but
batched, and the offload is worth it.

### Destination: numpy, torch, or PIL

`extract_frames` honors the **conventional** colorspace and axis layout
for the destination framework:

| Destination  | Colorspace | Per-frame shape | Batched shape (`batch_size=N`)                    |
|---|---|---|---|
| `"numpy"` (default, OpenCV) | **BGR** uint8 | `(H, W, 3)` HWC | `(N, H, W, 3)` NHWC (`layout="image"`) **or** THWC (`layout="video"`) — same memory |
| `"torch"` (PyTorch)         | **RGB** uint8 | `(3, H, W)` CHW | `(N, 3, H, W)` NCHW (`layout="image"`) **or** `(3, N, H, W)` CTHW (`layout="video"`) |
| `"pil"` (Pillow)            | **RGB**       | `PIL.Image`, `size=(W, H)` | not supported (Pillow has no batched type) |

Legend: N = batch size, T = time (= N), C = channels (= 3), H = height, W = width.

Notes:
- For numpy the `layout` choice is **purely semantic** (NHWC and THWC
  share the same memory layout). For torch it's a real permutation —
  NCHW vs CTHW differ in axis order.
- PIL's `image.size` is `(W, H)`, opposite from numpy/torch's `(H, W)`.
- All non-numpy destinations are **lazy imports**: video-helper itself
  doesn't take torch or Pillow as a dependency.

```python
# Default — numpy, BGR, channels last (OpenCV style).
for frame in vh.extract_frames("clip.mp4", start_instant=10, end_instant=20):
    # frame.shape == (H, W, 3), BGR uint8
    ...

# Torch CHW RGB on Apple Silicon GPU, per-frame.
import torch
for frame in vh.extract_frames("clip.mp4", destination="torch", device="mps"):
    # frame.shape == (3, H, W), RGB uint8, on MPS
    ...

# Torch NCHW RGB — typical image-model batch.
for batch in vh.extract_frames(
    "clip.mp4",
    destination="torch", device="mps", batch_size=32, layout="image",
):
    # batch.shape == (N, 3, H, W); one host→device transfer per batch
    embeddings = image_model(batch)

# Torch CTHW RGB — typical 3D-CNN / video-model clip.
for clip in vh.extract_frames(
    "clip.mp4",
    destination="torch", device="mps", batch_size=16, layout="video",
):
    # clip.shape == (3, T, H, W); T == 16 for all but the last clip
    embedding = video_model(clip)

# PIL.Image per frame — for code that uses Pillow filters / draw / paste.
for im in vh.extract_frames("clip.mp4", destination="pil"):
    # im.mode == "RGB", im.size == (W, H)
    im.filter(...)
```

`device="auto"` for torch resolves to `cuda` → `mps` → `cpu` in that order.

**Honest performance note:** at the time of v1.4.1, the torch path
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
