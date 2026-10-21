"""
Video Helper — minimal single-page GUI ("video bench").

This module holds nothing but the self-contained HTML document served by the
FastAPI app at ``GET /gui`` (see :mod:`video_helper.api`). It is deliberately
build-step-free: one string of HTML + Tailwind (via CDN) + vanilla ES-module
JavaScript. There is no bundler, no framework, no npm: the whole page is a
static asset the API returns verbatim.

Where the words live
--------------------
In the markup, in English. Each one is wrapped as ``{{_("…")}}`` in the HTML,
or listed in :data:`_JS_NAME_TO_SOURCE` for the script, and
:class:`os_helper.Catalog` translates it through the compiled ``gettext``
catalogues under ``locales/`` (``CODING.md`` 21.3).

English is the msgid, so it needs no catalogue and cannot fall out of sync
with one; a string the French catalogue has not caught up with renders as
readable English instead of as a key. The cost is the mirror image: rewording
the English here orphans its French entry, and gettext would quietly serve the
English. That is what ``tests/test_gui_i18n.py`` exists to catch — it hands
every source string in this module to :meth:`os_helper.Catalog.problems`, so
an orphaned translation is a red build rather than a half-reverted page.

The per-operation parameter labels stay out of the catalogue on purpose, and
the locale file says why: each one names the form field the request actually
carries, so the wire's own spelling is what makes a field checkable against
the API documentation.

:func:`render_gui` resolves a language and returns the finished page.

Why a separate module
---------------------
Keeping the (long) HTML out of :mod:`video_helper.api` keeps the route
definitions readable and lets the AI Helpers suite share one GUI template:
swap the operation list and the per-operation form fields, keep the plumbing.

What the page does
------------------
- Drop / pick a local video (kept entirely client-side until "Run").
- Choose one operation (validate / dimensions / duration / convert / chunk /
  black / compress / image-loop / concat / overlay / extract-audio /
  mux-audio / burn-subs / srt2vtt / extract-frames / extract-flow).
- Reveal only the fields (and any extra file inputs) that operation needs.
- POST a ``multipart/form-data`` request to the SAME FastAPI endpoints the
  CLI surface uses: the GUI adds zero new server logic.
- Preview the input and the output side by side: a ``<video>`` player for
  clips, an ``<img>`` for the odd still, a JSON dump for the read-only
  probes, and a download link for everything (single file, or a ``.zip`` for
  the multi-file ``extract-frames`` / ``srt2vtt`` operations).

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import functools
import html
import json
import re
from pathlib import Path

import os_helper as osh

# Inside the package, not beside it: a directory one level up is not package
# data and does not travel in the wheel. best-engine shipped exactly that bug —
# `pip install` gave a package whose every GUI string raised FileNotFoundError.
_LOCALES_DIR = Path(__file__).resolve().parent / "locales"

#: The gettext domain, and therefore each ``.mo`` file's stem.
_DOMAIN = "video_helper"

#: The language served when the request names one we cannot render.
_DEFAULT_LANGUAGE = "fr"


@functools.lru_cache(maxsize=1)
def _catalog() -> osh.Catalog:
    """Resolve the catalogue directory once, through the suite's shared loader."""
    return osh.Catalog.from_package(_LOCALES_DIR, _DOMAIN, default_language=_DEFAULT_LANGUAGE)


def supported_languages() -> tuple[str, ...]:
    """Language codes the GUI can render: English plus every compiled catalogue."""
    return _catalog().languages


def default_language() -> str:
    """The language an unknown or absent ``?lang=`` falls back to."""
    return _catalog().default_language


# The language toggle is computed, not translated. Its three parts all mean
# "the other language", which is data rather than copy: a msgid of
# ``/gui?lang=fr`` whose translation is ``/gui?lang=en`` would be nonsense, and
# `Catalog.problems` would rightly treat it as prose that had drifted.
#
#: Flag shown for a language — the flag of that language, not of the page.
_FLAGS: dict[str, str] = {"fr": "🇫🇷", "en": "🇬🇧"}

