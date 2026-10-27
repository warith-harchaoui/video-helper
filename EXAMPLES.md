# Video Helper Examples

[🇫🇷 EXEMPLES.md](https://github.com/warith-harchaoui/video-helper/blob/main/EXEMPLES.md) · 🇬🇧 English

Practical recipes for the public surface of `video-helper`. Each numbered
section is a scenario, not a function listing. Every snippet was checked against
the code, and every snippet that can run offline on a local clip was run while
this file was written — the outputs shown are what came back. A few of them need
something a plain checkout cannot supply (an ffmpeg built with `libass`, a live
header-gated URL, the face weights fetched on first use); each says so where it
appears.

---

## Table of Contents

- [Setup](#setup)
- [1. Probe & Validate](#1-probe--validate)
- [2. Convert & Resize](#2-convert--resize)
- [3. Frame Access](#3-frame-access)
  - [Iterate Frames](#iterate-frames)
  - [Sparse / Random Access](#sparse--random-access)
  - [Choosing a Backend](#choosing-a-backend)
  - [Hardware Acceleration](#hardware-acceleration)
  - [HTTP Headers (auth-protected URLs)](#http-headers-auth-protected-urls)
  - [Exact Output Size with Aspect-Preserving Padding](#exact-output-size-with-aspect-preserving-padding)
  - [Destination: numpy, torch, or PIL](#destination-numpy-torch-or-pil)
  - [Optical Flow](#optical-flow)
  - [Dump Frames to a Video](#dump-frames-to-a-video)
- [4. Temporal Crop](#4-temporal-crop)
- [5. Pipeline Primitives](#5-pipeline-primitives)
  - [Black Video](#black-video)
  - [Image Loop](#image-loop)
  - [Concatenate](#concatenate)
  - [Overlay Image](#overlay-image)
  - [Extract / Mux Audio](#extract--mux-audio)
  - [Burn Subtitles](#burn-subtitles)
  - [Compress to a Target Size](#compress-to-a-target-size)
- [6. Subtitle Tools](#6-subtitle-tools)
  - [SRT → VTT + CSS](#srt--vtt--css)
  - [Unique Colors](#unique-colors)
- [7. Face-Anchored Speaker Identity](#7-face-anchored-speaker-identity)
- [Command line](#command-line)
- [Troubleshooting](#troubleshooting)

---

## Setup

```bash
# Core only: vidgear + opencv + ffmpeg-python (no optional backends).
pip install --force-reinstall --no-cache-dir \
  video-helper
```

Optional extras (mix and match, or install `[all]`):

```bash
# [pyav]:  best windowed-sequential + sparse decoder. Honors hwaccel.
# [torch]: destination="torch" (NCHW / CTHW RGB on cpu / mps / cuda).
# [pil]:   destination="pil" (PIL.Image, RGB, size=(W, H)).
# [flow]:  method="raft" and the wavelet flow resize.
# [faces]: face-anchored speaker identity (section 7).
# [all]:   pyav + torch + pillow + torchvision + PyWavelets.

pip install --force-reinstall --no-cache-dir \
  "video-helper[all]"
```

Every snippet from here on assumes this import, and nothing else:

```python
import video_helper as vh
```

A handful of snippets build or inspect arrays directly and add
`import numpy as np`; each one shows the import where it needs it.

You also need `ffmpeg` on `PATH`. macOS: `brew install ffmpeg` (install `brew`
thanks to [brew.sh](https://brew.sh/)). Linux: `apt install ffmpeg`. Windows:
see the [ffmpeg site](https://ffmpeg.org/download.html).

[`burn_subtitles`](#burn-subtitles) needs an ffmpeg built with `libass`, which
not every binary distribution ships — see
[Troubleshooting](#troubleshooting).

## 1. Probe & Validate

```python
if vh.is_valid_video_file("clip.mp4"):
    info = vh.video_dimensions("clip.mp4")
    print(info)
    # {'width': 1920, 'height': 1080, 'duration': 12.333333,
    #  'frame_rate': 30.0, 'has_sound': True}

print(vh.video_duration("clip.mp4"))
# 12.333333
```

`duration` is whatever the container reports, to full float precision: do not
expect it to equal the duration you asked ffmpeg for when you made the file.

`is_valid_video_file` rejects fake `.mp4` files (no video stream) **and**
valid videos with non-video extensions.

`video_dimensions` also accepts a URL in place of a local path, plus an
optional `http_headers` dict forwarded to ffprobe: useful for
yt-dlp-resolved YouTube live, members-only, or age-gated content that
needs specific headers to be readable at all.

## 2. Convert & Resize

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

## 3. Frame Access

### Iterate Frames

`extract_frames` is a generator. Pick the range by index OR by time
(seconds); sample density via `frame_step` (every Nth frame) or
`frame_interval` (seconds between frames). All backends yield BGR uint8
arrays of shape `(H, W, 3)`, the OpenCV convention.

```python
for frame in vh.extract_frames(
    "clip.mp4",
    start_instant=5.0,
    end_instant=10.0,
    frame_interval=0.5,  # one frame every 0.5 s
):
    pass
```

### Sparse / Random Access

Need a handful of frames at specific times? Pass `frame_indices` or
`frame_times` instead of a range: the dispatcher routes to PyAV
(keyframe-seek) and falls back to VidGear (decode-all then filter) if
PyAV isn't installed.

```python
frames = list(vh.extract_frames("clip.mp4", frame_times=[1.5, 12.0, 47.0]))
frames = list(vh.extract_frames("clip.mp4", frame_indices=[0, 150, 900]))
```

For long videos with a few sparse picks this is **dramatically** faster
than the range API: PyAV keyframe-seeks instead of decoding everything
from t=0.

### Choosing a Backend

| Backend | Best for | Notes |
|---|---|---|
| `vidgear` | Full sequential ≤ 720p, and **only** path for `stabilize=True` | OpenCV + producer thread. Decodes from t=0; pays a tax on windowed / sparse reads. |
| `pyav` | Windowed sequential, sparse access, any `destination="torch"` + GPU | libav direct bindings. Lowest Python overhead, supports `hwaccel`. |
| `ffmpeg-pipe` | Sequential when PyAV isn't installed | Subprocess + raw bgr24 pipe. Honors `hwaccel`. No sparse support. ~10-20× slower than PyAV; keep only as fallback. |

A decord backend was prototyped during v1.4 development and dropped;
see [`SPEED_ANALYSIS.md`](SPEED_ANALYSIS.md) for the numbers (PyAV
beat decord ~30 % on its own sweet spot in our bench).

```python
# Let the dispatcher decide (default).
frames = list(vh.extract_frames("clip.mp4", start_instant=0, end_instant=2))

# Force a specific backend (useful for benchmarking or debugging).
frames = list(vh.extract_frames("clip.mp4", start_instant=0, end_instant=2, backend="pyav"))

# Stabilization always forces VidGear:
frames = list(vh.extract_frames("clip.mp4", stabilize=True))
```

**`stabilize=True` returns fewer frames than the video has.** VidGear's
stabilizer smooths over a trailing window (radius 25 by default) and that
window is never flushed at end of stream, so the last ~25 frames stay inside
it. Measured on a 2 s / 30 fps clip: 60 frames plain, 35 stabilized, and
stabilized frame *k* is source frame *k+1*. Ask for a slightly longer range
than you need, and do not rely on the two counts matching.

```python
print(len(list(vh.extract_frames("tiny30.mp4"))))  # 60
print(len(list(vh.extract_frames("tiny30.mp4", stabilize=True))))  # 35
```

### Hardware Acceleration

Default is `hwaccel=None` (software decode). Opt in via `hwaccel="auto"`
or an explicit value (`"videotoolbox"`, `"cuda"`, `"qsv"`). `"auto"`
resolves to:

- macOS → `videotoolbox` (Apple's media engine: fast, very low-power,
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
drops from ~4× to ~0.8×, CPU is mostly idle), **but** wall time is
2-3× *worse* for `destination="numpy"` because the frames still need a
GPU→CPU + swscale roundtrip to land as BGR numpy arrays. So with
`destination="numpy"`, hwaccel is a **power / parallelism win**, not a
latency win: useful for batch jobs on battery, or to free the CPU for
downstream work. For `destination="torch"` + GPU device, the dispatcher
auto-enables hwaccel: the host→device transfer is unavoidable but
batched, and the offload is worth it.

### HTTP Headers (auth-protected URLs)

Some sources need a specific `User-Agent` / `Referer` / `Cookie` / `Authorization` to play: typically yt-dlp-resolved YouTube live streams, members-only / age-gated content, Vimeo private videos, Twitch streams. Pass them via `http_headers`:

```python
# Headers obtained from youtube-helper (or hand-rolled)
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.youtube.com/",
}

for frame in vh.extract_frames(
    "https://rr5---sn-googlevideo.com/videoplayback?...",
    http_headers=headers,
    backend="pyav",  # or "ffmpeg-pipe"; vidgear warns + ignores
):
    print(frame.shape)
```

*Checked against the code but not run: the URL has to be a live, header-gated
stream resolved minutes earlier, which no fixture can stand in for.*

The VidGear backend logs a warning and ignores `http_headers`; OpenCV doesn't surface them cleanly. Use `backend="pyav"` (preferred) or `"ffmpeg-pipe"` for auth-protected URLs.

### Exact Output Size with Aspect-Preserving Padding

For ML pipelines that need a fixed input shape, set `output_width` + `output_height`. The frame is **scaled-fit** (aspect-preserving) and **padded** to exactly the requested size with `pad_color`:

```python
# 1920×1080 source → 224×224 square with black letterbox padding
for frame in vh.extract_frames(
    "clip.mp4",
    output_width=224,
    output_height=224,
    pad_color="black",
):
    # frame.shape == (224, 224, 3); the 16:9 source is centred horizontally
    # with black bands top and bottom (letterbox).
    model_input = frame
```

| `output_width` | `output_height` | Effect |
|---|---|---|
| set | set | Scale-fit + pad with `pad_color` to exact `(W, H)` |
| set | None | Scale to that width, preserve aspect, **no pad** (height derived) |
| None | set | Scale to that height, preserve aspect, **no pad** |
| None | None | Native dimensions (default) |

`pad_color` accepts `"black"` (default), `"white"`, `"red"`, `"green"`, `"blue"`, `"yellow"`, `"cyan"`, `"magenta"`, `"gray"` / `"grey"`, or `"#RRGGBB"` hex. `"transparent"` is not implemented: it raises `ValueError`, since it would need 4-channel output.

Composable with everything else: destinations, hwaccel, sparse access.

```python
# Square torch tensors on Apple Silicon GPU, batched
for batch in vh.extract_frames(
    "clip.mp4",
    output_width=224,
    output_height=224,
    pad_color="black",
    destination="torch",
    device="mps",
    batch_size=32,
    layout="image",
):
    # batch.shape == (32, 3, 224, 224), NCHW RGB uint8 on MPS
    logits = model(batch)
```

### Destination: numpy, torch, or PIL

`extract_frames` honors the **conventional** colorspace and axis layout
for the destination framework:

| Destination  | Colorspace | Per-frame shape | Batched shape (`batch_size=N`)                    |
|---|---|---|---|
| `"numpy"` (default, OpenCV) | **BGR** uint8 | `(H, W, 3)` HWC | `(N, H, W, 3)` NHWC (`layout="image"`) **or** THWC (`layout="video"`), same memory |
| `"torch"` (PyTorch)         | **RGB** uint8 | `(3, H, W)` CHW | `(N, 3, H, W)` NCHW (`layout="image"`) **or** `(3, N, H, W)` CTHW (`layout="video"`) |
| `"pil"` (Pillow)            | **RGB**       | `PIL.Image`, `size=(W, H)` | not supported (Pillow has no batched type) |

Legend: N = batch size, T = time (= N), C = channels (= 3), H = height, W = width.

Notes:
- For numpy the `layout` choice is **purely semantic** (NHWC and THWC
  share the same memory layout). For torch it's a real permutation:
  NCHW vs CTHW differ in axis order.
- PIL's `image.size` is `(W, H)`, opposite from numpy/torch's `(H, W)`.
- All non-numpy destinations are **lazy imports**: video-helper itself
  doesn't take torch or Pillow as a dependency.

```python
# Default: numpy, BGR, channels last (OpenCV style).
for frame in vh.extract_frames("clip.mp4", start_instant=10, end_instant=20):
    # frame.shape == (H, W, 3), BGR uint8
    ...

# Torch CHW RGB on Apple Silicon GPU, per-frame.
import torch

for frame in vh.extract_frames("clip.mp4", destination="torch", device="mps"):
    # frame.shape == (3, H, W), RGB uint8, on MPS
    ...

# Torch NCHW RGB: typical image-model batch.
for batch in vh.extract_frames(
    "clip.mp4",
    destination="torch",
    device="mps",
    batch_size=32,
    layout="image",
):
    # batch.shape == (N, 3, H, W); one host→device transfer per batch
    embeddings = image_model(batch)

# Torch CTHW RGB: typical 3D-CNN / video-model clip.
for clip in vh.extract_frames(
    "clip.mp4",
    destination="torch",
    device="mps",
    batch_size=16,
    layout="video",
):
    # clip.shape == (3, T, H, W); T == 16 for all but the last clip
    embedding = video_model(clip)

# PIL.Image per frame: for code that uses Pillow filters / draw / paste.
for im in vh.extract_frames("clip.mp4", destination="pil"):
    # im.mode == "RGB", im.size == (W, H)
    im.filter(...)
```

`device="auto"` for torch resolves to `cuda` → `mps` → `cpu` in that order.

**Honest performance note:** the torch path materializes each frame as numpy
and hands it over with `torch.from_numpy(...).to(device)`, so there is one
host→device round-trip per batch, not zero-copy. Letting VideoToolbox / NVDEC
hand frames straight to torch on-device would need a C++ extension; it is
listed as pending work in
[SPEED_ANALYSIS.md](https://github.com/warith-harchaoui/video-helper/blob/main/SPEED_ANALYSIS.md),
not scheduled. Batching is still what makes the current path worth using: the
same document measures it at 5-20× the throughput of wrapping each frame
individually.

### Optical Flow

`iter_frame_optical_flow` wraps **any** `(H, W, 3)` BGR uint8 frame iterator
(`extract_frames` output, or a live source sharing the same contract such as
`capture_helper.iter_camera_frames`) and re-yields `(H, W, 5)` float32
arrays: the frame (channels 0-2) plus dense flow `vx`/`vy` (channels 3-4)
relative to the previous frame. This composability (input is a generic
iterator, not a video path) is the point: the same call works for a file or
a live camera.

```python
# Default: DIS, no extra dependency (opencv-python is already core).
frames = vh.extract_frames("clip.mp4", frame_step=1)
for flow_frame in vh.iter_frame_optical_flow(frames, method="dis"):
    bgr = flow_frame[..., :3].astype("uint8")  # back to a plain frame
    vx, vy = flow_frame[..., 3], flow_frame[..., 4]  # signed px displacement

# Composes with a live camera the exact same way (capture-helper, not
# video-helper, owns the camera loop: no opencv/torch dependency added there).
import capture_helper as ch

for flow_frame in vh.iter_frame_optical_flow(ch.iter_camera_frames(), method="dis"):
    ...

# Deep-learning flow (RAFT via torchvision): needs `pip install "video-helper[flow]"`.
for flow_frame in vh.iter_frame_optical_flow(
    frames, method="raft", raft_variant="small", device="mps"
):
    ...

# grayscale=True: (H, W, 3) instead of (H, W, 5), intensity + flow only,
# a smaller motion-focused representation (e.g. feeding a flow-only model).
for flow_frame in vh.iter_frame_optical_flow(frames, method="dis", grayscale=True):
    gray = flow_frame[..., 0].astype("uint8")
    vx, vy = flow_frame[..., 1], flow_frame[..., 2]
```

The first yielded frame always has zero flow (no previous frame yet), so
frame count stays 1:1 with the input iterator. `method="dis"` (default) and
`"farneback"` are CPU-only OpenCV calls; `method="raft"` is quality-first and
GPU-recommended (CPU RAFT is not expected to be real-time), and requires
frames at least ~128px per side (an inherent RAFT constraint, not
video-helper's).

For the common "just give me flow for this video file" case, `extract_optical_flow`
wraps the two above into a single call, no manual frame-iterator plumbing:

```python
# Output kind is inferred from the extension: anything but '.npy' -> HSV
# visualization video; '.npy' -> the raw (T, H, W, 2) float32 flow array.
vh.extract_optical_flow("clip.mp4", "clip-flow.mp4", method="dis")
vh.extract_optical_flow("clip.mp4", "clip-flow.npy", method="dis")
```

Same operation on every other surface, matching every other function in the suite:

```bash
video-helper extract-flow --input clip.mp4 --output clip-flow.mp4 --method dis
curl -F 'file=@clip.mp4' -F 'method=dis' -o clip-flow.mp4 http://localhost:8000/extract-flow
# MCP: auto-published as a tool from the same FastAPI route, no extra setup.
```

**Resizing a computed flow field:** `output_width`/`output_height` (both required
together) go through `resize_flow`, wavelet-based instead of plain bilinear/bicubic,
so a motion boundary isn't smeared across the resize, and the flow *magnitude*
is correctly rescaled by the same factor as the spatial resize (needs
`pip install "video-helper[flow]"` for `PyWavelets`):

```python
# Shrink the flow output for storage: computed at full quality, then downsized.
vh.extract_optical_flow(
    "clip.mp4",
    "clip-flow.npy",
    method="dis",
    output_width=320,
    output_height=180,
)

# Or resize a flow field you already have, standalone:
resized = vh.resize_flow(flow[..., -2:], output_width=320, output_height=180)
```

### Dump Frames to a Video

`dump_frames` is the inverse: a list of frames → video file.

```python
import numpy as np

frames = [np.zeros((72, 128, 3), dtype=np.uint8) for _ in range(30)]
vh.dump_frames(frames, "buffer.mp4", fps=15)
```

## 4. Temporal Crop

`extract_video_chunk(input, start_s, end_s, output)` cuts a `[start, end]`
slice. Out-of-range bounds raise `AssertionError`. The output container
is dictated by the output extension. Pass `copy=True` to stream-copy the
cut instead of re-encoding it: fast and lossless, but only frame-accurate
when every frame of the input is already a keyframe.

```python
vh.extract_video_chunk("podcast.mp4", 60.0, 75.0, "highlight.mp4")

# Stream-copy: fast, no re-encode, needs keyframe-aligned bounds.
vh.extract_video_chunk("podcast.mp4", 60.0, 75.0, "highlight.mp4", copy=True)
```

## 5. Pipeline Primitives

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
    "title.png",
    3.0,
    "title.mp4",
    frame_rate=30,
    width=1920,
    height=1080,
)
```

### Concatenate

End-to-end concat via the ffmpeg `concat` demuxer (the only safe path
for clips with different codecs / framerates).

```python
vh.concat_videos(
    ["intro.mp4", "body.mp4", "outro.mp4"],
    "final.mp4",
    reencode=True,  # default; only set False if all inputs are bit-identical containers
    frame_rate=30,
)
```

### Overlay Image

Overlay a PNG (alpha supported). `x` / `y` accept plain integers OR
ffmpeg expressions for time-varying motion.

```python
vh.overlay_image(
    "clip.mp4",
    "cursor.png",
    "out.mp4",
    x="if(lt(t,2),100,400)",  # move at t=2s
    y="200",
    scale_width=24,
)
```

### Extract / Mux Audio

```python
# Pull the audio out of a video.
vh.extract_audio_track("interview.mp4", "interview.wav")
vh.extract_audio_track("interview.mp4", "interview.mp3", encoding="libmp3lame", sample_rate=22050)

# Replace a video's audio track with a separate file.
vh.mux_audio_video("silent.mp4", "voice.wav", "final.mp4")
```

The video stream is copied (no re-encode): fast and lossless on the
video side.

### Burn Subtitles

Permanently bake subtitles into the video frames. Accepts `.srt`, `.vtt`,
`.ass`, `.ssa`. Requires ffmpeg with `libass`.

*Checked against the code but not run here: the ffmpeg on this machine has no
`subtitles` filter, which is exactly the failure described under
[Troubleshooting](#troubleshooting).*

```python
# Plain SRT, default style.
vh.burn_subtitles("clip.mp4", "subs.srt", "captioned.mp4")

# Colored WebVTT (cue classes carry their own colors).
vh.burn_subtitles("clip.mp4", "subs.vtt", "captioned.mp4")

# Force a font + size on top of any source format.
vh.burn_subtitles(
    "clip.mp4",
    "subs.vtt",
    "captioned.mp4",
    force_style="FontName=Helvetica,FontSize=28,Outline=2",
)
```

### Compress to a Target Size

`compress_video` solves for the video bitrate that lands the whole file on
`target_size_mb` given its duration, then encodes at that bitrate in two
passes. Built for "the file that gets embedded in a web player", not for an
archival master.

```python
import os

# A 12.3 s 1080p clip, 1.776 MB on disk, asked to fit in 1 MB.
out = vh.compress_video("big.mp4", "web.mp4", target_size_mb=1.0)
print(out, round(os.path.getsize(out) / 1e6, 3), "MB")
# web.mp4 1.002 MB
```

The default codec is HEVC (`libx265`) tagged `hvc1`, because ffmpeg's own
default `hev1` tag is not recognised by QuickTime and Apple players.

```python
# macOS: single-pass hardware HEVC. Much faster, slightly worse per bit.
vh.compress_video("big.mp4", "vt.mp4", target_size_mb=1.0, vcodec="hevc_videotoolbox")

# Already small enough: remux only (adds +faststart), no re-encode at all.
vh.compress_video("clip.mp4", "remux.mp4", vcodec="copy")
```

A target so small that the solved bitrate falls under `min_video_bitrate_kbps`
(200 by default) is not silently honoured: the floor wins, the output overshoots
the target, and you get told so on the log rather than after measuring the file.

```
compress_video: target 0.3 MB over 12 sec would need 76 kbps for video —
below the 200 kbps floor. Using the floor instead; the output will exceed 0.3 MB.
```

## 6. Subtitle Tools

### SRT → VTT + CSS

`srt2vtt` lifts `<font color="#RRGGBB">…</font>` SRT tags into WebVTT
`<c.rrggbb>…</c>` cue classes and writes a companion CSS file with one
`::cue(.rrggbb)` rule per color.

```python
vh.srt2vtt("subs.srt")  # → subs.vtt + subs.css
vh.srt2vtt("subs.srt", "out.vtt", "out.css")  # explicit paths
```

### Unique Colors

`extract_unique_colors` returns the set of hex colors found in `<font
color>` tags of an SRT. Useful for previewing the palette before a
conversion.

```python
print(sorted(vh.extract_unique_colors("subs.srt")))
# ['#0000FF', '#00FF00', '#FF0000']
```

The return value is a `set`, so sort it before printing or comparing: set
iteration order is not part of Python's contract and changes between runs.

## 7. Face-Anchored Speaker Identity

Needs the `[faces]` extra: `pip install "video-helper[faces]"`.

*The snippets in this section were checked against the code and not run: the
first call downloads the YuNet / SFace / Light-ASD weights (see
[`video_helper.faces.models`](https://github.com/warith-harchaoui/video-helper/blob/main/video_helper/faces/models.py)),
so their output depends on a network fetch and on the faces in your own clip.
No output is shown below for that reason.*

Audio-only diarization (splitting a recording into "who spoke when" from the
sound alone) tells you a voice cluster exists, but not which on-screen face
it belongs to. `video_helper.faces` answers that by detecting faces, tracking
them from frame to frame, and scoring which tracked face's lip motion lines
up with a given speaker's audio activity. Two pieces cover the common cases:

```python
from video_helper.faces import FaceDetector, track_faces

detector = FaceDetector()

# Detect faces (with 5 landmarks each) in every frame of a short clip.
frame_dets = []
for i, frame in enumerate(vh.extract_frames("meeting.mp4", start_instant=0, end_instant=5)):
    frame_dets.append((i, detector.detect(frame)))

# Link per-frame detections into continuous tracks (one per person on screen).
tracks = track_faces(frame_dets)
print(len(tracks), "face track(s) found in the first 5 seconds")
```

The harness that ties detection, tracking, and active-speaker scoring
together is `active_speaker_map`: given diarization turns (e.g. from
`vocal-helper`), it samples a handful of short clips instead of decoding the
whole recording, growing the sample only for speakers it isn't yet sure
about:

```python
from video_helper.faces import active_speaker_map

# One dict per diarization turn: which cluster spoke, at what time.
speaker_turns = [
    {"spk": 0, "t0": 0.0, "t1": 4.2},
    {"spk": 1, "t0": 4.2, "t1": 9.0},
    {"spk": 0, "t0": 9.0, "t1": 14.5},
]

assignments = active_speaker_map("meeting.mp4", audio_16k=None, speaker_turns=speaker_turns)
for a in assignments:
    print(
        f"speaker {a.speaker} -> face {a.face_id} "
        f"(coverage={a.coverage:.2f}, margin={a.margin:.2f})"
    )
```

Each `SpeakerFaceAssignment` carries `crops` too: the best `(frame, Face)`
samples of the assigned face, ready to hand to `FaceRecognizer` for a
persistent embedding. A speaker that never gathered enough on-screen
evidence (`coverage` below the floor) is simply left out of the results,
so the caller's voice-only fallback still applies.

See the [`faces` module docstring](https://github.com/warith-harchaoui/video-helper/blob/main/video_helper/faces/__init__.py) for the
full picture: `FaceRecognizer` (SFace embeddings), `mouth_roi` /
`mouth_openness` (the lip-motion signal), `get_engine` (the zero-weight
proxy vs. the accurate Light-ASD PyTorch model), and `build_asd_digest`
(the internal clip-compaction step `active_speaker_map` uses on long
recordings).

## Command line

One `click` command line covers the same operations, so a shell script needs no
Python wrapper. `--help` on the group lists every sub-command, and `--help` on
any sub-command lists its options.

```bash
video-helper --help
video-helper extract-frames --help
video-helper --version
# video-helper, version 2.8.0
```

The three read-only commands print to stdout and nothing else, so they pipe:

```bash
$ video-helper validate --input clip.mp4
true

$ video-helper duration --input clip.mp4
12.333333

$ video-helper dimensions --input clip.mp4
{
  "width": 1920,
  "height": 1080,
  "duration": 12.333333,
  "frame_rate": 30.0,
  "has_sound": true
}
```

Every command that writes a single file echoes the path it wrote, so `$(…)`
chains:

```bash
video-helper convert   --input clip.mp4 --output small.mp4 \
                       --width 640 --height 360 --frame-rate 15 --without-sound
video-helper chunk     --input clip.mp4 --start 6 --end 9 --output highlight.mp4
video-helper compress  --input big.mp4  --output web.mp4 --target-size-mb 1
video-helper black     --duration 0.5 --width 1280 --height 720 --output black.mp4
video-helper image-loop --image title.png --duration 2 --output title.mp4 \
                       --width 1280 --height 720
video-helper overlay   --input clip.mp4 --image cursor.png --output overlaid.mp4 \
                       --x 100 --y 200 --scale-width 24
video-helper extract-audio --input clip.mp4 --output track.wav
video-helper mux-audio --input title.mp4 --audio track.wav --output narrated.mp4 --shortest
video-helper burn-subs --input clip.mp4 --subs subs.srt --output captioned.mp4
video-helper srt2vtt   --input subs.srt --output subs.vtt --css subs.css
```

`concat` is the one command whose option is **plural**, because it takes a list.
Both spellings work and order is preserved:

```bash
video-helper concat --inputs intro.mp4 body.mp4 outro.mp4 --output final.mp4
video-helper concat --inputs intro.mp4 --inputs body.mp4 --inputs outro.mp4 --output final.mp4
```

`--input` on `concat` is an error rather than a silent one-file concat:

```
Error: No such option '--input'. (Did you mean one of: '--inputs', '--output'?)
```

`extract-frames` writes one PNG per sampled frame and reports the manifest as
JSON, so the next step in a shell pipeline can read it with `jq`:

```bash
$ video-helper extract-frames --input clip.mp4 --output-dir frames \
      --frame-interval 2 --start 0 --end 6
{
  "frames": [
    "frames/frame_000000000.png",
    "frames/frame_000000001.png",
    "frames/frame_000000002.png",
    "frames/frame_000000003.png"
  ],
  "count": 4
}
```

`extract-flow` mirrors [Optical Flow](#optical-flow): the output extension picks
the kind, `.npy` for the raw `(T, H, W, 2)` array and anything else for the HSV
visualization video.

```bash
video-helper extract-flow --input clip.mp4 --output flow.npy --method dis \
      --start 0 --end 1 --output-width 160 --output-height 90
# flow.npy
```

## Troubleshooting

**`RuntimeError: ffmpeg has no 'subtitles' filter (libass missing)`** —
`burn_subtitles` and `video-helper burn-subs` need an ffmpeg built with
`--enable-libass`, and several binary distributions (including some
homebrew-core bottles) ship without it. Check before you need it:

```bash
ffmpeg -hide_banner -filters | grep subtitles
```

No output means no libass. On macOS, `brew uninstall ffmpeg && brew install
ffmpeg --HEAD` builds one that has it. Nothing else in the package is affected:
`srt2vtt` and `extract_unique_colors` parse subtitles in Python and work either
way.

**`ValueError` on `pad_color="transparent"`** — deliberate. Transparency would
require 4-channel BGRA/RGBA frames, which would break the `(H, W, 3)` contract
every destination promises. Pad with an unused colour and carry the mask
yourself.

**Sparse access feels slow** — `frame_indices` / `frame_times` keyframe-seek
only on the PyAV backend. Without the `[pyav]` extra the dispatcher falls back
to VidGear, which decodes from t=0 and then filters, so the cost is the same as
reading the whole file. `pip install "video-helper[pyav]"`.

**`hwaccel="auto"` made it slower** — expected for `destination="numpy"`, and
measured in
[SPEED_ANALYSIS.md](https://github.com/warith-harchaoui/video-helper/blob/main/SPEED_ANALYSIS.md):
the decode moves to the media engine, then the frames have to come back over
the bus and through swscale to land as BGR arrays. It is a power and
parallelism win, not a latency win. For `destination="torch"` on a GPU device
the dispatcher enables it on its own, where it does pay.

**`faces` quietly produces nothing** — the weights are fetched on first use
(see [7. Face-Anchored Speaker Identity](#7-face-anchored-speaker-identity)). If
no source can be reached, `ensure_model` returns `None`, detection is disabled
with a warning on the log and the ASD stack falls back to the zero-weight
lip-motion proxy. Degrading instead of crashing is the intent; check the log
rather than the exit code.
