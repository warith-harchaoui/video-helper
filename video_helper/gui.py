"""
Video Helper — minimal single-page GUI ("video bench").

This module holds nothing but the self-contained HTML document served by the
FastAPI app at ``GET /gui`` (see :mod:`video_helper.api`). It is deliberately
build-step-free: one string of HTML + Tailwind (via CDN) + vanilla ES-module
JavaScript. There is no bundler, no framework, no npm — the whole page is a
static asset the API returns verbatim.

Why a separate module
---------------------
Keeping the (long) HTML out of :mod:`video_helper.api` keeps the route
definitions readable and lets the AI Helpers suite share one GUI template:
swap the operation list and the per-operation form fields, keep the plumbing.

What the page does
------------------
- Drop / pick a local video (kept entirely client-side until "Run").
- Choose one operation (validate / dimensions / duration / convert / chunk /
  black / image-loop / concat / overlay / extract-audio / mux-audio /
  burn-subs / srt2vtt / extract-frames).
- Reveal only the fields (and any extra file inputs) that operation needs.
- POST a ``multipart/form-data`` request to the SAME FastAPI endpoints the
  CLI and MCP surfaces use — the GUI adds zero new server logic.
- Preview the input and the output side by side: a ``<video>`` player for
  clips, an ``<img>`` for the odd still, a JSON dump for the read-only
  probes, and a download link for everything (single file, or a ``.zip`` for
  the multi-file ``extract-frames`` / ``srt2vtt`` operations).

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

# The entire GUI is this one HTML string. It is returned as-is by the
# ``/gui`` route. Tailwind is pulled from a CDN so there is no build step;
# the JavaScript is a single inline ES module talking to the existing API.
GUI_HTML: str = r"""<!doctype html>
<html lang="en" class="h-full">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Video Helper — Video Bench</title>
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
      <h1 class="text-2xl font-semibold tracking-tight">Video Helper — Video Bench</h1>
      <p class="mt-1 text-sm text-slate-600">
        Drop a video, pick an operation, run it on the local API,
        then compare input vs output and download the result. Everything
        runs on your machine — nothing is uploaded to a third party.
      </p>
    </header>

    <!-- 1) File input: drag-and-drop zone doubling as a file picker. -->
    <section class="mb-5">
      <label for="file" class="block text-sm font-medium mb-1">Input video file</label>
      <div id="drop" tabindex="0"
           class="flex flex-col items-center justify-center rounded-xl border-2 border-dashed
                  border-slate-300 bg-white px-4 py-8 text-center cursor-pointer
                  focus:outline-none focus:ring-2 focus:ring-blue-500 hover:border-blue-400">
        <p class="text-sm text-slate-500">Drop a file here, or click to choose</p>
        <p id="filename" class="mt-2 text-sm font-medium text-slate-800"></p>
        <input id="file" type="file" accept="video/*,image/*" class="hidden" />
      </div>
      <p class="mt-1 text-xs text-slate-500">
        The <code>black</code> operation needs no input; <code>image-loop</code>
        expects a still image here.
      </p>
    </section>

    <!-- 2) Operation selector. Changing it reveals only the relevant fields. -->
    <section class="mb-5">
      <label for="op" class="block text-sm font-medium mb-1">Operation</label>
      <select id="op"
              class="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm
                     focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="validate">validate — is this a valid video? (JSON)</option>
        <option value="dimensions">dimensions — width / height / duration / fps (JSON)</option>
        <option value="duration">duration — length in seconds (JSON)</option>
        <option value="convert" selected>convert — re-encode / resize / drop audio</option>
        <option value="chunk">chunk — extract a [start, end] slice</option>
        <option value="black">black — synthesize a solid-black clip</option>
        <option value="image-loop">image-loop — loop a still image into a clip</option>
        <option value="concat">concat — join multiple clips head-to-tail</option>
        <option value="overlay">overlay — burn a still image onto the video</option>
        <option value="extract-audio">extract-audio — dump the audio track</option>
        <option value="mux-audio">mux-audio — attach an audio track</option>
        <option value="burn-subs">burn-subs — burn subtitles into frames</option>
        <option value="srt2vtt">srt2vtt — SRT → WebVTT + CSS (zip)</option>
        <option value="extract-frames">extract-frames — PNG frames (zip)</option>
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
        <input id="width" type="number" placeholder="(optional)"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="convert black image-loop">
        <label class="block text-xs font-medium mb-1">height</label>
        <input id="height" type="number" placeholder="(optional)"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="convert black image-loop concat">
        <label class="block text-xs font-medium mb-1">frame_rate</label>
        <input id="frame_rate" type="number" placeholder="(optional)"
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
      <div data-ops="extract-audio">
        <label class="block text-xs font-medium mb-1">audio format</label>
        <input id="audio_format" value="wav"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <!-- Secondary file inputs, revealed per operation. -->
      <div data-ops="concat" class="col-span-2">
        <label class="block text-xs font-medium mb-1">
          extra clip(s) — concat needs at least a second video
        </label>
        <input id="extra" type="file" accept="video/*" multiple
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="overlay" class="col-span-2">
        <label class="block text-xs font-medium mb-1">image to overlay</label>
        <input id="overlay_image" type="file" accept="image/*"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="mux-audio" class="col-span-2">
        <label class="block text-xs font-medium mb-1">audio track to attach</label>
        <input id="mux_audio_file" type="file" accept="audio/*,video/*"
               class="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" />
      </div>
      <div data-ops="burn-subs" class="col-span-2">
        <label class="block text-xs font-medium mb-1">subtitles (.srt / .vtt / .ass)</label>
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
        Run
      </button>
      <span id="status" class="ml-3 text-sm text-slate-600" role="status" aria-live="polite"></span>
    </section>

    <!-- 5) Players + result. Input on the left, output on the right. -->
    <section class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">Input</h2>
        <video id="in-video" controls class="w-full rounded"></video>
        <img id="in-image" class="w-full rounded" hidden alt="input still" />
      </div>
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <h2 class="mb-2 text-sm font-medium">Output</h2>
        <video id="out-video" controls class="w-full rounded"></video>
        <img id="out-image" class="w-full rounded" hidden alt="output still" />
        <audio id="out-audio" controls class="w-full" hidden></audio>
        <pre id="out-json" class="mt-2 overflow-auto rounded bg-slate-100 p-2 text-xs" hidden></pre>
        <div id="out-extra" class="mt-2 text-sm text-slate-600"></div>
        <a id="download" class="mt-2 inline-block text-sm font-medium text-blue-600 hover:underline"
           hidden download>Download result</a>
      </div>
    </section>
  </div>

  <script type="module">
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
      "convert": "/convert", "chunk": "/chunk", "black": "/black",
      "image-loop": "/image-loop", "concat": "/concat", "overlay": "/overlay",
      "extract-audio": "/extract-audio", "mux-audio": "/mux-audio",
      "burn-subs": "/burn-subs", "srt2vtt": "/srt2vtt", "extract-frames": "/extract-frames",
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
      if (!NO_INPUT_OPS.has(op) && !inputFile) { status("Pick an input file first."); return; }

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
        if (!img) { status("overlay needs an image file."); return; }
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
        if (!a) { status("mux-audio needs an audio file."); return; }
        fd.append("file", inputFile);
        fd.append("audio", a);
        fd.append("output_format", $("output_format").value);
      } else if (op === "burn-subs") {
        const s = $("subs_file").files[0];
        if (!s) { status("burn-subs needs a subtitles file."); return; }
        fd.append("file", inputFile);
        fd.append("subs", s);
        fd.append("output_format", $("output_format").value);
      } else if (op === "srt2vtt") {
        fd.append("file", inputFile);
      } else if (op === "extract-frames") {
        fd.append("file", inputFile);
        fd.append("frame_step", $("frame_step").value);
      }

      // Fire the request and render the response by response type.
      status("Running…");
      $("run").disabled = true;
      resetOutput();
      try {
        const res = await fetch(url, { method: "POST", body: fd });
        if (!res.ok) {
          const txt = await res.text();
          status("Error " + res.status + ": " + txt.slice(0, 200));
          return;
        }
        if (JSON_OPS.has(op)) {
          const j = await res.json();
          $("out-json").textContent = JSON.stringify(j, null, 2);
          $("out-json").hidden = false;
          status("Done.");
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
          $("out-extra").textContent = "Multiple files bundled as a .zip.";
        } else if (AUDIO_OPS.has(op)) {
          dl.download = "output." + ($("audio_format").value || "wav");
          $("out-audio").src = objUrl; $("out-audio").hidden = false;
        } else {
          // Single video file: play it inline and offer the download.
          dl.download = "output." + ($("output_format").value || "mp4");
          $("out-video").src = objUrl; $("out-video").hidden = false;
        }
        dl.hidden = false;
        status("Done.");
      } catch (err) {
        status("Request failed: " + err);
      } finally {
        $("run").disabled = false;
      }
    });
  </script>
</body>
</html>
"""
