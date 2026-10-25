# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.8.0] - 2026-10-25

### Changed

- **One command line, built with click; the argparse CLI is gone.** The
  package shipped two CLIs over the same sixteen operations — `video-helper`
  (argparse, 1109 lines) and `video-helper-click` (click, 691 lines) — and a
  flag naming the parsing library describes the implementation, not the
  interface. `video_helper/cli_click.py` is now `video_helper/cli.py`,
  `video_helper/cli_argparse.py` is deleted, and the single console script
  `video-helper` points at it. `video-helper-mcp` is untouched: it starts
  another surface, it is not a command line.

  `click` moves out of the `[cli]` extra into the core `dependencies`, and
  the `[cli]` extra is deleted — the CLI is no longer optional, so its
  dependency cannot be either. The `os-helper` cap widens from `<3` to `<4`
  (os-helper 3.0.0 drops its own CLI the same way).

  **Parity was measured, not assumed.** Before the argparse module was
  deleted, a script walked its subparsers and click's command table and
  compared them flag by flag: 16 subcommands on each side, no flag present on
  one side only, and no default differing except click's `Sentinel.UNSET`
  standing where argparse writes `None` for a `required=True` option. The
  tests that existed twice (once per CLI) collapsed onto the surviving one;
  the assertions that existed *only* on the argparse side — the parsed values
  for `compress`, `extract-flow` and `extract-frames`, not just their help
  text and defaults — were ported rather than dropped, through click's
  `Command.make_context`, which runs the parser and stops before the
  callback.

### Fixed

- **`concat --inputs a.mp4 b.mp4 c.mp4` would have concatenated one clip, not
  three.** The two CLIs agreed on the flag *name* and disagreed on its
  arity: argparse declared `--inputs` with `nargs="+"`, click with
  `multiple=True` (one `--inputs` per file). A flag-name comparison cannot see
  this, and the failure is the bad kind — no error, just a shorter output file
  than asked for. Since the surviving command is named `video-helper`, the
  argparse spelling is the one users already have in their shell history and
  in this module's own usage examples, so `concat` now accepts both: the files
  listed after a single `--inputs` are picked up by a trailing catch-all
  argument (click has no `nargs=-1` for options) and stitched back in order.
  Mixing the two spellings is refused with a usage error instead of silently
  reordered, because click reports the two halves with no record of how they
  interleaved. Covered by a test that asserts the resulting *order*, and
  proven by breaking the merge and watching it go red.

- **`--version` named a command that no longer exists.** The click group
  passed `prog_name="video-helper-click"`, so the surviving CLI would have
  introduced itself under the deleted name. It now prints `video-helper`, and
  answers to `-V` as well as `--version` (`-v` is left free: it reads as
  "verbose" to everyone). The version still comes from the installed
  distribution metadata, since this package exposes no `__version__` — so an
  editable checkout reports whatever was last `pip install`ed.

- **The group's help text described an architecture that is gone.** It read
  "click twin of the argparse CLI. Same subcommands."; it now says what the
  tool does. In the same pass, `chunk --help` stopped printing literal RST
  backticks (click renders a command docstring verbatim), and the dead
  `try: import click / except ImportError: install the [cli] extra` guard was
  removed.

- **The agent skill's CLI reference documented a command line that never
  existed.** `skills/video-helper/references/cli-reference.md` showed
  positional arguments (`video-helper convert IN OUT`) and the flags `--fps`,
  `--no-audio`, `--position`, `--margin`, `--subtitles` and `--font-size`.
  Not one of those is real: every operation takes long flags, and the real
  names are `--input` / `--output`, `--frame-rate`, `--without-sound`,
  `--x` / `--y` / `--scale-width`, `--subs` and `--force-style`. An agent
  following that page would have failed on its first call. Rewritten against
  the actual `-h` output of all sixteen subcommands, output contract included
  (`dimensions` emits JSON, not `W H FPS`). `requirements.txt`, which listed
  no `click` at all, now carries it among the core runtime deps.

### Migration