#: How each language names itself. Deliberately NOT translated: a French page
#: offering English says "English version" in English, which is what a reader
#: scanning for their own language actually looks for.
_ENDONYMS: dict[str, str] = {"fr": "Version française", "en": "English version"}


# The inline script's strings. The JS names are the contract between this
# module and the script below; the English beside each one is the msgid, so
# the script's copy lives in the same place as the markup's and is checked
# by the same test. Injected as JSON, which is the one encoding an
# apostrophe cannot break out of — and French copy is full of them.
_JS_NAME_TO_SOURCE: dict[str, str] = {
    "needInput": "Pick an input file first.",
    "overlayNeedsImage": "overlay needs an image file.",
    "muxNeedsAudio": "mux-audio needs an audio file.",
    "burnSubsNeedsSubs": "burn-subs needs a subtitles file.",
    "running": "Running…",
    "errorPrefix": "Error ",
    "done": "Done.",
    "zipNote": "Multiple files bundled as a .zip.",
    "npyNote": "Raw flow array (.npy) — download only, no inline preview.",
    "requestFailed": "Request failed: {error}",
}


#: One ``{{_("…")}}`` site in the template. Non-greedy and newline-free, so a
#: run of them on one line stays separate and an unterminated one is left
#: alone rather than swallowing the rest of the page.
_SOURCE_RE = re.compile(r'\{\{_\("(.*?)"\)\}\}')


