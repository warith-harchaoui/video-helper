# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **`iter_frame_optical_flow`**: optional generator that wraps any `(H, W, 3)` BGR
  frame iterator — `extract_frames` output, or a live source such as
  `capture_helper.iter_camera_frames`, sharing the same contract — and
  re-yields `(H, W, 5)` float32 arrays (frame + `vx`/`vy` dense flow vs. the
  previous frame), or `(H, W, 3)` (grayscale intensity + flow) with the new
  `grayscale=True`. Three backends: `"dis"` (default) and `"farneback"` need
  no new dependency (opencv-python is already core); `"raft"` is a deep
  RAFT network via torchvision, gated behind the new `[flow]` extra.
- **`extract_optical_flow`**: file-level convenience wrapper (`extract_frames`
  → `iter_frame_optical_flow` → write) with full CLI/API/MCP parity, matching every
  other operation in the suite — `video-helper extract-flow` /
  `video-helper-click extract-flow`, `POST /extract-flow` (auto-published as
  an MCP tool via `fastapi-mcp`, no extra wiring needed). Output kind is
  inferred from the output path's extension: `.npy` (raw `(T, H, W, 2)`
  float32 flow array) or anything else (default `.mp4`, an HSV-color-wheel
  visualization video).
- **`resize_flow`**: resizes a dense-optical-flow field via wavelet
  decomposition (`PyWavelets`, part of the `[flow]` extra) instead of plain
  bilinear/bicubic interpolation, specifically to avoid smearing motion
  discontinuities across a resize, plus correctly rescaling flow *magnitude*
  by the same factor as the spatial resize (a common silent correctness bug
  in naive flow-resizing code). Wired into `iter_frame_optical_flow` and
  `extract_optical_flow` (and their CLI/API surfaces) as an optional
  `output_width`/`output_height` pair.

### Security

- **The HTTP API leaked a temp directory (including the uploaded video) on
  every failed request** to any of the 11 action routes (`/convert`,
  `/compress`, `/chunk`, `/black`, `/image-loop`, `/concat`, `/overlay`,
  `/extract-audio`, `/mux-audio`, `/burn-subs`, `/srt2vtt`): cleanup was
  only ever scheduled via `background.add_task(_cleanup, tmp)` on the
  success path, so a client sending deliberately-invalid input repeatedly
  could exhaust server disk — every failure left its whole temp dir behind
  forever. Fixed with a shared `_cleanup_on_error` context manager that
  reclaims the temp dir immediately on any exception, leaving the
  success-path background cleanup untouched.

### Fixed

- **CLI**: a library exception now prints one clean `Error: ...` line to
  stderr and exits 1, instead of a raw Python traceback, on both CLI
  twins. `video-helper-click`'s console-script entry point now points at a
  new `cli_click.main()` wrapper (was the bare `cli` group).
- **API**: every library exception collapsed into FastAPI's generic 500.
  `AssertionError`/`ValueError` (the library's own input-validation
  failures) now map to 400; anything else (`RuntimeError`, `ImportError`,
  an `ffmpeg.Error`) maps to 502.
- **Tests**: `test_compress_video_rejects_infeasible_target_size` asserted
  stale behavior — `compress_video` was intentionally changed to clamp to
  the floor bitrate with a warning instead of raising (see its own
  `min_video_bitrate_kbps` docstring), but the test still expected an
  `AssertionError`. Updated to assert the actual, intended behavior.

## [2.2.0] - 2026-08-13

### Added

- **`compress_video`**: two-pass ffmpeg encode that solves for the video
  bitrate needed to hit a target file size (HEVC/`libx265` by default,
  tagged `hvc1` for QuickTime/Apple compatibility, `+faststart`). Ships
  with full CLI (`video-helper compress` / `video-helper-click compress`),
  API (`POST /compress`), and GUI parity, matching every other operation
  in the suite.
- `extract_frames`'s `output_width` / `output_height` / `pad_color`
  parameters (previously library-only) are now also exposed on the CLI
  `extract-frames` subcommand and the `/extract-frames` API endpoint.

### Fixed

- PyAV decoder deadlock risk in `_extract_via_pyav`.
- `pad_color='transparent'` error message hardcoded a stale version string.

### Changed

