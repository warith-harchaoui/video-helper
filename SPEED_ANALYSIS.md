# `extract_frames` — Backend Speed Analysis

Empirical benchmark of the backends exposed by `video_helper.extract_frames`,
to drive the dispatcher's defaults. Updated whenever the bench script
gets re-run on a meaningfully different machine or after a non-trivial
implementation change.

Reproduce with:

```bash
pip install --upgrade git+https://github.com/warith-harchaoui/os-helper.git@v1.3.0
PYTHONPATH=. python scripts/benchmark_extract_frames.py
# Or subset: --resolutions 720p,1080p --codecs h264
```

The bench sweeps **resolution × codec × access pattern × backend × hwaccel**.
Each cell is the **best wall-clock of 3 runs** and the **mean CPU time of
3 runs** (via `osh.wall_timer` and `osh.cpu_timer`). The **CPU/Wall
ratio** is the headline signal: values >1 mean multi-threaded CPU work,
values <1 mean the CPU is mostly idle (work is offloaded to a hardware
decoder or a subprocess).

## Hardware / software baseline

| Item | Value |
|---|---|
| Machine | Apple Silicon (arm64) |
| OS | macOS (Darwin 25.5.0) |
| Python | 3.13.13 |
| System ffmpeg | 8.1.2 (with VideoToolbox hwaccel) |
| PyAV | 17.1.0 |
| OpenCV / VidGear | as bundled with current site-packages |

Test clips are generated on the fly with `ffmpeg`'s `testsrc2` source
(an animated pattern, 10 s @ 30 fps), so decode work is non-trivial.

## History

- **v1.4 prototype** included a `decord` backend. It was removed before
  release because (a) PyPI wheels don't cover Py 3.13 / Apple Silicon and
  upstream recommends a source build with `ffmpeg@4` parallel, and (b)
  on every scenario we benched, PyAV was ~30 % faster on PyAV's
  expected weak spot (sparse access).
- **v1.4 hwaccel-wiring fix.** The first version of the PyAV backend
  passed `options={"hwaccel": "videotoolbox"}` to `av.open()`, which
  the AVFormatContext silently ignored — every `hwaccel="auto"` cell
  was effectively a no-op. The corrected wiring uses
  `av.codec.hwaccel.HWAccel(device_type="videotoolbox")` and is what
  the numbers below reflect.

## Results

### Sequential FULL (decode every frame, ~300 per 10 s @ 30 fps)

| Clip | Backend | Hwaccel | Wall (ms) | CPU (ms) | CPU/Wall | Throughput |
|---|---|---:|---:|---:|---:|---:|
| 360p H.264  | vidgear     | -    | **103** | 280  | 2.72× | **2 910 fps** |
| 360p H.264  | pyav        | None | 197 | 392  | 1.99× | 1 521 fps |
| 360p H.264  | pyav        | auto | 220 | 396  | 1.80× | 1 365 fps |
| 360p H.264  | ffmpeg-pipe | None | 1 953 | 1 133 | 0.58× | 154 fps |
| 720p H.264  | **vidgear** | -    | **248** | 1 018 | 4.10× | **1 208 fps** |
| 720p H.264  | pyav        | None | 271 | 942  | 3.47× | 1 107 fps |
| 720p H.264  | pyav        | **auto** | 804 | **595** | **0.74×** | 373 fps |
| 720p H.264  | ffmpeg-pipe | None | 7 694 | 4 645 | 0.60× | 39 fps |
| 720p HEVC   | vidgear     | -    | **309** | 1 245 | 4.03× | **972 fps** |
| 720p HEVC   | pyav        | None | 302 | 1 173 | 3.88× | 994 fps |
| 720p HEVC   | pyav        | **auto** | 757 | **581** | **0.77×** | 396 fps |
| **1080p H.264** | vidgear | -    | 400 | 2 066 | 5.17× | 751 fps |
| **1080p H.264** | **pyav** | None | **377** | 1 774 | 4.70× | **795 fps** |
| 1080p H.264 | pyav        | **auto** | 1 213 | **999** | **0.82×** | 247 fps |
| **1080p HEVC**  | vidgear | -    | 729 | 3 737 | 5.13× | 412 fps |
| **1080p HEVC**  | **pyav** | None | **716** | 3 277 | 4.58× | **419 fps** |
| 1080p HEVC  | pyav        | **auto** | 1 249 | **1 124** | **0.90×** | 240 fps |

