"""
Video Helper — FastAPI HTTP surface.

Exposes every public function in :mod:`video_helper.main` as an HTTP
endpoint so `video-helper` can be dropped behind any reverse proxy and
consumed by other services. Kept intentionally minimal:

- Multipart uploads for video inputs (``UploadFile``), streamed straight
  to a temporary file so large clips don't blow up memory.
- ``FileResponse`` for single-file outputs (``/convert``, ``/chunk`` …).
- ZIP-encoded ``StreamingResponse`` for multi-file outputs
  (``/extract-frames`` → PNG frames zipped) so the client gets one download
  per call.
- ``BackgroundTasks`` cleans temp files after the response has been
  streamed — no leftover garbage on disk after a request.

Install the extra to get the runtime dependencies::

    pip install 'video-helper[api]'

Then run the app with any ASGI server::

    uvicorn video_helper.api:app --host 0.0.0.0 --port 8000

Usage Example
-------------
>>> # Start the server:
>>> #   uvicorn video_helper.api:app --reload
>>> # Get a file's dimensions (JSON):
>>> #   curl -F 'file=@clip.mp4' http://localhost:8000/dimensions
>>> # Cut a slice:
>>> #   curl -F 'file=@clip.mp4' -F 'start=10' -F 'end=20' \\
>>> #        -o cut.mp4 http://localhost:8000/chunk
>>> # Extract PNG frames as a ZIP:
>>> #   curl -F 'file=@clip.mp4' -F 'frame_step=5' \\
>>> #        -o frames.zip http://localhost:8000/extract-frames
>>> # Full OpenAPI docs at http://localhost:8000/docs

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional

try:
    from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The FastAPI HTTP surface requires the [api] extra. "
        "Install with: pip install 'video-helper[api]'"
    ) from exc

from . import (
    black_video,
    burn_subtitles,
    concat_videos,
    extract_audio_track,
    extract_frames,
    extract_video_chunk,
    image_loop_to_video,
    is_valid_video_file,
    mux_audio_video,
    overlay_image,
    srt2vtt,
    video_converter,
    video_dimensions,
    video_duration,
)


# ---------------------------------------------------------------------------
# App factory + shared plumbing
# ---------------------------------------------------------------------------


app = FastAPI(
    title="Video Helper API",
    description=(
        "HTTP surface for the video-helper utilities: validate, dimensions, "
        "duration, convert, chunk, black-video, image-loop, concat, overlay, "
        "extract-audio, mux-audio, burn-subtitles, srt2vtt, extract-frames."
    ),
    version="1.6.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


def _spool(upload: UploadFile, dest_dir: Path, suffix_hint: Optional[str] = None) -> Path:
    """
    Persist an ``UploadFile`` to a temp path on disk.

    We copy the stream instead of holding the bytes in memory so a
    multi-hundred-MB clip does not OOM the worker. The file inherits
    the caller's suffix when available so ffmpeg picks the right
    demuxer.

    Parameters
    ----------
    upload : UploadFile
        The FastAPI upload object.
    dest_dir : Path
        Temp directory that will hold the spooled file.
    suffix_hint : str, optional
        Extension override (with or without the leading dot). Falls back
        to the client-provided filename's suffix.

    Returns
    -------
    Path
        Path to the spooled file on disk.
    """
    ext = suffix_hint or (Path(upload.filename or "").suffix or ".bin")
    if not ext.startswith("."):
        ext = "." + ext
    out = dest_dir / (f"upload{ext}")
    with out.open("wb") as fp:
        shutil.copyfileobj(upload.file, fp)
    return out


def _cleanup(*paths) -> None:
    """Best-effort cleanup — never let a tidy-up failure kill a response."""
    for p in paths:
        try:
            path = Path(p)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink(missing_ok=True)
        except Exception:
            pass


def _new_tmpdir() -> Path:
    """Create a request-scoped temp directory under the system temp root."""
    return Path(tempfile.mkdtemp(prefix="video-helper-"))


def _zip_folder(folder: Path) -> io.BytesIO:
    """Bundle ``folder``'s contents into an in-memory ZIP for streaming."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in folder.rglob("*"):
            if p.is_file():
                zf.write(p, arcname=p.relative_to(folder))
    buf.seek(0)
    return buf


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Simple liveness probe — no dependency check, just proves the app is up."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Read routes
# ---------------------------------------------------------------------------


@app.post("/validate", tags=["reads"])
def validate(file: UploadFile = File(...)) -> JSONResponse:
    """Probe an uploaded video for validity (ffprobe + extension check)."""
    tmp = _new_tmpdir()
    try:
        src = _spool(file, tmp)
        ok = is_valid_video_file(str(src))
    finally:
        _cleanup(tmp)
    return JSONResponse({"valid": bool(ok)})


