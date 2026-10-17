# video-helper non-CLI surfaces

## 1. Library

```python
import video_helper as vh
```

`vh` is the suite's canonical alias. Public API (`video_helper.__all__`):
`is_valid_video_file`, `video_dimensions`, `video_duration`, `video_converter`,
`extract_video_chunk`, `compress_video`, `black_video`, `image_loop_to_video`,
`concat_videos`, `overlay_image`, `extract_audio_track`, `mux_audio_video`,
`burn_subtitles`, `srt2vtt`, `extract_frames`, `dump_frames`,
`extract_unique_colors`, `extract_optical_flow`, `iter_frame_optical_flow`,
`resize_flow`, `hw_vcodec`.

Logging and file management route through `os_helper` — the suite convention.

## 2. CLIs — argparse (core) and click (`[cli]`)

`video-helper` and `video-helper-click`. See `cli-reference.md`.

## 3. HTTP API — FastAPI (`[api]`)

```bash
pip install 'video-helper[api]'
python -m video_helper.api          # 127.0.0.1:8000, OpenAPI docs at /docs
```

One route per operation: `/validate`, `/dimensions`, `/duration`, `/convert`,
`/compress`, `/chunk`, `/black`, `/image-loop`, `/concat`, `/overlay`,
`/extract-audio`, `/mux-audio`, `/burn-subs`, `/srt2vtt`, `/extract-frames`,
`/extract-flow`, plus `/health`, `/` and `/gui`.

Uploads are multipart; responses stream the produced file back, or return JSON
for the probing routes.

## 4. MCP — `fastapi-mcp` over the *same* app (`[mcp]`)

```bash
pip install 'video-helper[mcp]'
video-helper-mcp                    # same app, MCP mounted at /mcp
```

`video_helper.mcp` takes the FastAPI app from `video_helper.api` and mounts
`FastApiMCP` on it. Every MCP tool *is* an HTTP route, so the two surfaces
cannot drift and one process serves both doors.

Register it with Claude Code:

```bash
claude mcp add video-helper --transport http http://127.0.0.1:8000/mcp
```

## 5. Browser GUI (`[api]`)

`GET /gui` — a minimal bench: drop a file, pick an operation, get the result.
See the repo's `GUI.md`.

## 6. The optional face / active-speaker stack (`[faces]`)

`video_helper.faces` is a separate module, not part of the core transforms:
YuNet face detection and SFace recognition (through opencv-python's own DNN
wrappers), PySceneDetect shot segmentation, and a LightASD active-speaker
engine in PyTorch. Weights are fetched on first use from the suite's own
mirror — `light_asd.onnx`, not the upstream `.pth`.

Reach for it when the question is "which face is speaking in this shot", and
only then: it is heavier than everything else in the package, and the core
install stays free of it on purpose.