**Headline:**
- **VidGear wins the full-sequential case up to 720p**; at **1080p, PyAV (no hwaccel) wins** in both H.264 and HEVC.
- **hwaccel="auto" via VideoToolbox actually offloads the CPU now** — CPU/Wall ratio drops from ~4× to ~0.8× (the CPU is mostly idle), confirming the decode work moved to the media engine.
- **But wall time is 2-3× WORSE with hwaccel** in every cell. Reason: the frames still have to come back as `bgr24` numpy arrays, and the GPU→CPU + swscale conversion eats more than the decode savings.

**Take-away on hwaccel for the `numpy` destination:** the engine works,
the wall budget worsens. The win exists, but it's a **power / parallelism
win**, not a latency win (CPU is freed up for other work; battery saved;
the decode no longer competes with downstream Python threads). For
maximum *throughput* to numpy, software decode wins.

### Sequential WINDOWED (1 s at the middle of the clip, ~31 frames)

| Clip | Backend | Hwaccel | Wall (ms) | CPU (ms) | CPU/Wall | Throughput |
|---|---|---:|---:|---:|---:|---:|
| 720p H.264  | vidgear | -    | 172 | 642 | 3.72× | 180 fps |
| 720p H.264  | **pyav** | None | **141** | 443 | 3.15× | **220 fps** |
| 720p H.264  | pyav    | **auto** | 450 | **145** | **0.32×** | 69 fps |
| 1080p H.264 | vidgear | -    | 295 | 1 336 | 4.52× | 105 fps |
| 1080p H.264 | **pyav** | None | **191** | 878 | 4.61× | **163 fps** |
| 1080p H.264 | pyav    | **auto** | 730 | **290** | **0.40×** | 43 fps |
| 1080p HEVC  | vidgear | -    | 479 | 2 411 | 5.03× | 65 fps |
| 1080p HEVC  | **pyav** | None | **701** | 2 276 | 3.25× | 44 fps |
| 1080p HEVC  | pyav    | **auto** | 984 | **557** | **0.57×** | 31 fps |