- `video-helper-click <cmd>` → `video-helper <cmd>`. Every subcommand, flag
  and default is unchanged, so only the program name moves.
- `pip install "video-helper[cli]"` now fails on an unknown extra. Drop the
  extra: `pip install video-helper` installs the CLI and `click` with it.
- `pip install -e ".[cli]"` → `pip install -e .`.

## [2.7.0] - 2026-10-21

### Changed

- **The GUI's strings moved from `locales/i18n.yaml` to a `gettext`
  catalogue.** The English is now the source, written in the markup itself as
  `{{_("…")}}`; the French lives in
  `video_helper/locales/fr/LC_MESSAGES/video_helper.po`, read through the new
  `os_helper.Catalog` (os-helper 2.6.0). One mechanism for the whole suite,
  and a translator now works in the format every translation tool already
  speaks, on real sentences rather than on key names.

  What this buys: a string the French catalogue has not caught up with renders
  as **readable English** instead of as a key like `RUN_BUTTON`. What it costs:
  rewording the English orphans its French entry, and gettext would quietly
  serve the English — so `tests/test_gui_i18n.py` now hands every source
  string to `Catalog.problems`, which names both halves of that fault. Proven
  by doing it: rewording the Run button turned the suite red before this
  shipped.

  The language toggle is no longer translated. Its three parts all mean "the
  other language", which is data rather than copy — a msgid of `/gui?lang=fr`
  translating to `/gui?lang=en` would be nonsense — so they are computed from
  the resolved language instead, and covered by their own test.

### Fixed

- **The compiled catalogue would never have shipped.** The stock Python
  `.gitignore` this repository inherited carries a blanket `*.mo`, where a
  `.mo` is a build artifact. Here it is the file the GUI reads at run time:
  left ignored it would have been absent from the repository, therefore from
  the sdist, therefore from the wheel, and **every string would have rendered
  as English on an installed copy** while looking perfect locally, where the
  file sits on disk either way. Negated for this package's own catalogues, and
  held by a "tracked by git" test — the same bug this suite already shipped
  twice, reached by a third route.

## [2.6.1] - 2026-10-21

### Changed

- **`POST /concat` renames `reencode` to `no_reencode`, and the old name is
  now a 400.** FastAPI **0.147.0** (2026-10-19) changed how omitted boolean
  form fields resolve: they are read as `False` "matching unchecked HTML
  checkboxes", explicitly "including required fields and fields with defaults
  of `True` or `None`" (PR #16523).

  `reencode` was declared `bool = Form(True)`. Every client that left it out
  — including **this package's own GUI**, whose concat panel posts no such
  field and relied on the server default — silently switched to stream-copy
  concatenation. That is the mode that only works when every input already
  shares a codec, profile and timebase; for anything else ffmpeg emits a file
  that plays wrong or not at all. The HTTP surface was quietly producing
  broken video.

  Declaring the field `bool | None = Form(None)` does not escape it — the
  upstream note names that case too. An off-by-default flag is the only shape
  the new semantics cannot invert, so the wire field is now `no_reencode`,
  which also matches the CLI's existing `--reencode/--no-reencode` pair.
  Omitting it still means "re-encode", as documented.

  Sending the retired `reencode` is a **400** naming the replacement, rather
  than being ignored: FastAPI drops unknown form fields, so a client asking
  for `reencode=false` would otherwise have been silently re-encoded instead
  — the opposite of its request.

  MINOR rather than MAJOR deliberately: `concat_videos(..., reencode=)` in
  the Python API is untouched and no default behaviour is reversed; the change
  restores the documented default upstream had inverted. Only HTTP callers
  that named the flag explicitly are affected, and they get a loud error.

## [2.6.0] - 2026-10-21

### Added

