# Landscape

[🇫🇷 PAYSAGE.md](https://github.com/warith-harchaoui/video-helper/blob/main/PAYSAGE.md) · 🇬🇧 English

Related and competing Python libraries in the "manipulate video files"
space, benchmarked against `video-helper`. Ratings are ⭐ (1) to
⭐⭐⭐⭐⭐ (5), scored on `video-helper`'s intended job — everyday video
handling for AI pipelines (validate, convert, chunk, concat, overlay,
extract-frames, extract-audio, mux-audio, burn subtitles, subtitle
format conversion, image-loop). A library optimised for a very
different job (e.g. real-time inference, non-linear editing) is not
penalised — the score just reflects fit to *this* niche.

## At a glance

| Video Parsing | Multi-format I/O | Convert / scale-and-pad | Chunk / concat / overlay | Frame extraction | Subtitles | GPU decode | Multi-destination | Light install |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **video-helper** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| moviepy | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| PyAV | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| decord | ⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐ |
| torchvision.io | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐ |
| VidGear | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| OpenCV | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| ffmpeg-python | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐⭐⭐⭐ |
| imageio | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| scenedetect | ⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |

## Positioning map

2D representation of the table above.

![Positioning map](https://raw.githubusercontent.com/warith-harchaoui/video-helper/main/assets/landscape.png)

The map is a 2-D summary of the eight criteria, so read it as a shape, not a scoreboard. `video-helper` is at the top-right corner. The axes read **Horizontal — Versatile ↔ Adaptable** and **Vertical — Lightweight ↔ Efficient**.

## Positioning

`video-helper` deliberately sits at the intersection of
**moviepy-level ergonomics** (one-line convert / chunk / concat /
overlay / burn subs) and **AI-pipeline needs** (multi-backend frame
extraction dispatcher, hwaccel, torch destination on demand, HTTP
headers passthrough for yt-dlp-resolved streams). It intentionally
does *not* try to compete with `PyAV` on the low-level packet API or
`torchvision.io` on native torch tensors, and it keeps `torch` and
`PIL` **optional** — you only pay their install cost if you actually
call `destination="torch"` / `destination="pil"`. That trade-off is the
main differentiator against `torchvision.io` (torch mandatory) and
against `decord` (ffmpeg4 source build required).

Where the ratings come from, in a sentence each: multi-format I/O
leans on ffmpeg-native probing and muxing; frame extraction is a
dispatcher over VidGear / PyAV / ffmpeg-pipe with sparse, windowed and
streaming modes and a keyframe seek; subtitles cover libass burn-in
plus SRT→VTT conversion with CSS; GPU decode is auto hwaccel
(VideoToolbox / NVDEC) through PyAV / ffmpeg-pipe; and multi-destination
returns numpy by default with torch and PIL available on request.

## When to pick what

- **`video-helper`** — video prep for AI pipelines: batch convert +
  scale-fit-and-pad to a fixed model input, sparse / windowed frame
  sampling with hwaccel, subtitle burn-in, audio mux for narration,
  concat for stitched training clips, HTTP headers passthrough for
  yt-dlp-resolved streams.
- **`moviepy`** — timeline-style scripting (place-and-cut clip graphs),
  compositing several clips into one, quick title cards. Not ideal for
  batch throughput.
- **`PyAV`** — you need packet-level control (custom codec settings,
  keyframe placement, seek precision).
- **`decord` / `torchvision.io`** — pure random-access frame reads
  straight into torch tensors, with a training loop that dominates
  total cost (dataloader-heavy workflow).
- **`VidGear`** — you need OpenCV+FFmpeg helpers with the built-in
  stabilizer and don't care about sparse access.
- **`OpenCV`** — quick prototyping, no batch throughput target, no
  subtitle needs.
- **`ffmpeg-python`** — you want to compose an arbitrary filter graph
  and don't need numpy interop.
- **`scenedetect`** — you specifically need shot-boundary detection.
