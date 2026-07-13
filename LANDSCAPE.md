# LANDSCAPE

Related and competing Python libraries in the "manipulate video files"
space, benchmarked against `video-helper`. Ratings are `⭐️` (1) to
`⭐️⭐️⭐️⭐️⭐️` (5), scored on `video-helper`'s intended job — everyday video
handling for AI pipelines (validate, convert, chunk, concat, overlay,
extract-frames, extract-audio, mux-audio, burn subtitles, subtitle
format conversion, image-loop). A library optimised for a very
different job (e.g. real-time inference, non-linear editing) is not
penalised — the score just reflects fit to *this* niche.

## At a glance

| Library / project | Multi-format I/O (ffmpeg-native) | Format conversion / scale-and-pad | Chunk / concat / overlay / image-loop | Frame extraction (sparse + windowed + streaming) | Subtitles (burn-in + srt2vtt) | GPU-accelerated decode (VideoToolbox / NVDEC) | Multi-destination (numpy / torch / PIL) | Light install (no torch by default) |
| --- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **video-helper** *(this project)* | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ (VidGear / PyAV / ffmpeg-pipe dispatcher) | ⭐️⭐️⭐️⭐️⭐️ (libass burn-in + SRT→VTT+CSS) | ⭐️⭐️⭐️⭐️ (auto hwaccel; PyAV / ffmpeg-pipe) | ⭐️⭐️⭐️⭐️⭐️ (numpy default, torch + PIL optional) | ⭐️⭐️⭐️⭐️⭐️ (torch optional) |
| moviepy | ⭐️⭐️⭐️⭐️ (ffmpeg-backed) | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️⭐️ (clip-graph model) | ⭐️⭐️⭐️ (sequential, no sparse index) | ⭐️⭐️⭐️ (TextClip / SubtitlesClip) | ⭐️ | ⭐️⭐️ (numpy only) | ⭐️⭐️⭐️⭐️ |
| PyAV | ⭐️⭐️⭐️⭐️⭐️ (libav bindings) | ⭐️⭐️⭐️ (encoder API) | ⭐️⭐️ (packet-level primitives) | ⭐️⭐️⭐️⭐️⭐️ (keyframe seek, hwaccel) | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ (numpy from `to_ndarray`) | ⭐️⭐️⭐️⭐️ |
| decord | ⭐️⭐️ (ffmpeg4 source build) | ⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️⭐️ (batched random access) | ⭐️ | ⭐️⭐️⭐️ (limited) | ⭐️⭐️⭐️⭐️ (numpy / torch tensors) | ⭐️⭐️ |
| torchvision.io | ⭐️⭐️⭐️ (video_reader backend) | ⭐️⭐️ | ⭐️ | ⭐️⭐️⭐️⭐️ (torch tensors direct) | ⭐️ | ⭐️⭐️ (needs torch build w/ hwaccel) | ⭐️⭐️⭐️⭐️⭐️ (torch tensors native) | ⭐️ (torch mandatory) |
| VidGear | ⭐️⭐️⭐️⭐️ (OpenCV + FFmpeg helpers) | ⭐️⭐️⭐️ | ⭐️⭐️⭐️ (streamgear pipelines) | ⭐️⭐️⭐️⭐️ (sequential, threaded, stabilizer) | ⭐️ | ⭐️⭐️ (limited) | ⭐️⭐️ (numpy only) | ⭐️⭐️⭐️⭐️ |
| OpenCV (`cv2.VideoCapture`) | ⭐️⭐️⭐️ | ⭐️⭐️⭐️ (VideoWriter) | ⭐️⭐️ | ⭐️⭐️⭐️ (sequential; `set(POS_FRAMES)` unreliable) | ⭐️ | ⭐️⭐️ (backend-dependent) | ⭐️⭐️ (numpy only) | ⭐️⭐️⭐️⭐️ |
| ffmpeg-python | ⭐️⭐️⭐️⭐️⭐️ (thin wrapper) | ⭐️⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️⭐️ (filter graph) | ⭐️⭐️⭐️ (subprocess pipe) | ⭐️⭐️⭐️ (subtitles filter) | ⭐️⭐️⭐️⭐️ (any hwaccel ffmpeg knows) | ⭐️ (no numpy glue) | ⭐️⭐️⭐️⭐️⭐️ |
| imageio / imageio-ffmpeg | ⭐️⭐️⭐️⭐️ | ⭐️⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️ (sequential) | ⭐️ | ⭐️ | ⭐️⭐️⭐️ (numpy default) | ⭐️⭐️⭐️⭐️⭐️ |
| scenedetect | ⭐️⭐️⭐️ | ⭐️ | ⭐️⭐️ (auto-cut) | ⭐️⭐️⭐️⭐️ (scene-boundary sampling) | ⭐️ | ⭐️⭐️ | ⭐️⭐️ | ⭐️⭐️⭐️⭐️ |

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
