# video-helper CLI reference

One command line, `video-helper`, installed with the core package. Every
operation is a subcommand and every argument is a long flag — `--input` /
`--output` / … — the same vocabulary the HTTP routes and the MCP tools use,
so a recipe translates between surfaces without renaming anything.

`video-helper -h` lists the subcommands; `video-helper <cmd> -h` lists a
subcommand's flags. `video-helper -V` prints the installed version.

**There are no positional arguments.** `video-helper convert in.mp4 out.mp4`
is a usage error; the flags are mandatory.

## Probing

```bash
video-helper validate   --input IN   # ext + ffprobe; prints true/false, exits 1 if false
video-helper dimensions --input IN   # JSON: width, height, duration, frame_rate, has_sound
video-helper duration   --input IN   # seconds, as a float
```

`validate` and `dimensions` also accept an `http(s)://` URL, and `dimensions`
forwards HTTP headers to ffprobe for the sources that need them:

```bash
video-helper dimensions --input "https://…/clip.mp4" --header "Referer: https://…"
```

Repeat `--header` once per header.

## Re-encoding and resizing

```bash
video-helper convert --input IN --output OUT \
    [--width W] [--height H] [--frame-rate N] [--without-sound]
```

Container and codec follow `--output`'s extension. Give **one** of `--width` /
`--height` to scale while preserving aspect ratio.

## Cutting, compressing, synthesizing

```bash
video-helper chunk      --input IN --output OUT --start SECONDS --end SECONDS
video-helper compress   --input IN [--output OUT] [--target-size-mb MB] \
                        [--vcodec libx265|libx264|copy] [--audio-bitrate 128k] \
                        [--min-video-bitrate-kbps 200] [--no-overwrite]
video-helper black      --duration SECONDS --width W --height H --output OUT [--frame-rate N]
video-helper image-loop --image IMAGE --duration SECONDS --output OUT \
                        [--frame-rate N] [--width W] [--height H]
```

`compress` is **two-pass and size-targeted**: it computes the bitrate that
lands under the requested file size (default 97 MB) rather than making you
guess one. `--output` is optional — it defaults to a sibling of the input.
`--vcodec copy` remuxes without re-encoding.

`black`'s `--width` / `--height` are required: there is no source to inherit a
resolution from.

## Assembling

```bash
video-helper concat  --inputs IN1 IN2 [IN3 …] --output OUT [--no-reencode] [--frame-rate N]
video-helper overlay --input IN --image LOGO.png --output OUT \
                     [--x X] [--y Y] [--scale-width W]
```

`--inputs` takes the clips in playback order; `--inputs a.mp4 --inputs b.mp4`
is the same thing one flag at a time. Do not mix the two spellings — the
command refuses an order it cannot reconstruct rather than guessing.

`--reencode` is the default and normalises mismatched resolutions, codecs and
frame rates before the join. `--no-reencode` stream-copies, which is faster but
only correct when every input already shares a codec, profile and timebase.

`overlay`'s `--x` / `--y` are strings, not just integers: an ffmpeg expression
such as `--x "main_w-overlay_w-10"` works, which is how a watermark gets pinned
to a corner regardless of resolution.

## Audio tracks

```bash
video-helper extract-audio --input IN --output OUT.wav \
                           [--sample-rate 44100] [--channels 2] [--encoding pcm_s16le]
video-helper mux-audio     --input IN --audio AUDIO --output OUT \
                           [--audio-codec aac] [--audio-bitrate 192k] [--shortest]
```

`mux-audio` replaces / attaches the audio track; `--shortest` ends the result
with whichever of the two inputs runs out first.

To *transform* the extracted audio (resample, mono, trim), hand it to
`audio-helper` — that is the division of labour in the suite.

## Subtitles

```bash
video-helper burn-subs --input IN --subs FILE.srt --output OUT [--force-style "…"]
video-helper srt2vtt   --input IN.srt [--output OUT.vtt] [--css OUT.css]
```

`burn-subs` renders the text into the pixels (irreversible, needed where
players strip tracks); `--force-style` takes an ASS style override, e.g.
`--force-style "FontSize=28,Outline=2"`. `srt2vtt` keeps the text selectable —
prefer it for the web — and defaults both outputs to siblings of the input.

## Frames and optical flow

```bash
video-helper extract-frames --input IN --output-dir OUTDIR \
                            [--frame-step N | --frame-interval SECONDS] \
                            [--start S] [--end E] \
                            [--backend auto|vidgear|pyav|ffmpeg-pipe] \
                            [--width W] [--height H] [--pad-color black|'#RRGGBB']
video-helper extract-flow   --input IN [--output OUT] [--method dis|farneback|raft] \
                            [--dis-preset ultrafast|fast|medium] [--frame-step N] \
                            [--start S] [--end E] [--fps N] [--clip-flow PX] \
                            [--output-width W --output-height H] [--no-overwrite]
```

Sampling is by stride (`--frame-step`, default 1) or by period
(`--frame-interval`, in seconds) — not both. `--width` / `--height` scale-fit
and pad with `--pad-color` when the target aspect ratio differs from the
source.

Frame extraction has several backends and `--backend auto` picks one from the
access pattern: PyAV (needs `[pyav]`) for windowed-sequential and sparse
reads, VidGear or an ffmpeg pipe otherwise. See the repo's `SPEED_ANALYSIS.md`
for the measurements behind that choice.

In the library, `extract_frames` is a **generator** of BGR uint8 arrays —
nothing accumulates in RAM — with `destination="torch"` (needs `[torch]`,
NCHW/CTHW on cpu/mps/cuda) and `destination="pil"` (needs `[pil]`) as
alternatives. `dump_frames` writes images to disk instead.

`extract-flow` writes an HSV-visualization video unless `--output` ends in
`.npy`, which writes the raw `(T, H, W, 2)` float32 array instead. Methods:
`dis` and `farneback` are OpenCV (no extra), `raft` is the deep-learning one
and needs `[flow]`, as does `--output-width` / `--output-height` resizing.

## Output contract

- Every command prints the path it wrote; `extract-frames` prints a JSON object
  with the list of paths and their count.
- Probes print bare values: `true` / `false` for `validate` (and exit 1 when
  false), a float for `duration`, a JSON object for `dimensions`.
- A library failure is logged through `os_helper`, printed as one `Error: …`
  line on stderr — never a traceback — and exits non-zero; partial output files
  are removed rather than left behind.
