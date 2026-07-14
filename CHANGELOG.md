# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