- **The video-bench GUI speaks French and English.** Every string it shows now
  comes from `video_helper/locales/i18n.yaml` through `os_helper.Locales`, the
  loader shared across the suite (CODING.md 21.3), instead of being written
  into the markup. `GET /gui?lang=fr|en` picks the language; anything the file
  does not carry — including a mistyped code and the empty default — falls
  back to the declared default locale, so a bad `?lang=` returns a page rather
  than a 500. A flag in the header toggles between the two.

  The template is tokenised (`{{TOKEN}}` in HTML, a `T` object for the
  script), so one piece of markup serves both languages and a translator never
  opens a Python file. The script's strings are injected as JSON rather than
  substituted as text: it is the encoding an apostrophe cannot break out of,
  and French copy is full of them. All sixteen operation descriptions, the
  three optical-flow methods and the two flow output formats are translated;
  the operation names themselves are the API's own and stay.

  `GUI_HTML` still resolves, via a module-level `__getattr__` that renders on
  access — importers that predate this keep working, and the locale file is
  not read by callers that never serve the GUI.

  **The parameter labels stay out of the catalogue on purpose**: `width`,
  `height`, `frame_rate`, `method`, `vcodec`, `target_size_mb` and the rest
  each name the form field the request actually carries, so the wire's own
  spelling is what makes a field checkable against the API documentation.
  `audio format` was the one exception — the field it fills is
  `output_format`, so that label is a description rather than a wire name, and
  it is translated.

  One deliberate simplification: the input hint lost the `<code>` wrappers
  around `black` and `image-loop`. Keeping them would have cut one sentence
  into three fragments, which a translator cannot reorder — the exact failure
  localisation exists to prevent.

### Changed

- **The declared `os-helper` floor rises to 2.4.0**, the version that
  introduced `Locales`. It was `>=2.0.0`, which the GUI can no longer honour:
  a user installing against os-helper 2.0.x would get an `AttributeError` out
  of the `/gui` route. Nothing would have caught it — pip resolves the newest
  os-helper, never the floor. `tests/test_gui_i18n.py` now asserts the floor
  against the feature it needs.

### Fixed

- **A GUI test asserted the default language rather than the page's
  identity.** It looked for the literal `"video bench"`, which is no longer
  what a French default renders. It now asks the locale file what the page is
  called.

### Notes

- The locale file lives **inside** the package, is declared in
  `package-data` (a table this project did not have), and is carved out of
  this repository's blanket `*.yaml` ignore rule — the third member of the
  suite to carry that rule and the third to need the carve-out. Three tests
  hold those three properties; verified the way the sibling defect was found,
  by opening the built wheel and finding the file inside it.

## [2.5.0] - 2026-10-19

### Fixed

- **Reading a remote URL could hang forever.** ffmpeg applies no I/O timeout
  unless asked, so a connection the remote has half-closed is simply waited on:
  the process sits at 0 % CPU holding a socket that will never deliver another
  byte, and only a kill ends it.

  This module is built to read exactly the URLs that behave that way —
  `video_dimensions`, `extract_frames` and the frame-extraction backends all
  accept yt-dlp-resolved `googlevideo.com` links and forward `http_headers` to
  ffmpeg. None of the three network entry points was bounded:

  - `video_dimensions`'s `ffmpeg.probe` call,
  - `_extract_via_ffmpeg_pipe`'s `ffmpeg` subprocess,
  - `_extract_via_pyav`'s `av.open`, whose options go straight to libavformat.

  All three now pass `rw_timeout` (60 s, `VIDEO_HELPER_RW_TIMEOUT` in seconds to
  change it, `0` to opt out). It is a protocol option, so on the CLI path it is
  placed ahead of `-i`. Local paths are untouched: a file on disk cannot stall
  on a socket.

  Found by auditing the suite, where the same root cause had already been fixed
  in `youtube-helper`, `youtube-helper-rs` and `podcast-helper`. A caveat worth
  carrying from that work: `rw_timeout` removes the common case but is not a
  guarantee — a `podcast-helper` run stalled for over four hours with the option
  set. Anything that *must* finish still needs a bound it owns, outside the
  process.

## [2.4.1] - 2026-09-03

### Fixed

- `faces.digest._write_manifest` now writes the `<output>.manifest.json`
  sidecar atomically (temp file + `os.replace`) instead of `open(path, "w")`
  directly — a reader (including a later, separate-process call to
  `load_manifest`) could previously observe a truncated file if the writer
  was killed mid-write.