# One template, every language. Human-facing text is tokenised as {{TOKEN}}
# (HTML) or read from the injected `T` object (JavaScript); `render_gui` fills
# both. Tailwind is pulled from a CDN so there is no build step; the JavaScript
# is a single inline ES module talking to the existing API.
_GUI_TEMPLATE: str = r"""<!doctype html>
<html lang="{{LANG}}" class="h-full">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{{_("Video Helper — Video Bench")}}</title>
  <!-- Tailwind via CDN: keeps the page a single self-contained file, no build. -->
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    /* Respect users who ask for reduced motion (accessibility baseline). */
    @media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
  </style>
</head>
<body class="h-full bg-slate-50 text-slate-900 antialiased">
  <div class="mx-auto max-w-3xl px-4 py-8">
    <header class="mb-6">
      <!-- Language toggle: a flag that links to the other locale of this page. -->
      <a href="{{LANG_HREF}}" aria-label="{{LANG_ARIA}}"
         class="float-right text-xl hover:opacity-70">{{LANG_FLAG}}</a>
      <h1 class="text-2xl font-semibold tracking-tight">{{_("Video Helper — Video Bench")}}</h1>
      <p class="mt-1 text-sm text-slate-600">
        {{_("Drop a video, pick an operation, run it on the local API, then compare input vs output and download the result. Everything runs on your machine — nothing is uploaded to a third party.")}}
      </p>
    </header>

    <!-- 1) File input: drag-and-drop zone doubling as a file picker. -->
    <section class="mb-5">
      <label for="file" class="block text-sm font-medium mb-1">{{_("Input video file")}}</label>
      <div id="drop" tabindex="0"
           class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed
                  border-slate-300 bg-white px-4 py-8 text-center cursor-pointer
                  focus:outline-none focus:ring-2 focus:ring-blue-500 hover:border-blue-400">
        <p class="text-sm text-slate-500">{{_("Drop a file here, or click to choose")}}</p>
        <p id="filename" class="mt-2 text-sm font-medium text-slate-800"></p>
        <input id="file" type="file" accept="video/*,image/*" class="hidden" />
      </div>
      <p class="mt-1 text-xs text-slate-500">
        {{_("The black operation needs no input; image-loop expects a still image here.")}}
      </p>
    </section>

    <!-- 2) Operation selector. Changing it reveals only the relevant fields. -->
    <section class="mb-5">
      <label for="op" class="block text-sm font-medium mb-1">{{_("Operation")}}</label>
      <select id="op"
              class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="validate">{{_("validate — is this a valid video? (JSON)")}}</option>
        <option value="dimensions">{{_("dimensions — width / height / duration / fps (JSON)")}}</option>
        <option value="duration">{{_("duration — length in seconds (JSON)")}}</option>
        <option value="convert" selected>{{_("convert — re-encode / resize / drop audio")}}</option>
        <option value="chunk">{{_("chunk — extract a [start, end] slice")}}</option>
        <option value="black">{{_("black — synthesize a solid-black clip")}}</option>
        <option value="compress">{{_("compress — two-pass compress to a target file size")}}</option>
        <option value="image-loop">{{_("image-loop — loop a still image into a clip")}}</option>
        <option value="concat">{{_("concat — join multiple clips head-to-tail")}}</option>
        <option value="overlay">{{_("overlay — burn a still image onto the video")}}</option>
        <option value="extract-audio">{{_("extract-audio — dump the audio track")}}</option>
        <option value="mux-audio">{{_("mux-audio — attach an audio track")}}</option>
        <option value="burn-subs">{{_("burn-subs — burn subtitles into frames")}}</option>
        <option value="srt2vtt">{{_("srt2vtt — SRT → WebVTT + CSS (zip)")}}</option>
        <option value="extract-frames">{{_("extract-frames — PNG frames (zip)")}}</option>
        <option value="extract-flow">{{_("extract-flow — dense optical flow (mp4 viz or .npy)")}}</option>
      </select>
    </section>

    <!-- 3) Per-operation parameter fields. Shown/hidden by the data-ops list. -->
    <section id="params" class="mb-5 grid grid-cols-2 gap-3">
      <div data-ops="convert chunk black image-loop concat overlay mux-audio burn-subs">
        <label class="block text-xs font-medium mb-1">output_format</label>
        <input id="output_format" value="mp4"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="convert black image-loop">
        <label class="block text-xs font-medium mb-1">width</label>
        <input id="width" type="number" placeholder="{{_("(optional)")}}"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="convert black image-loop">
        <label class="block text-xs font-medium mb-1">height</label>
        <input id="height" type="number" placeholder="{{_("(optional)")}}"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="convert black image-loop concat">
        <label class="block text-xs font-medium mb-1">frame_rate</label>
        <input id="frame_rate" type="number" placeholder="{{_("(optional)")}}"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="convert">
        <label class="flex items-center gap-2 text-xs font-medium mb-1 mt-5">
          <input id="without_sound" type="checkbox" class="rounded border-slate-300" />
          without_sound
        </label>
      </div>
      <div data-ops="chunk">
        <label class="block text-xs font-medium mb-1">start (s)</label>
        <input id="start" type="number" step="0.01" value="0"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="chunk">
        <label class="block text-xs font-medium mb-1">end (s)</label>
        <input id="end" type="number" step="0.01" value="5"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="black image-loop">
        <label class="block text-xs font-medium mb-1">duration (s)</label>
        <input id="duration" type="number" step="0.1" value="3"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="overlay">
        <label class="block text-xs font-medium mb-1">x</label>
        <input id="x" value="0"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="overlay">
        <label class="block text-xs font-medium mb-1">y</label>
        <input id="y" value="0"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="extract-frames">
        <label class="block text-xs font-medium mb-1">frame_step</label>
        <input id="frame_step" type="number" value="30"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="extract-flow">
        <label class="block text-xs font-medium mb-1">method</label>
        <select id="flow_method" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="dis" selected>{{_("dis (fast, CPU, no extra install)")}}</option>
          <option value="farneback">{{_("farneback (CPU, no extra install)")}}</option>
          <option value="raft">{{_("raft (deep learning, needs the [flow] extra)")}}</option>
        </select>
      </div>
      <div data-ops="extract-flow">
        <label class="block text-xs font-medium mb-1">output_format</label>
        <select id="flow_output_format" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="video" selected>{{_("video — HSV-visualization mp4")}}</option>
          <option value="npy">{{_("npy — raw (T, H, W, 2) flow array")}}</option>
        </select>
      </div>
      <div data-ops="extract-flow">
        <label class="block text-xs font-medium mb-1">frame_step</label>
        <input id="flow_frame_step" type="number" value="1"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="extract-audio">
        <label class="block text-xs font-medium mb-1">{{_("audio format")}}</label>
        <input id="audio_format" value="wav"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="compress">
        <label class="block text-xs font-medium mb-1">target_size_mb</label>
        <input id="target_size_mb" type="number" step="0.1" value="97"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="compress">
        <label class="block text-xs font-medium mb-1">audio_bitrate</label>
        <input id="compress_audio_bitrate" value="128k"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="compress">
        <label class="block text-xs font-medium mb-1">vcodec</label>
        <select id="vcodec" class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm">
          <option value="libx265" selected>libx265 (HEVC)</option>
          <option value="libx264">libx264</option>
        </select>
      </div>
      <div data-ops="compress">
        <label class="block text-xs font-medium mb-1">min_video_bitrate_kbps</label>
        <input id="min_video_bitrate_kbps" type="number" value="200"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <!-- Secondary file inputs, revealed per operation. -->
      <div data-ops="concat" class="col-span-2">
        <label class="block text-xs font-medium mb-1">
          {{_("extra clip(s) — concat needs at least a second video")}}
        </label>
        <input id="extra" type="file" accept="video/*" multiple
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="overlay" class="col-span-2">
        <label class="block text-xs font-medium mb-1">{{_("image to overlay")}}</label>
        <input id="overlay_image" type="file" accept="image/*"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="mux-audio" class="col-span-2">
        <label class="block text-xs font-medium mb-1">{{_("audio track to attach")}}</label>
        <input id="mux_audio_file" type="file" accept="audio/*,video/*"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="burn-subs" class="col-span-2">
        <label class="block text-xs font-medium mb-1">{{_("subtitles (.srt / .vtt / .ass)")}}</label>
        <input id="subs_file" type="file" accept=".srt,.vtt,.ass,.ssa,text/plain"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
    </section>

    <!-- 4) Run button + status line. -->
    <section class="mb-6">
      <button id="run"
              class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white
                     hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500
                     disabled:opacity-50">
        {{_("Run")}}
      </button>
      <span id="status" class="ml-3 text-sm text-slate-600" role="status" aria-live="polite"></span>
    </section>

    <!-- 5) Players + result. Input on the left, output on the right. -->
    <section class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">{{_("Input")}}</h2>
        <video id="in-video" controls class="w-full rounded"></video>
        <img id="in-image" class="w-full rounded" hidden alt="{{_("input still")}}" />
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">{{_("Output")}}</h2>
        <video id="out-video" controls class="w-full rounded"></video>
        <img id="out-image" class="w-full rounded" hidden alt="{{_("output still")}}" />
        <audio id="out-audio" controls class="w-full" hidden></audio>
        <pre id="out-json" class="mt-2 overflow-auto rounded bg-slate-100 p-2 text-xs" hidden></pre>
        <div id="out-extra" class="mt-2 text-sm text-slate-600"></div>
        <a id="download" class="mt-2 inline-block text-sm font-medium text-blue-600 hover:underline"
           hidden download>{{_("Download result")}}</a>
      </div>
    </section>
  </div>

  <script type="module">
    // Every human-readable string the script writes comes from the locale
    // file, injected as JSON — the one encoding an apostrophe cannot break
    // out of, and French copy is full of them.
    const T = {{T_JSON}};

    // --- tiny DOM helpers -------------------------------------------------
    const $ = (id) => document.getElementById(id);
    const status = (msg) => { $("status").textContent = msg; };

    // Currently-selected primary input file (kept client-side until Run).
    let inputFile = null;

    // --- file picker + drag-and-drop -------------------------------------
    const drop = $("drop");
    const fileInput = $("file");
    // Clicking the drop zone opens the native picker.
    drop.addEventListener("click", () => fileInput.click());
    drop.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); fileInput.click(); }
    });
    // Highlight while dragging over the zone.
    drop.addEventListener("dragover", (e) => { e.preventDefault(); drop.classList.add("border-blue-500"); });
    drop.addEventListener("dragleave", () => drop.classList.remove("border-blue-500"));
    drop.addEventListener("drop", (e) => {
      e.preventDefault();
      drop.classList.remove("border-blue-500");
      if (e.dataTransfer.files.length) setInput(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener("change", () => { if (fileInput.files.length) setInput(fileInput.files[0]); });

    // Register a chosen file: show its name and load it into the input preview.
    // Images (for image-loop) go to the <img>; everything else to the <video>.
    function setInput(f) {
      inputFile = f;
      $("filename").textContent = f.name;
      const url = URL.createObjectURL(f);
      if (f.type.startsWith("image/")) {
        $("in-image").src = url; $("in-image").hidden = false;
        $("in-video").removeAttribute("src"); $("in-video").hidden = true;
      } else {
        $("in-video").src = url; $("in-video").hidden = false;
        $("in-image").removeAttribute("src"); $("in-image").hidden = true;
      }
    }

    // --- operation -> visible fields -------------------------------------
    const opSelect = $("op");
    // Show only the parameter blocks whose data-ops list contains the op.
    function syncParams() {
      const op = opSelect.value;
      for (const el of document.querySelectorAll("#params [data-ops]")) {
        el.hidden = !el.dataset.ops.split(" ").includes(op);
      }
    }
    opSelect.addEventListener("change", syncParams);
    syncParams();

    // Endpoint path per op (a few differ from the raw op name).
    const URL_FOR = {
      "validate": "/validate", "dimensions": "/dimensions", "duration": "/duration",
      "convert": "/convert", "chunk": "/chunk", "black": "/black", "compress": "/compress",
      "image-loop": "/image-loop", "concat": "/concat", "overlay": "/overlay",
      "extract-audio": "/extract-audio", "mux-audio": "/mux-audio",
      "burn-subs": "/burn-subs", "srt2vtt": "/srt2vtt", "extract-frames": "/extract-frames",
      "extract-flow": "/extract-flow",
    };
    // Operations whose response is a ZIP (multiple files) — download only.
    const ZIP_OPS = new Set(["srt2vtt", "extract-frames"]);
    // Operations that return JSON, not a media file.
    const JSON_OPS = new Set(["validate", "dimensions", "duration"]);
    // Operations that need no primary input (generated from parameters only).
    const NO_INPUT_OPS = new Set(["black"]);
    // Operations whose media output is audio, not video.
    const AUDIO_OPS = new Set(["extract-audio"]);

    // Optional-number helper: only append a field when the user filled it.
    function appendIf(fd, key, id) {
      const v = $(id).value;
      if (v !== "" && v !== null && v !== undefined) fd.append(key, v);
    }

    // Hide every output surface before rendering a fresh result.
    function resetOutput() {
      for (const id of ["out-video", "out-image", "out-audio", "out-json"]) {
        $(id).hidden = true; $(id).removeAttribute("src");
      }
      $("out-json").textContent = "";
      $("out-extra").textContent = "";
      $("download").hidden = true;
    }

    // --- run: build the multipart request per operation ------------------
    $("run").addEventListener("click", async () => {
      const op = opSelect.value;
      const fd = new FormData();
      if (!NO_INPUT_OPS.has(op) && !inputFile) { status(T.needInput); return; }

      const url = URL_FOR[op];
      if (op === "validate" || op === "dimensions" || op === "duration") {
        fd.append("file", inputFile);
      } else if (op === "convert") {
        fd.append("file", inputFile);
        fd.append("output_format", $("output_format").value);
        appendIf(fd, "frame_rate", "frame_rate");
        appendIf(fd, "width", "width");
        appendIf(fd, "height", "height");
        fd.append("without_sound", $("without_sound").checked ? "true" : "false");
      } else if (op === "chunk") {
        fd.append("file", inputFile);
        fd.append("start", $("start").value);
        fd.append("end", $("end").value);
        fd.append("output_format", $("output_format").value);
      } else if (op === "black") {
        fd.append("duration", $("duration").value);
        fd.append("width", $("width").value || "1280");
        fd.append("height", $("height").value || "720");
        appendIf(fd, "frame_rate", "frame_rate");
        fd.append("output_format", $("output_format").value);
      } else if (op === "compress") {
        fd.append("file", inputFile);
        fd.append("target_size_mb", $("target_size_mb").value || "97");
        fd.append("audio_bitrate", $("compress_audio_bitrate").value || "128k");
        fd.append("vcodec", $("vcodec").value);
        fd.append("min_video_bitrate_kbps", $("min_video_bitrate_kbps").value || "200");
      } else if (op === "image-loop") {
        fd.append("image", inputFile);
        fd.append("duration", $("duration").value);
        appendIf(fd, "frame_rate", "frame_rate");
        appendIf(fd, "width", "width");
        appendIf(fd, "height", "height");
        fd.append("output_format", $("output_format").value);
      } else if (op === "concat") {
        // concat needs >= 2 files: the primary plus every extra selected.
        fd.append("files", inputFile);
        for (const f of $("extra").files) fd.append("files", f);
        appendIf(fd, "frame_rate", "frame_rate");
        fd.append("output_format", $("output_format").value);
      } else if (op === "overlay") {
        const img = $("overlay_image").files[0];
        if (!img) { status(T.overlayNeedsImage); return; }
        fd.append("file", inputFile);
        fd.append("image", img);
        fd.append("x", $("x").value);
        fd.append("y", $("y").value);
        fd.append("output_format", $("output_format").value);
      } else if (op === "extract-audio") {
        fd.append("file", inputFile);
        fd.append("output_format", $("audio_format").value);
      } else if (op === "mux-audio") {
        const a = $("mux_audio_file").files[0];
        if (!a) { status(T.muxNeedsAudio); return; }
        fd.append("file", inputFile);
        fd.append("audio", a);
        fd.append("output_format", $("output_format").value);
      } else if (op === "burn-subs") {
        const s = $("subs_file").files[0];
        if (!s) { status(T.burnSubsNeedsSubs); return; }
        fd.append("file", inputFile);
        fd.append("subs", s);
        fd.append("output_format", $("output_format").value);
      } else if (op === "srt2vtt") {
        fd.append("file", inputFile);
      } else if (op === "extract-frames") {
        fd.append("file", inputFile);
        fd.append("frame_step", $("frame_step").value);
      } else if (op === "extract-flow") {
        fd.append("file", inputFile);
        fd.append("method", $("flow_method").value);
        fd.append("output_format", $("flow_output_format").value);
        appendIf(fd, "frame_step", "flow_frame_step");
      }

      // Fire the request and render the response by response type.
      status(T.running);
      $("run").disabled = true;
      resetOutput();
      try {
        const res = await fetch(url, { method: "POST", body: fd });
        if (!res.ok) {
          const txt = await res.text();
          status(T.errorPrefix + res.status + ": " + txt.slice(0, 200));
          return;
        }
        if (JSON_OPS.has(op)) {
          const j = await res.json();
          $("out-json").textContent = JSON.stringify(j, null, 2);
          $("out-json").hidden = false;
          status(T.done);
          return;
        }
        // Binary response (media file or zip): wrap in an object URL.
        const blob = await res.blob();
        const objUrl = URL.createObjectURL(blob);
        const dl = $("download");
        dl.href = objUrl;
        if (ZIP_OPS.has(op)) {
          // Multi-file output: no inline player, just a zip download.
          dl.download = op + ".zip";
          $("out-extra").textContent = T.zipNote;
        } else if (AUDIO_OPS.has(op)) {
          dl.download = "output." + ($("audio_format").value || "wav");
          $("out-audio").src = objUrl; $("out-audio").hidden = false;
        } else if (op === "compress") {
          dl.download = "compressed.mp4";
          $("out-video").src = objUrl; $("out-video").hidden = false;
        } else if (op === "extract-flow" && $("flow_output_format").value === "npy") {
          // Raw array output: no inline player, download-only (like the zip ops).
          dl.download = "flow.npy";
          $("out-extra").textContent = T.npyNote;
        } else if (op === "extract-flow") {
          dl.download = "flow.mp4";
          $("out-video").src = objUrl; $("out-video").hidden = false;
        } else {
          // Single video file: play it inline and offer the download.
          dl.download = "output." + ($("output_format").value || "mp4");
          $("out-video").src = objUrl; $("out-video").hidden = false;
        }
        dl.hidden = false;
        status(T.done);
      } catch (err) {
        status(T.requestFailed.replace("{error}", err));
      } finally {
        $("run").disabled = false;
      }
    });
  </script>
</body>
</html>
"""