- Added a conda `environment.yaml`; the Dockerfile now installs
  `requirements.txt` as its own cached layer.
- `requirements-dev.txt` is now derived from `pyproject.toml`'s `[dev]`
  extra instead of maintained by hand.

## [2.1.1] - 2026-08-09

### Fixed

- **`video_converter` failed on an extensionless output path** (ffmpeg
  cannot infer a muxer without one); now defaults the container to mp4.

## [2.1.0] - 2026-08-08

### Added

- **MCP surface** (`video_helper.mcp`, `[mcp]` extra, entry point
  `video-helper-mcp`): exposes the existing FastAPI app as MCP tools via
  `fastapi-mcp`, mirroring the pattern already shipped in `standpoint` /
  `vocal-helper` / `md2star` / `os-helper`. Closes the CLI/API/MCP surface
  gap for video-helper flagged in `ai-helpers/.private/do.md` §7.

## [2.0.1] - 2026-08-02

Documentation-only follow-up. The install commands now point at PyPI
(`pip install video-helper`) instead of a pinned git tag, so the rendered PyPI
project page never drifts to an old version.

### Fixed

- README / LISEZMOI / EXAMPLES install commands no longer self-pin to a git tag
  (`@v1.8.0`); they use `pip install video-helper` (and the `[extra]` forms),
  which always resolves to the latest published release.

### Added

- `tests/test_readme_install_pin.py` guards against the stale git self-pin ever
  returning to any Markdown file.

## [2.0.0] - 2026-08-02

### Added

- **GPU/MPS acceleration for Light-ASD.** Active-speaker detection now auto-selects
  a discrete NVIDIA **CUDA** GPU as well as Apple-Silicon **MPS** (was MPS-only),
  falling back to CPU. `NH_ASD_DEVICE=cpu|cuda|mps|auto` overrides; an explicit but
  unavailable backend warns and auto-selects. The CPU-demote-on-forward-error guard
  is unchanged.

### Changed

- **Working-resolution cap for the whole faces pipeline.** Extracted frames are now
  downscaled to a reasonable max height (default 720, `NH_FACES_MAX_HEIGHT` to
  override), preserving aspect ratio and never upscaling, before face detection and
  the ASD mouth-crop pipeline. A 4K recording no longer forces YuNet and Light-ASD
  to chew through needlessly large frames; decode memory and detection/ASD compute
  drop sharply. Detection, tracking, ASD, recognition and the emitted crops all
  share the same reduced, self-consistent coordinate space, so results stay correct.
- Adopt the os-helper 2.0.0 foundation: pin `os-helper>=2.0.0,<3`. The face-model
  mirror already downloads through `osh.download_file`, now on the resumable,
  atomic, integrity-checked 2.x primitive. Major bump because the shared foundation
  crossed a major boundary.
- README / LISEZMOI use absolute github.com / raw.githubusercontent URLs so they
  render on PyPI. CI trimmed to a super-light single-Python blocking gate.

### Fixed

- The 1.9.0 CI was red (vendored Light-ASD code + un-formatted sources + a
  torch-only test). Now green: `_lightasd/` (vendored upstream) is excluded from
  ruff lint/format, the first-party sources are formatted ruff-clean, and the ASD
  device test carries a `torch` `importorskip` so it skips in the light CI env and
  runs locally where the `[faces]` extra is installed.

## [1.9.0] - 2026-08-02

### Added

- **`video_helper.faces` — face-anchored speaker-identity primitives** (install
  with the `[faces]` extra: `onnxruntime` + `scenedetect`; `opencv-python` is
  already core). Reusable, HuggingFace-free, ONNX-portable CV building blocks:
  - `FaceDetector` — YuNet detection + 5 landmarks (`cv2.FaceDetectorYN`).
  - `FaceRecognizer` — SFace 128-d embeddings (`cv2.FaceRecognizerSF`).
  - `track_faces` — IoU/ByteTrack-family tracking into `FaceTrack`s (pure NumPy).
  - `mouth_roi` — lip-centred ROI for the ASD visual stream.
  - **Active Speaker Detection** — `get_engine` / `active_speaker_map`: the
    accurate **LightASD** engine runs the real Light-ASD net (CVPR 2023) in
    PyTorch with an exact `python_speech_features` MFCC front-end (no fragile
    ONNX export), with a weights-free lip-motion proxy fallback. Model weights
    (YuNet / SFace / `light_asd.pth`) are fetched on first use from the shared
    `ai-helpers` model mirror.
  - `get_engine` — an `ASDEngine`: a zero-weight lip-motion proxy (always
    available) or `LightASD` via ONNX Runtime.
  - `active_speaker_map` — the **smart-sampling harness**: PySceneDetect shots +
    speaker-turns + a cheap face census pick a small clip set, heavy ASD runs
    only there and grows until every speaker is covered with certainty.
  - `ensure_model` — sovereign model downloader: fetches from your own mirror
    (`AI_HELPERS_MODEL_BASE_URL`), falling back to OpenCV Zoo GitHub (Apache-2.0);
    never HuggingFace at runtime. `scripts/seed_model_mirror.py` seeds the mirror.

