# video-helper CLI reference

Two CLIs over the same operations. `video-helper` (argparse) ships with the
core package; `video-helper-click` (needs `[cli]`) is the click twin. Flags
match between them.

## Probing

```bash
video-helper validate IN            # ext + ffprobe; prints true/false
video-helper dimensions IN          # width, height, fps
video-helper duration IN            # seconds, as a float
```

`validate` and `dimensions` also accept an `http(s)://` URL.

## Re-encoding and resizing

```bash
video-helper convert IN OUT [--width W] [--height H] [--fps N] [--no-audio]
```
Container and codec follow `OUT`'s extension. Give **one** of `--width` /
`--height` to scale while preserving aspect ratio.

## Cutting, compressing, synthesizing

```bash
video-helper chunk IN OUT --start SECONDS --end SECONDS
video-helper compress IN OUT --target-size-mb MB
video-helper black OUT --duration SECONDS [--width W] [--height H] [--fps N]
video-helper image-loop IMAGE OUT --duration SECONDS [--fps N]
```

`compress` is **two-pass and size-targeted**: it computes the bitrate that
lands under the requested file size rather than making you guess one.

## Assembling

```bash
video-helper concat OUT IN1 IN2 [IN3 …]
video-helper overlay IN OUT --image LOGO.png [--position top-left|top-right|bottom-left|bottom-right] [--margin PX]
```

Clips with mismatched resolutions or frame rates are normalised before the
join.

## Audio tracks

```bash
video-helper extract-audio IN OUT.wav
video-helper mux-audio IN AUDIO OUT        # replace / attach the audio track
```

To *transform* the extracted audio (resample, mono, trim), hand it to
`audio-helper` — that is the division of labour in the suite.

## Subtitles

```bash
video-helper burn-subs IN OUT --subtitles FILE.srt [--font-size N]
video-helper srt2vtt IN.srt OUT.vtt [--css OUT.css]
```

`burn-subs` renders the text into the pixels (irreversible, needed where
players strip tracks). `srt2vtt` keeps them selectable — prefer it for the web.

## Frames and optical flow

```bash
video-helper extract-frames IN OUTDIR [--fps N] [--start S] [--end E]
video-helper extract-flow IN OUT [--method dis|farneback|raft]
```

Frame extraction has several backends and the dispatcher picks one from the
access pattern: PyAV (needs `[pyav]`) for windowed-sequential and sparse
reads, VidGear or an ffmpeg pipe otherwise. See the repo's `SPEED_ANALYSIS.md`
for the measurements behind that choice.

In the library, `extract_frames` is a **generator** of BGR uint8 arrays —
nothing accumulates in RAM — with `destination="torch"` (needs `[torch]`,
NCHW/CTHW on cpu/mps/cuda) and `destination="pil"` (needs `[pil]`) as
alternatives. `dump_frames` writes images to disk instead.

`extract-flow` methods: `dis` and `farneback` are OpenCV (no extra), `raft` is
the deep-learning one and needs `[flow]`.

## Output contract

- Every command prints the path(s) it wrote, one per line.
- Probes print bare values (`true`/`false`, `W H FPS`, a float).
- Failures are logged through `os_helper` and exit non-zero; partial output
  files are removed rather than left behind.
