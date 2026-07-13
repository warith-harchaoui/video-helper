# GUI — Video Helper

> A design plan, not a CLI mirror. The CLI already handles "one clip at
> a time, one operation at a time". A GUI must go further — otherwise
> why build one? This document lays out an ambitious, opinionated
> visual product for the video-prep-for-AI workflow.

## North star

> **A frame-accurate canvas where clips flow through named operations,
> side by side, and you can scrub every intermediate frame.**

Video work is inherently sequential (validate → chunk → concat → burn
subs → mux audio → …) but auditing the *effect* of each operation is
what the CLI cannot give you. The GUI's job is to make the **pipeline
visible, frame-accurate, and A/B-comparable** — not to reproduce ffmpeg
flags with checkboxes.

## Three surfaces, one product

### 1. Recipe Canvas *(primary surface)*

- Draggable node graph, left-to-right — nodes are the fourteen verbs
  (`validate`, `dimensions`, `duration`, `convert`, `chunk`, `black`,
  `image-loop`, `concat`, `overlay`, `extract-audio`, `mux-audio`,
  `burn-subs`, `srt2vtt`, `extract-frames`).
- Each node shows a **live 3-frame proxy strip of its output** (first
  frame, middle frame, last frame) updated on parameter change
  (debounced 300 ms). Waveform strip below when audio is present.
- Edges carry video *and metadata* (width × height, duration, framerate,
  has_sound). Downstream nodes highlight in red when an upstream change
  would invalidate them (e.g. changing dimensions under a fixed-size
  `overlay`).
- One toggle per node: **"Bypass"** — routes the input straight to the
  output. Makes A/B trivial: compare the graph with a node bypassed vs
  active.
- Right-click a node → **"Export snapshot as recipe.yaml"**. Recipes
  are shell-independent artifacts you can commit to a repo — CI replays
  them via the CLI.

### 2. Frame-first Comparator

Two horizontally aligned scrubbable video tracks that scrub together.
Every node with a "Compare against original" toggle sends the pre/post
frames here. Bindings:

- Space bar: toggle *before / after* on the same playhead position.
- `A / B` keys: 1-frame dial between two versions — the mixer-style
  workflow editors actually use.
- Difference channel: renders `abs(after - before)` at the bottom
  (grayscale heatmap). Massively helps tune convert scales, overlay
  positioning, subtitle rendering, chunk boundaries.
- Waveform lane locked to the same playhead — extract-audio and
  mux-audio become auditable at the sample level.

### 3. Batch Drop Zone

A single big rectangle. Drop any number of files → they enter the
canvas as a batch context. Every node processes the whole batch;
outputs sit in a **contact-sheet view** (thumbnail first-frame per clip,
sortable by any metadata column: duration, dimensions, has_sound,
frame_rate). Right-click → *"open in Recipe Canvas"* to trace back the
graph.

## Design principles

- **Nothing invisible.** Every operation shows its effect *on this
  frame*, not a symbolic parameter. That is the entire point of a GUI.
- **Time is a first-class citizen.** Everything scrubs. Playhead is a
  singleton across the app. Timecodes shown in `HH:MM:SS.fff` and in
  frame index — both formats are how editors actually think.
- **Files, not memory blobs.** The recipe engine writes intermediates
  to a project folder (opt-out). The CLI outputs and the GUI outputs
  are byte-identical — no "GUI produces different files".
- **Explain the backend.** For nodes that route through the frame
  extraction dispatcher: tooltip shows *why* PyAV / VidGear /
  ffmpeg-pipe was picked, and a link to `SPEED_ANALYSIS.md`. No mystery
  buttons.
- **Keyboard first, mouse second.** Every node action has a shortcut.
  The comparator's `A/B` toggle is inspired by mixing consoles, not
  Photoshop.
- **Colorblind-safe by construction.** All state uses shape + color +
  text, never color alone (see companion `front-colors` audit skill).

## What we deliberately don't do

- **No timeline editor.** DAWs and NLEs already exist (DaVinci
  Resolve, Premiere, Kdenlive). We are not competing with them. Cuts
  happen via `chunk` and `concat` nodes, visualized but not manipulated
  on a linear ruler.
- **No effects rack.** No color grading, no keyframed animations. Only
  the video-prep-for-AI verbs. Scope discipline.
- **No cloud lock-in.** Everything runs on the same local FastAPI
  server the container already ships. GUI is a thin JS client.

## Stack

- Front end: TypeScript + Svelte 5 + Vega-Lite (metadata plots) +
  `<video>` element with `requestVideoFrameCallback` for frame-accurate
  scrubbing. No React — matches the `front-ui` companion skill's stack.
- Back end: the FastAPI app already exists (`video_helper.api`) and
  covers 100 % of the operations. GUI is a client only.
- Recipe format: YAML, versioned, human-diffable.

## Milestones

| Milestone | What ships | Why first |
| --- | --- | --- |
| M0 | Recipe Canvas with 3 nodes: `validate`, `chunk`, `concat`. 3-frame proxy strip. | Prove the canvas metaphor before scaling verbs. |
| M1 | All 14 verbs. Frame-first comparator. | Feature parity with the CLI. |
| M2 | Batch Drop Zone + contact sheet. | Where the GUI passes the CLI in productivity. |
| M3 | Recipe export/import + node validation graph. | Reproducibility story for pipelines shared across a team. |
| M4 | Frame-embedding cluster view: drop 100 clips, sample N frames per clip, embed with a CLIP-class model, see them clustered, click a cluster to hear one representative. | The "we can only do this in a GUI" moment — dataset triage for video-model training. |

## Non-goals (recorded so we do not drift)

- Not a full NLE.
- Not a hosted SaaS.
- Not a substitute for the CLI in CI (recipes emit CLI-equivalent
  YAML that CI can replay headless).

## Success metric

> A user who owns 500 clips and needs to prep a training set for a
> video-understanding model does the whole job in one afternoon, in one
> window, and finishes with a committable `recipe.yaml`.

If we ship that, we win.