## [1.8.1] - 2026-08-01

### Removed

- **Agent skill dropped from the public repo.** Without an MCP surface,
  the Claude/OpenCode skill (`skills/`) no longer earns its keep as public
  distribution — moved to the gitignored `.private/skills/` (kept locally
  as reference, never published). `TRIGGERS.md` stays public; its
  skill-specific framing and dead `skills/` links are removed.

## [1.8.0] - 2026-08-01

### Removed

- **MCP surface dropped.** `fastapi-mcp`'s latest release (0.4.0) is
  incompatible with the latest `mcp` SDK (`Server.__init__()` signature
  mismatch), breaking CI with no available version pairing to pin around.
  Removed `video_helper/mcp.py`, the `video-helper-mcp` entry point, the
  `mcp` extra, and `fastapi-mcp` from `dev`. The library, both CLIs, the
  FastAPI HTTP surface, and the browser GUI are unaffected — video-helper
  now ships **four** surfaces instead of five. MINOR bump, matching how
  the `decord` backend removal was versioned in 1.4.0.

## [1.7.0] - 2026-07-20

### Added

- **Minimal browser GUI ("video bench")** served by the FastAPI app at
  `GET /gui`, with `GET /` redirecting to it. Drop a clip, pick one of
  the fourteen operations, run it against the existing HTTP endpoints,
  preview input vs output in an in-browser `<video>` / `<img>` /
  `<audio>` player (JSON for the read-only probes), and download the
  result (single file, or a `.zip` for `extract-frames` / `srt2vtt`).
  Self-contained page (Tailwind via CDN + vanilla JS, no build step) in
  the new `video_helper/gui.py` module.
- **Agent skill** (`skills/video-helper/`): a Claude Skill and OpenCode
  skill (`SKILL.md` + `references/{cli-reference,surfaces,triggers}.md`
  + `skills/README.md`) so an agent can discover and drive video-helper
  without a terminal.
- Repo-root **`TRIGGERS.md`** — exhaustive, auditable catalogue of the
  natural-language phrasings, commands, functions, and file types that
  should invoke each operation; referenced from README and LISEZMOI.
- **Local-first privacy badge** and a **The Promise / La promesse**
  section in README / LISEZMOI.

### Changed

- The FastAPI `version` field is now read from installed package
  metadata (`importlib.metadata`) instead of a hard-coded string, which
  had drifted to `1.6.2`; it now always matches `pyproject.toml`.
- README / LISEZMOI "Multi-surface exposure" now documents the shipped
  `/gui` bench (previously only referenced the GUI.md design roadmap).

### Notes

- Public library API is unchanged and fully backward-compatible — no
  function in `video_helper.__all__` was touched (youtube-helper's
  dependency on these names is unaffected). All changes are additive.

## [1.6.5] - 2026-07-15

### Documentation

- Harmonize README/LISEZMOI to the AI Helpers common structure (single
  H1, PyPI + source install paths, refreshed pins to v1.6.5); no code
  changes.

## [1.6.4] - 2026-07-14

### Fixed
- Replace references to the archived `yt-helper` project with
  `youtube-helper` (the extract-frames auth-headers hint and EXAMPLES.md).


## [1.6.3] - 2026-07-14

### Maintenance

- Apply the project coding standards across the package and `tests/`:
  Numpy-style docstrings on every function/class (including private and
  nested helpers), full type annotations with `from __future__ import
  annotations`, and comment density raised above the floor in every
  module. No public API or behavior changes.
