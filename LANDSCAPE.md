# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/video-helper/blob/main/PAYSAGE.md) · 🇬🇧 English

Related and competing Python libraries in the "manipulate video files"
space, benchmarked against `video-helper`. Ratings are ⭐ (1) to
⭐⭐⭐⭐⭐ (5), scored on `video-helper`'s intended job: everyday video
handling for AI pipelines (validate, convert, chunk, concat, overlay,
extract-frames, extract-audio, mux-audio, burn subtitles, subtitle
format conversion, image-loop). A library optimised for a very
different job (e.g. real-time inference, non-linear editing) is not
penalised; the score just reflects fit to *this* niche.

## At a glance

<!-- TABLE:START -->
| Video Parsing | Multi-format I/O | Convert / scale-and-pad | Chunk / concat / overlay | Frame extraction | Subtitles | GPU decode | Multi-destination | Light install |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **video-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| moviepy | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| decord | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| torchvision.io | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐ |
| VidGear | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| OpenCV | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| ffmpeg-python | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| imageio | ⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| scenedetect | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
<!-- TABLE:END -->

## Positioning map

<!-- FIGURE:START -->
2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/video-helper/main/assets/landscape.png)

The map is a 2-D summary of the eight criteria, so read it as a shape, not a scoreboard. `video-helper` is at the top-right corner. The axes read **Horizontal: Nimble ↔ Versatile** and **Vertical: Compact ↔ Expansive**.
<!-- FIGURE:END -->

## Positioning

`video-helper` deliberately sits at the intersection of
**moviepy-level ergonomics** (one-line convert / chunk / concat /
overlay / burn subs) and **AI-pipeline needs** (multi-backend frame
extraction dispatcher, hwaccel, torch destination on demand, HTTP
headers passthrough for yt-dlp-resolved streams). It intentionally
does *not* try to compete with `PyAV` on the low-level packet API or
`torchvision.io` on native torch tensors, and it keeps `torch` and
`PIL` **optional**: you only pay their install cost if you actually
call `destination="torch"` / `destination="pil"`. That trade-off is the
main differentiator against `torchvision.io` (torch mandatory) and
against `decord`, whose newest release ships no wheel for Apple Silicon
nor for any Python ≥ 3.9 on macOS, so it has to be built from source
against `ffmpeg@4`.

Where the ratings come from, in a sentence each: multi-format I/O
leans on ffmpeg-native probing and muxing; frame extraction is a
dispatcher over VidGear / PyAV / ffmpeg-pipe with sparse, windowed and
streaming modes and a keyframe seek; subtitles cover libass burn-in
plus SRT→VTT conversion with CSS; GPU decode auto-detects the platform's
hwaccel (VideoToolbox on macOS, CUDA/NVDEC or Quick Sync on Linux/Windows)
through PyAV / ffmpeg-pipe; and multi-destination returns numpy by
default with torch and PIL available on request.

## When to pick what

- **`video-helper`**: video prep for AI pipelines. Batch convert plus
  scale-fit-and-pad to a fixed model input, sparse / windowed frame
  sampling with hwaccel, subtitle burn-in, audio mux for narration,
  concat for stitched training clips, HTTP headers passthrough for
  yt-dlp-resolved streams.
- **`moviepy`**: timeline-style scripting (place-and-cut clip graphs),
  compositing several clips into one, quick title cards. Not ideal for
  batch throughput.
- **`PyAV`**: you need packet-level control (custom codec settings,
  keyframe placement, seek precision).
- **`decord` / `torchvision.io`**: pure random-access, GPU-decoded
  frame reads straight into torch tensors, with a training loop that
  dominates total cost (dataloader-heavy workflow).
- **`VidGear`**: you need OpenCV+FFmpeg helpers with the built-in
  stabilizer and don't care about sparse access.
- **`OpenCV`**: quick prototyping, no batch throughput target, no
  subtitle needs.
