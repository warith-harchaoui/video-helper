# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