- **`video_converter` and `compress_video`'s hardware-encode paths now
  serialize across processes, not just threads.** `_HW_ENCODE_SEM` was an
  in-process `threading.Semaphore`, which does nothing when an ffmpeg batch
  spans several separate OS processes (an ingest orchestrator plus one
  subprocess per build) each independently requesting a VideoToolbox
  session. Colliding hardware requests fall back to software passes that
  each spawn `_MAX_THREADS` of their own, oversubscribing the machine
  (observed: load average past 100 on a 12-core box with just two such
  processes active). Replaced with `_ffmpeg_serialize()`, an `flock`-based
  lock file (`VIDEO_HELPER_FFMPEG_LOCK`) held across the hardware attempt
  and its software fallback, in both `video_converter` and
  `compress_video`'s report encode (which previously held no lock at all).

## [2.4.0] - 2026-08-24

### Added

- **Hardware VideoToolbox encode path on macOS** for `video_converter`'s
  cross-container transcode and `compress_video` (new `vcodec=
  "hevc_videotoolbox"` option), a large speed win over the software x264/
  x265 passes on a long source (minutes instead of tens of minutes),
  at a small, acceptable quality-per-bit cost for a web-embedded video —
  not recommended for an archival master. New public `hw_vcodec(software,
  hardware)` probes `ffmpeg -encoders` and returns the hardware codec only
  when the running ffmpeg build actually lists it, falling back to
  *software* on any probe failure, a non-Darwin platform, or an unlisted
  encoder. Both hardware paths retry once on the software codec if the
  encode itself fails (VideoToolbox has a small, machine-dependent cap on
  concurrent hardware sessions).
- **`VIDEO_HELPER_MAX_THREADS`** (default 4): caps ffmpeg's own thread pool
  on the heavy encode paths — ffmpeg's default (0 = auto) claims every core
  it can see, fine for one isolated process but oversubscribes badly under
  concurrent batch conversions.
- **`VIDEO_HELPER_MAX_HW_SESSIONS`** (default 1): an in-process semaphore
  serializing concurrent VideoToolbox hardware encode attempts — several
  threads requesting a hardware session at once can collide and error out,
  each falling back to a software pass that then monopolizes its thread for
  20-30x longer, which is what actually starves a batch job, not the
  collision itself. Does not coordinate across separate OS processes.

### Fixed

- **`compress_video`'s hardware-encode failure path could silently return a
  broken file when called with `overwrite=False`.** On a VideoToolbox
  failure it recurses into itself with `vcodec="libx265"` to retry in
  software — but ffmpeg creates/truncates the output file as part of muxer
  setup before the encode loop runs, so a failed hardware pass can leave a
  partial, invalid file on disk. The recursive call's own
  `if not overwrite and file_exists(output_video)` early-return then saw
  that leftover file and handed it straight back, never running the
  software fallback at all. Now removes the partial output file before
  recursing.

## [2.3.3] - 2026-08-21

### Fixed

- **`faces/sampling.py`**: shot detection called PySceneDetect's deprecated
  `FrameTimecode.get_seconds()`; switched to the `.seconds` property it was
  deprecated in favor of. No behavior change, just silences the warning.
- **`_extract_via_pyav`'s hwaccel fallback**: caught `av.error.ValueError`,
  an attribute that does not exist on PyAV's error module (it roots its
  hierarchy at `FFmpegError`, not the stdlib exception names). Any real
  hwaccel init/open failure raised `AttributeError` from inside the `except`
  clause itself instead of triggering the intended software-decode fallback,
  crashing harder than doing nothing. Now catches `av.error.FFmpegError`.
- **`/extract-frames` and `/extract-flow` API routes**: spooling the upload,
  creating the frames directory, and zipping the result all ran outside the
  `_cleanup_on_error` guard that every other action route uses; a failure at
  any of those steps (not just inside the extraction call) leaked the whole
  temp dir, including the spooled upload, on disk. Both routes now wrap their
  full body in `_cleanup_on_error`, matching the pattern already used
  elsewhere in `api.py`.