- Route library logging through the os-helper logging surface
  (`osh.info/warning/error`) and adopt os-helper path/file utilities
  more widely; pin `os-helper>=1.5.0`.
- Refresh the project logo asset.


## [1.6.2] - 2026-07-08

### Documentation

- Cross-platform Install prerequisites (macOS / Ubuntu / Windows).

## [1.6.1] - 2026-07-07

## [1.5.2] - 2026-06-29

### Added

- `is_valid_video_file(url)` short-circuits to `True` for `http://` /
  `https://` URLs — the only way to validate a remote URL is to spend
  bandwidth fetching it, and ffmpeg surfaces a clear error downstream
  if the URL is bad. Lets yt-dlp-resolved direct URLs (e.g. from
  `youtube_helper.pick_video_stream`) pass through.
- `video_dimensions(...)` accepts a new optional `http_headers` kwarg.
  When the input is a URL, the headers are forwarded to `ffprobe` via
  `-headers` so authenticated streams (YouTube live, members-only,
  age-gated) probe correctly.
- `extract_frames(...)` now passes its `http_headers` argument through
  to the internal `video_dimensions(...)` probe so URL inputs no
  longer 403 on the metadata round-trip before decoding begins.

### Tests

- `tests/test_url_support.py` — 6 unit tests for the URL short-circuit
  and the new `http_headers` parameter. Network-free (the URL paths are
  exercised through behaviour assertions; no actual ffprobe call is
  made against the internet).

## [1.5.1] - 2026-06-29

### Changed

- Establish suite-wide Python coding-style mandate in `CONTRIBUTING.md`:
  numpy-style docstrings on every function and class, module-level
  docstring header (with usage example + author), full type annotations,
  generous explanatory comments.
- `EXAMPLES.md` cookbook present at the repo root and linked from
  README + LISEZMOI.
- `print(...)` in docs (EXAMPLES.md / README / LISEZMOI) is followed by
  a `#`-comment showing the expected output (doctest / REPL style);
  library `.py` code uses `osh.info` / `osh.warning` / `osh.error`
  instead of bare `print`.
- Every `brew install <pkg>` mention is paired with a brew.sh hint when
  not already obvious from context.
- `.gitignore` updated to drop accidental `*config.json` commits while
  keeping `*config.json.example` templates tracked.

## [1.5.1] - 2026-06-29

### Changed

- Convert `pyproject.toml` from `[tool.poetry]` to PEP 621 `[project]`;
  switch build-backend to `setuptools`.
- Drop `setup.py`, `requirements.txt`, `environment.yml`, `poetry.lock`.
- Expand `[project.optional-dependencies]`: `pyav` / `torch` / `pil`
  / `all` / `dev`.
- Add GitHub Actions CI.

## [1.5.0] - 2026-06-28

### Added

- `extract_frames(http_headers=...)`: pass arbitrary HTTP headers
  (User-Agent, Referer, Cookie, etc.) to PyAV / ffmpeg-pipe backends.
- `extract_frames(output_width=, output_height=, pad_color="black")`:
  exact output size with aspect-preserving padding (cv2.resize +
  cv2.copyMakeBorder). Named colors + `#RRGGBB`; transparent raises.

## [1.4.1] - 2026-06-28

### Added

- `destination="numpy" | "torch" | "pil"` conventions documented per
  framework (numpy=BGR HWC/NHWC; torch=RGB CHW/NCHW/CTHW; PIL size=W,H).
- `layout="image" | "video"` parameter for batched yields.

## [1.4.0] - 2026-06-28

### Added

- `extract_frames` multi-backend dispatcher: VidGear / PyAV /
  ffmpeg-pipe. Pattern detection (stabilize / sequential / random)
  → automatic backend choice.

### Removed

- `decord` backend after benchmarks showed it loses to PyAV (~30%)
  on its claimed sparse-access sweet spot.

## [1.3.0] - 2026-06-28

### Added

- Pipeline tests and `EXAMPLES.md`.

### Changed

- Docstring cleanup.

## [1.2.0] - 2026-06-27

Internal version bump.

## [1.1.0] - 2026-06-23

### Changed

- Bump `os-helper` pin to v1.1.0; add Python 3.13 support.

## [1.0.0] - 2026-05-22

First tagged release.