def render_gui(lang: str = "") -> str:
    """Render the single-page GUI in the requested language.

    Parameters
    ----------
    lang : str
        Two-letter language code. Anything without a compiled catalogue —
        including the empty string — falls back to :data:`_DEFAULT_LANGUAGE`,
        so an unknown ``?lang=`` never 500s.

    Returns
    -------
    str
        The complete HTML document for that language.

    Examples
    --------
    >>> "<!doctype html>" in render_gui("en")
    True
    >>> render_gui("tlh") == render_gui(default_language())
    True
    """
    cat = _catalog()
    resolved = cat.resolve(lang)
    translate = cat.translator_for(resolved).gettext

    # The other language, for the toggle. With two languages this is "the one
    # that is not current"; with more it is the next one round, which keeps the
    # flag a cycle rather than a dead end.
    languages = cat.languages
    other = languages[(languages.index(resolved) + 1) % len(languages)]

    def _render_source(match: re.Match[str]) -> str:
        """Translate one ``{{_("…")}}`` site and escape it for HTML.

        Escaping is not optional: these land in attributes (placeholder, alt,
        aria, title) as readily as in text nodes, and a French apostrophe in an
        attribute would close it early.
        """
        return html.escape(translate(match.group(1)), quote=True)

    page = _SOURCE_RE.sub(_render_source, _GUI_TEMPLATE)
    page = page.replace("{{LANG}}", html.escape(resolved, quote=True))
    page = page.replace("{{LANG_HREF}}", html.escape(f"/gui?lang={other}", quote=True))
    page = page.replace("{{LANG_FLAG}}", _FLAGS.get(other, other.upper()))
    page = page.replace("{{LANG_ARIA}}", html.escape(_ENDONYMS.get(other, other), quote=True))

    # The script's strings go in as JSON rather than as substituted text: it is
    # the encoding that cannot be broken out of by an apostrophe, and French
    # copy is full of them.
    table = {name: translate(source) for name, source in _JS_NAME_TO_SOURCE.items()}
    return page.replace("{{T_JSON}}", json.dumps(table, ensure_ascii=False))


def __getattr__(name: str) -> str:
    """Serve ``GUI_HTML`` on first access rather than building it at import.

    The module-level constant used to BE the page, and importers still reach
    for it. Assigning it eagerly would read and parse the locale file on every
    import of this module, including in callers that never serve the GUI — and
    a module-level ``__getattr__`` only fires for names that are NOT otherwise
    defined, so the name is deliberately left unbound rather than set to a
    placeholder.
    """
    if name == "GUI_HTML":
        return render_gui()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