## [2.3.2] - 2026-08-17

### Fixed

- **`dump_frames`**: silently swapped red and blue on every frame it wrote —
  an internal `RGB2BGR` conversion treated the input as RGB while every other
  part of video-helper (including `extract_frames`, which `dump_frames` is
  documented as the inverse of) uses BGR uint8. `dump_frames` now writes
  frames as-is, matching its documented contract and the OpenCV convention
  used throughout the library. `extract_optical_flow`'s `.mp4` visualization
  output (the only in-repo caller of `dump_frames`) is updated to match
  (`_flow_to_bgr`, was `_flow_to_rgb`) so its rendered colors are unaffected.
- **`[faces]` extra**: dropped the dead `onnxruntime` dependency — nothing in
  `video_helper.faces` ever imported it. YuNet detection and SFace
  recognition load their `.onnx` weight files through OpenCV's own bundled
  DNN wrappers (`cv2.FaceDetectorYN`, `cv2.FaceRecognizerSF`), and the
  accurate ASD engine (`LightASD`) runs entirely in PyTorch. Also fixed
  docstrings in `faces/__init__.py`, `faces/asd.py`, and
  `scripts/seed_model_mirror.py` that incorrectly claimed the ASD engine ran
  "through ONNX Runtime" (it never did) and that the seeding script should
  produce a `light_asd.onnx` file (the runtime looks for `light_asd.pth`).
- **`compress` CLI/API surfaces**: `compress_video`'s `vcodec="copy"` remux
  escape hatch (no re-encode) was a real, working library feature but
  unreachable from either CLI — both `--vcodec` choices lists only allowed
  `libx265`/`libx264`. The FastAPI `/compress` route accepted `copy` but
  silently accepted *any* string, forwarding invalid values straight to
  ffmpeg instead of a clean 400. Added `"copy"` to both CLI choice lists,
  added the same 400 validation `/extract-flow` already had for
  `output_format`, and documented `vcodec="copy"` in `compress_video`'s
  docstring and the README/LISEZMOI reference tables.
- **`extract-flow` API surface**: `method`, `dis_preset`, and `raft_variant`
  were unconstrained on `POST /extract-flow` (plain `str = Form(...)`)
  though both CLIs already restrict them via `choices=`. Bad values still
  failed correctly (the library itself validates and raises `ValueError`,
  mapped to a 400), but with a generic wrapped message and no OpenAPI enum
  documented for the field. Added the same explicit `if x not in (...):
  raise HTTPException(400, ...)` pattern already used for `output_format`
  and `compress`'s `vcodec`, for a clean, schema-visible error on all three
  fields.
- **`/concat` API route**: clobbered spooled uploads that shared the same
  extension. `_spool()` always wrote to a fixed `upload<ext>` path;
  `concat()` called it once per file then renamed, so a later file with the
  same extension overwrote an earlier one on disk before its own rename
  ever ran. Each upload now writes directly to its position-derived name,
  matching the pattern `/overlay` and `/mux-audio` already use for their
  second upload.
- **`active_speaker_map`'s docstring contradicted its own return contract**:
  it claimed uncertain clusters (margin *and* coverage below threshold) are
  omitted, but the finalize step only ever re-checks coverage; a cluster
  with a lower margin but sufficient coverage is intentionally still
  returned, with its real margin exposed as a caller-facing certainty
  signal rather than an internal filter. Docstring now states the actual,
  intentional behavior; the code was already correct.

### Documentation

- Glossed dense optical flow for a first-time reader in `README.md` /
  `LISEZMOI.md` and `flow.py`'s module docstring; punctuation-dash cleanup
  across the docs and every touched module's opening docstring.

## [2.3.1] - 2026-08-15

### Fixed

- **Packaging**: `pyproject.toml`'s `description` (PyPI `summary` metadata)
  exceeded PyPI's 512-character limit, which rejected the upload outright.
  Trimmed to the same content, more concisely worded.

## [2.3.0] - 2026-08-15

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