- **`ffmpeg-python`**: you want to compose an arbitrary filter graph
  and don't need numpy interop.
- **`scenedetect`**: you specifically need shot-boundary detection.

## Sources and as-of date

Checked on **27 October 2026**. Every version and date below was read that day
from each project's own release metadata on PyPI
(`https://pypi.org/pypi/<name>/json`), which is the publisher's own record
rather than a third-party summary:

| Project | Newest release | Published |
|---|---|---|
| moviepy | 2.2.1 | 2025-05-21 |
| av (PyAV) | 19.0.2 | 2026-10-21 |
| decord | 0.6.0 | 2021-06-14 |
| torchvision | 0.29.1 | 2026-09-30 |
| vidgear | 0.3.6 | 2026-10-26 |
| opencv-python | 5.0.0.93 | 2026-07-02 |
| ffmpeg-python | 0.2.0 | 2019-07-06 |
| imageio | 2.38.1 | 2026-10-08 |
| scenedetect | 0.7.2 | 2026-10-12 |

Two rows of that table carry most of the weight of the star table above.

- `decord`'s ⭐⭐ on **Light install** is its wheel list, not an opinion: release
  0.6.0 publishes `macosx_10_15_x86_64` (CPython 3.6–3.8), `manylinux2010_x86_64`
  and `win_amd64`, and nothing else. `video-helper` prototyped a decord backend
  during v1.4 development and dropped it for that reason; the reasoning is in
  [SPEED_ANALYSIS.md](https://github.com/warith-harchaoui/video-helper/blob/main/SPEED_ANALYSIS.md)
  under *History*.
- `ffmpeg-python`'s ⭐⭐⭐⭐⭐ on **Light install** and its 2019 release date are the
  same fact seen twice: it is a small, finished argument builder over the ffmpeg
  CLI, which is also why `video-helper` depends on it.

The competitor columns are a judgement of **fit to this niche**, read off each
project's own documentation and public API. They are not a head-to-head
benchmark, and no number here was produced by running one. A claim that could
not be sourced was left out rather than estimated.

`video-helper`'s own row is not a third-party claim: the capabilities behind it
are the functions listed in
[README.md](https://github.com/warith-harchaoui/video-helper/blob/main/README.md)
and exercised by the test suite. The decode figures behind **GPU decode** and
**Frame extraction** come from
[SPEED_ANALYSIS.md](https://github.com/warith-harchaoui/video-helper/blob/main/SPEED_ANALYSIS.md),
measured on Apple Silicon / macOS (Darwin 25.5.0) with system ffmpeg 8.1.2 and
PyAV 17.1.0. That snapshot dates from the v1.4.0 backend redesign and has not
been re-measured since, so read it as an order of magnitude rather than as
today's milliseconds.

## Ideas worth stealing

Researched rather than guessed: what each neighbour does better, and what this library would have to change to match it. Nothing here is a commitment — it is the reading list the next version starts from.

- **`torchcodec` — the decoder PyTorch now points at** — Best-in-class CPU decoding plus CUDA-accelerated decoding, with a video exposed as a sequence of frames indexable by position or by presentation time. It matters doubly here: `torchvision.io`'s video API, which this table still rates, is being superseded by it, so that row is now legacy rather than a live alternative.

- **`decord` and `deffcode` — frame-accurate seeking as a stated guarantee** — Seeking to a timestamp and getting the frame you asked for — rather than the nearest keyframe — is the property callers assume and rarely verify. `deffcode` (April 2026) makes precise key-frame seeking its headline.

- **`scenedetect` — shot boundaries as a first-class operation** — Cutting on content rather than on a fixed interval is what most downstream uses actually want, and it composes with the chunking this library already does.

- **`VidGear` — a threaded read buffer ahead of the consumer** — Decoding on the calling thread makes every consumer pay full decode latency per frame. A bounded read-ahead buffer is cheap and is the same lesson the Rust capture twin learned about bounded queues.