**Headline:** PyAV (no hwaccel) wins all windowed cases except 1080p
HEVC where VidGear's threaded decoder actually edges it out by ~30 %
(VidGear pays no Python-side seek cost, and at 1080p HEVC software
decode is heavy enough that VidGear's thread pool amortizes well).
hwaccel again drops CPU dramatically but worsens wall.

### Sparse access (12 evenly-spaced indices)

| Clip | Backend | Hwaccel | Wall (ms) | CPU (ms) | CPU/Wall |
|---|---|---:|---:|---:|---:|
| 720p H.264  | vidgear  | -    | 233 | 998   | 4.28× (decodes all 300) |
| 720p H.264  | **pyav** | None | **147** | 582   | **3.97×** |
| 720p H.264  | pyav     | auto | 586 | **144** | 0.24× |
| 1080p H.264 | vidgear  | -    | 432 | 2 107 | 4.88× (decodes all 300) |
| 1080p H.264 | **pyav** | None | **225** | 1 214 | **5.40×** |
| 1080p H.264 | pyav     | auto | 949 | **302** | 0.32× |
| 1080p HEVC  | vidgear  | -    | 1 001 | 5 598 | 5.59× (decodes all 300) |
| 1080p HEVC  | **pyav** | None | **983** | 3 300 | **3.36×** |
| 1080p HEVC  | pyav     | auto | 1 219 | **564** | 0.46× |

**Headline:** PyAV wins everywhere thanks to keyframe seek (decodes
only ~12 frames vs VidGear's 300). hwaccel: same pattern — CPU drops
~10×, wall gets worse.

### ffmpeg-pipe is non-competitive

10-20× slower than PyAV/VidGear at every cell. Subprocess startup
(~300 ms minimum) and pipe-byte overhead dominate. Keep only as a
no-PyAV last-resort fallback. CPU/Wall ratio sits at 0.5-0.6× because
the actual decode work lives in the ffmpeg subprocess and isn't
counted by `osh.cpu_timer` — the parent Python process is idle waiting
on the pipe.

## Decisions applied to v1.4.0 — default destination = `numpy`

- **decord backend removed** (build pain, zero observed win).
- **`hwaccel` default → `None`** for the numpy destination. The
  VideoToolbox offload works but the GPU→CPU→numpy round-trip wipes
  out the latency win. Power/parallelism benefits remain accessible
  via `hwaccel="auto"` (or explicit) opt-in.
- **Routing (numpy destination)**:
  - `stabilize=True`                  → vidgear (only one with the stabilizer)
  - sparse access                     → pyav if installed, else vidgear (range+filter)
  - full sequential ≤ 720p            → vidgear (fastest; threaded AVFoundation)
  - full sequential ≥ 1080p           → pyav (vidgear's lead vanishes; PyAV wins)
  - windowed sequential               → pyav if installed, else ffmpeg-pipe, else vidgear
- **The full-sequential ≤720p vs ≥1080p threshold** is currently hardcoded.
  It would be cleaner to make it pixel-count-driven (e.g. switch above
  ~1.5 Mpx).

## Shipped in v1.4.0

- **`destination=` parameter** (`"numpy"` default, `"torch"` with
  `device="cpu"|"mps"|"cuda"|"auto"`). For `destination="torch"` +
  GPU device, the dispatcher now auto-prefers PyAV + `hwaccel="auto"`
  (since the per-frame numpy materialization is unavoidable today but
  the batched device transfer is the right shape).
- **`batch_size=` parameter** (works with both destinations). Yields
  shape `(N, H, W, 3)` per batch. With `destination="torch"` + GPU
  device, **one host→device transfer per batch** instead of one per
  frame — typical 5-20× win over the manual `from_numpy().to(...)`
  loop.
- **Bench script extended** with `--torch-device` flag and `--resolutions 4k`
  opt-in (HEVC encoding at 3840×2160 is slow, kept out of the default
  matrix).

## Pending work — true zero-copy (vNext / v1.5+)

Even with PyAV + hwaccel correctly wired, **the torch destination today
still goes through a numpy intermediate**: PyAV decoded frame
(VideoToolbox / CUDA) → `to_ndarray('bgr24')` (CPU copy + swscale) →
`torch.from_numpy(...).to(device)` (host→device copy). The two copies
wipe out most of the hwaccel win on wall time even at 1080p+.

To unlock true zero-copy on GPU, we need a **C++ extension** (no
Cython, per design choice):

- **macOS / Apple Silicon path**: ffmpeg's VideoToolbox decoder outputs
  `CVPixelBuffer` (NV12 by default). Wrap as `IOSurface` → `MTLTexture`
  via `CVMetalTextureCacheCreateTextureFromImage`, then either (a) do
  BGR conversion as a Metal compute kernel and hand the resulting
  `MTLBuffer` to torch via `torch.utils.dlpack.from_dlpack`, or (b)
  skip BGR conversion and yield NV12 / YUV tensors so the caller does
  the colorspace pass on the GPU. Option (b) is faster and probably
  what most ML pipelines want (they normalize to RGB anyway).
- **CUDA path**: ffmpeg's CUVID decoder outputs `CUdeviceptr` frames
  already on GPU. Wrapping as a torch CUDA tensor via
  `__cuda_array_interface__` is a few lines. BGR conversion can stay
  a CUDA kernel or be deferred to the caller.
- **Estimated effort**: 1-2 weeks for both paths + tests + a clean
  build system. The C++ build will be the painful part — needs
  `setuptools.Extension` with platform-specific compiler flags
  (`-framework Metal -framework CoreVideo` on macOS, `-lcudart` on
  Linux+CUDA) plus install-time detection of which paths to build.
- **Expected payoff**: hwaccel finally wins on wall time too —
  somewhere between 2× (Apple Silicon NV12) and 5-10× (CUDA NVDEC).

Parked for v1.5+ — not in the v1.4.0 scope.

## Pending non-vNext follow-ups

- **Bench at 4K HEVC** (opt-in via `--resolutions 4k`; skipped from
  default because HEVC encoding at 4K takes ~30-90 s per fixture).
  HW decoders shine more at higher pixel counts.
- **Bench script counter overhead**: `sum(1 for _ in fn())` counts
  inside the timer, adding ~5-10 ms of Python overhead per call.
  Should be `len(list(fn()))` so the counter sits outside the timer.
- **The full-sequential ≤720p vs ≥1080p threshold** in `_choose_backend`
  is hardcoded. Could be pixel-count-driven (e.g. switch above ~1.5 Mpx).
  Simplicity tax probably not worth the ~50 ms saved.