@app.post("/dimensions", tags=["reads"])
def dimensions(file: UploadFile = File(...)) -> JSONResponse:
    """Return width/height/duration/frame_rate/has_sound for the upload."""
    tmp = _new_tmpdir()
    try:
        src = _spool(file, tmp)
        info = video_dimensions(str(src))
    finally:
        _cleanup(tmp)
    return JSONResponse(info)


@app.post("/duration", tags=["reads"])
def duration(file: UploadFile = File(...)) -> JSONResponse:
    """Return the duration in seconds of the uploaded video."""
    tmp = _new_tmpdir()
    try:
        src = _spool(file, tmp)
        seconds = video_duration(str(src))
    finally:
        _cleanup(tmp)
    return JSONResponse({"duration_seconds": float(seconds)})


# ---------------------------------------------------------------------------
# Action routes
# ---------------------------------------------------------------------------


@app.post("/convert", tags=["actions"])
def convert(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form("mp4", description="Target container extension."),
    frame_rate: Optional[int] = Form(None),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    without_sound: bool = Form(False),
):
    """Re-encode / resize / drop-audio the uploaded video."""
    tmp = _new_tmpdir()
    src = _spool(file, tmp)
    dst = tmp / f"converted.{output_format.lstrip('.')}"
    video_converter(
        input_video=str(src),
        output_video=str(dst),
        frame_rate=frame_rate,
        width=width,
        height=height,
        without_sound=without_sound,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/chunk", tags=["actions"])
def chunk(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    start: float = Form(...),
    end: float = Form(...),
    output_format: str = Form("mp4"),
):
    """Extract a ``[start, end]`` slice from the uploaded video."""
    tmp = _new_tmpdir()
    src = _spool(file, tmp)
    dst = tmp / f"chunk.{output_format.lstrip('.')}"
    extract_video_chunk(
        input_video=str(src),
        sample_start=start,
        sample_end=end,
        output_video=str(dst),
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/black", tags=["actions"])
def black(
    background: BackgroundTasks,
    duration_seconds: float = Form(..., alias="duration"),
    width: int = Form(...),
    height: int = Form(...),
    frame_rate: int = Form(30),
    output_format: str = Form("mp4"),
):
    """Synthesize a silent solid-black clip."""
    tmp = _new_tmpdir()
    dst = tmp / f"black.{output_format.lstrip('.')}"
    black_video(
        duration=duration_seconds,
        width=width,
        height=height,
        output_video=str(dst),
        frame_rate=frame_rate,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/image-loop", tags=["actions"])
def image_loop(
    background: BackgroundTasks,
    image: UploadFile = File(...),
    duration_seconds: float = Form(..., alias="duration"),
    frame_rate: int = Form(30),
    width: Optional[int] = Form(None),
    height: Optional[int] = Form(None),
    output_format: str = Form("mp4"),
):
    """Loop a still image for ``duration`` seconds into a silent video."""
    tmp = _new_tmpdir()
    img = _spool(image, tmp, suffix_hint=Path(image.filename or "").suffix or ".png")
    dst = tmp / f"loop.{output_format.lstrip('.')}"
    image_loop_to_video(
        image=str(img),
        duration=duration_seconds,
        output_video=str(dst),
        frame_rate=frame_rate,
        width=width,
        height=height,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/concat", tags=["actions"])
def concat(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    reencode: bool = Form(True),
    frame_rate: Optional[int] = Form(None),
    output_format: str = Form("mp4"),
):
    """Concatenate multiple uploaded videos head-to-tail."""
    if len(files) < 2:
        raise HTTPException(status_code=400, detail="concat needs at least 2 files")
    tmp = _new_tmpdir()
    # Spool inputs in order — FastAPI preserves multipart part ordering.
    srcs = [str(_spool(f, tmp, suffix_hint=Path(f.filename or "").suffix)) for f in files]
    # Two files spooled with the same "upload" prefix would collide; give
    # each spooled file a unique name derived from its position.
    for i, s in enumerate(srcs):
        renamed = tmp / f"input_{i:03d}{Path(s).suffix}"
        Path(s).rename(renamed)
        srcs[i] = str(renamed)
    dst = tmp / f"concat.{output_format.lstrip('.')}"
    concat_videos(
        input_videos=srcs,
        output_video=str(dst),
        reencode=reencode,
        frame_rate=frame_rate,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/overlay", tags=["actions"])
def overlay(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    image: UploadFile = File(...),
    x: str = Form("0"),
    y: str = Form("0"),
    scale_width: Optional[int] = Form(None),
    output_format: str = Form("mp4"),
):
    """Overlay a still image on the uploaded video."""
    tmp = _new_tmpdir()
    src = _spool(file, tmp, suffix_hint=Path(file.filename or "").suffix or ".mp4")
    # Second upload needs a different filename — spool manually.
    img = tmp / (f"overlay{Path(image.filename or '').suffix or '.png'}")
    with img.open("wb") as fp:
        shutil.copyfileobj(image.file, fp)
    dst = tmp / f"overlaid.{output_format.lstrip('.')}"
    overlay_image(
        input_video=str(src),
        image=str(img),
        output_video=str(dst),
        x=x,
        y=y,
        scale_width=scale_width,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/extract-audio", tags=["actions"])
def extract_audio(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    output_format: str = Form("wav"),
    sample_rate: int = Form(44100),
    channels: int = Form(2),
    encoding: str = Form("pcm_s16le"),
):
    """Dump the audio track of the uploaded video."""
    tmp = _new_tmpdir()
    src = _spool(file, tmp)
    dst = tmp / f"audio.{output_format.lstrip('.')}"
    extract_audio_track(
        input_video=str(src),
        output_audio=str(dst),
        sample_rate=sample_rate,
        channels=channels,
        encoding=encoding,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/mux-audio", tags=["actions"])
def mux_audio(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    audio: UploadFile = File(...),
    audio_codec: str = Form("aac"),
    audio_bitrate: str = Form("192k"),
    shortest: bool = Form(False),
    output_format: str = Form("mp4"),
):
    """Mux a separate audio track onto the uploaded video."""
    tmp = _new_tmpdir()
    src = _spool(file, tmp, suffix_hint=Path(file.filename or "").suffix or ".mp4")
    # Second upload — separate name.
    a = tmp / (f"audio_track{Path(audio.filename or '').suffix or '.wav'}")
    with a.open("wb") as fp:
        shutil.copyfileobj(audio.file, fp)
    dst = tmp / f"muxed.{output_format.lstrip('.')}"
    mux_audio_video(
        input_video=str(src),
        input_audio=str(a),
        output_video=str(dst),
        audio_codec=audio_codec,
        audio_bitrate=audio_bitrate,
        shortest=shortest,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/burn-subs", tags=["actions"])
def burn_subs(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    subs: UploadFile = File(...),
    force_style: Optional[str] = Form(None),
    output_format: str = Form("mp4"),
):
    """Burn subtitles into the frames of the uploaded video."""
    tmp = _new_tmpdir()
    src = _spool(file, tmp, suffix_hint=Path(file.filename or "").suffix or ".mp4")
    s = tmp / (f"subs{Path(subs.filename or '').suffix or '.srt'}")
    with s.open("wb") as fp:
        shutil.copyfileobj(subs.file, fp)
    dst = tmp / f"captioned.{output_format.lstrip('.')}"
    burn_subtitles(
        input_video=str(src),
        subtitles_file=str(s),
        output_video=str(dst),
        force_style=force_style,
    )
    background.add_task(_cleanup, tmp)
    return FileResponse(str(dst), filename=dst.name, media_type="application/octet-stream")


@app.post("/srt2vtt", tags=["actions"])
def srt2vtt_route(
    background: BackgroundTasks,
    file: UploadFile = File(...),
):
    """Convert an uploaded SRT to WebVTT + companion CSS; response is a ZIP."""
    tmp = _new_tmpdir()
    src = _spool(file, tmp, suffix_hint=".srt")
    out_vtt = tmp / "output.vtt"
    out_css = tmp / "output.css"
    srt2vtt(
        srt_file_path=str(src),
        vtt_file_path=str(out_vtt),
        css_file_path=str(out_css),
    )
    # Pack the two sibling files into a ZIP so the client gets both in one shot.
    pack_dir = tmp / "pack"
    pack_dir.mkdir()
    shutil.copy(out_vtt, pack_dir / out_vtt.name)
    shutil.copy(out_css, pack_dir / out_css.name)
    buf = _zip_folder(pack_dir)
    background.add_task(_cleanup, tmp)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="srt2vtt.zip"'},
    )


@app.post("/extract-frames", tags=["actions"])
def extract_frames_route(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    frame_step: int = Form(1),
    frame_interval: Optional[float] = Form(None),
    start: Optional[float] = Form(None),
    end: Optional[float] = Form(None),
    backend: str = Form("auto"),
):
    """Extract frames as PNGs; response is a ZIP archive."""
    import cv2  # noqa: WPS433 — deferred so the module import stays cheap

    tmp = _new_tmpdir()
    src = _spool(file, tmp, suffix_hint=Path(file.filename or "").suffix or ".mp4")
    frames_dir = tmp / "frames"
    frames_dir.mkdir()
    try:
        for i, frame in enumerate(
            extract_frames(
                video_path=str(src),
                frame_step=frame_step,
                frame_interval=frame_interval,
                start_instant=start,
                end_instant=end,
                backend=backend,
            )
        ):
            cv2.imwrite(str(frames_dir / f"frame_{i:09d}.png"), frame)
    except Exception as exc:
        _cleanup(tmp)
        raise HTTPException(status_code=500, detail=f"extract-frames failed: {exc}") from exc
    buf = _zip_folder(frames_dir)
    background.add_task(_cleanup, tmp)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="frames.zip"'},
    )
