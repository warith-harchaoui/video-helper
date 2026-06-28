import logging
import os
import platform
import re
import shutil
import subprocess
from typing import Iterator, List, Optional, Sequence, Set, Tuple

import cv2
import ffmpeg
import numpy as np
import os_helper as osh
from vidgear.gears import VideoGear


video_extensions = [
    "mp4",
    "avi",
    "mov",
    "wmv",
    "flv",
    "mkv",
    "webm",
    "mpeg",
    "mpg",
    "m4v",
    "3gp",
    "ogv",
    "mxf",
    "ts",
    "vob",
    "m2ts",
    "mts",
    "rm",
    "asf"
]

def extract_unique_colors(srt_file_path: str) -> Set[str]:
    """
    Extract all unique hex color codes from an SRT file.
    
    Parameters
    ----------
    srt_file_path : str
        Path to the input .srt file.
    
    Returns
    -------
    Set[str]
        A set of unique hex color codes found in the .srt file.

    Usage
    -----
    >>> srt_file = "subtitles.srt"
    >>> unique_colors = extract_unique_colors(srt_file)
    >>> print(unique_colors)
    {'#FF0000', '#00FF00', '#0000FF'}
    """
    color_tag_pattern = re.compile(r'<font color="(#\w{6})">', re.IGNORECASE)
    unique_colors = set()
    
    with open(srt_file_path, 'r', encoding='utf-8') as srt_file:
        for line in srt_file:
            # Find all occurrences of <font color="#RRGGBB">
            matches = color_tag_pattern.findall(line)
            # Add all found hex colors to the set (uppercase to avoid duplicates)
            unique_colors.update([match.upper() for match in matches])
    
    return unique_colors

def _generate_css_from_colors(color_codes: Set[str], css_file_path: str) -> None:
    """
    Generate a CSS file with styles for each unique color code.
    
    Parameters
    ----------
    color_codes : Set[str]
        A set of unique hex color codes.
    css_file_path : str
        Path to save the generated CSS file.

    Usage
    -----
    >>> unique_colors = {'#FF0000', '#00FF00', '#0000FF'}
    >>> css_file = "styles.css"
    >>> _generate_css_from_colors(unique_colors, css_file)
    """
    with open(css_file_path, 'w', encoding='utf-8') as css_file:
        for color in color_codes:
            # Strip the '#' from the color code for the class name and use the hex code for styling
            class_name = color.replace('#', '').lower()
            css_file.write(f"::cue(.{class_name}) {{ color: {color}; }}\n")

    logging.info(f"CSS file generated: {css_file_path}")

def srt2vtt(srt_file_path: str, vtt_file_path: str = None, css_file_path: str = None) -> None:
    """
    Convert an SRT subtitle file to WebVTT, preserving font colors and emitting a companion CSS file.

    Any ``<font color="#RRGGBB">…</font>`` tag in the SRT is rewritten as a
    WebVTT ``<c.<hex_lowercase>>…</c>`` cue class, and a stylesheet binding
    each class to its color is written next to the VTT.

    Parameters
    ----------
    srt_file_path : str
        Path to the input .srt file.
    vtt_file_path : str, optional
        Path to the output .vtt file. Defaults to ``<srt_stem>.vtt`` next
        to the input.
    css_file_path : str, optional
        Path to the output .css file. Defaults to ``<srt_stem>.css`` next
        to the input.

    Examples
    --------
    >>> srt2vtt("subtitles.srt")
    >>> srt2vtt("subtitles.srt", "out.vtt", "out.css")
    """
    unique_colors = extract_unique_colors(srt_file_path)

    folder, stem, _ = osh.folder_name_ext(srt_file_path)
    if osh.emptystring(vtt_file_path):
        vtt_file_path = osh.join([folder, stem + ".vtt"])
    if osh.emptystring(css_file_path):
        css_file_path = osh.join([folder, stem + ".css"])

    _generate_css_from_colors(unique_colors, css_file_path)

    def convert_color_tags(line: str) -> str:
        """Rewrite ``<font color="#RRGGBB">…</font>`` as ``<c.rrggbb>…</c>``."""
        color_tag_pattern = re.compile(
            r'<font color="(#\w{6})">(.*?)<\/font>', re.IGNORECASE
        )

        def replace_color(match: re.Match) -> str:
            color_code = match.group(1).upper()
            text = match.group(2)
            class_name = color_code.replace("#", "").lower()
            return f"<c.{class_name}>{text}</c>"

        return color_tag_pattern.sub(replace_color, line)

    with open(srt_file_path, "r", encoding="utf-8") as srt_file:
        lines = srt_file.readlines()

    with open(vtt_file_path, "w", encoding="utf-8") as vtt_file:
        vtt_file.write("WEBVTT\n\n")
        for line in lines:
            line = convert_color_tags(line)
            # WebVTT uses '.' for the fractional separator in timecodes; SRT uses ','.
            if "-->" in line:
                line = line.replace(",", ".")
            vtt_file.write(line)

    logging.info(f"WebVTT saved: {vtt_file_path}")

def is_valid_video_file(video_file: str) -> bool:
    """
    Check that ``video_file`` exists, has a known video extension, and contains a video stream.

    Combines an extension check (against :data:`video_extensions`) with an
    ``ffprobe`` invocation so both a fake ``.mp4`` (no video stream) and a
    real video renamed to ``.xyz`` are rejected.

    Parameters
    ----------
    video_file : str
        Path to the input video file.

    Returns
    -------
    bool
        True iff the file exists, ffprobe finds at least one video stream,
        and the extension is in :data:`video_extensions`.
    """
    if not osh.file_exists(video_file):
        logging.info(f"Video file not found: {video_file}")
        return False

    valid = False
    try:
        probe = ffmpeg.probe(video_file)
        next(s for s in probe["streams"] if s["codec_type"] == "video")
        valid = True
    except Exception:
        valid = False

    _, _, ext = osh.folder_name_ext(video_file)
    if ext.lower() not in video_extensions:
        valid = False

    logging.info(f"Video file {video_file} is {'valid' if valid else 'invalid'}")
    return valid



def video_dimensions(video_file: str) -> dict:
    """
    Get the dimensions of a video file using ffmpeg-python:
    - width
    - height
    - duration
    - frame rate

    Parameters
    ----------
    video_file : str
        Path to the input video file.

    Returns
    -------
    dict
        A dictionary containing the video dimensions:
        - width: int, width of the video in pixels
        - height: int, height of the video in pixels
        - duration: float, duration of the video in seconds
        - frame_rate: float, frame rate of the video in frames per second
        - has_sound: bool, whether the video has sound or not

    Usage
    -----
    >>> video_file = "video.mp4"
    >>> d = video_dimensions(video_file)
    >>> print(d)
    {'width': 1920, 'height': 1080, 'duration': 10.0, 'frame_rate': 30.0, 'has_sound': True}

    Notes
    -----
    The function uses ffmpeg to probe the video file and extract the video stream information to get the dimensions, duration, and frame rate.
    """
    osh.checkfile(video_file, msg=f"Video file not found: {video_file}")

    probe = ffmpeg.probe(video_file)
    video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
    width = int(video_info["width"])
    height = int(video_info["height"])
    duration = float(video_info["duration"])
    frame_rate = video_info["r_frame_rate"]
    frame_rate = frame_rate.split("/")
    frame_rate = float(frame_rate[0]) / float(frame_rate[1])
    has_sound = any(s["codec_type"] == "audio" for s in probe["streams"])
    d = {
        "width": width,
        "height": height,
        "duration": duration,
        "frame_rate": frame_rate,
        "has_sound": has_sound,
    }
    return d



def video_converter(
    input_video: str,
    output_video: str = None,
    frame_rate: int = None,
    width: int = None,
    height: int = None,
    without_sound: bool = False,
):
    """
    Convert a video file to a new format with specified options.

    Parameters
    ----------
    input_video : str
        Path to the input video file.
    output_video : str
        Path to the output video file.
    frame_rate : int, optional
        Frame rate of the output video file.
    width : int, optional
        Width of the output video file. If only width is specified, aspect ratio is maintained. If width is odd, it is reduced by 1 (ffmpeg reasons).
    height : int, optional
        Height of the output video file. If only height is specified, aspect ratio is maintained. If height is odd, it is reduced by 1 (ffmpeg reasons).
    without_sound : bool, optional
        Remove audio from the output video file.

    Notes
    -----
    - The output video file will be in the same format as the input, unless an output file with a different format is specified.
        
    Examples
    --------
    >>> video_converter("input.mp4", "output.mp4", frame_rate=30, width=640, height=480)
    >>> video_converter("input.mp4", "output.mp4", without_sound=True)
    """
    logging.info(f"Converting video file:\n\t{input_video}\ninto\n\t{output_video}")

    # Check if the input video file exists and is valid
    assert is_valid_video_file(input_video), f"Input video file not okay:\n\t{input_video}"

    quiet = osh.verbosity() <= 0  # Determine verbosity level

    # Extract folder and file extension details
    fi, bi, input_ext = osh.folder_name_ext(input_video)
    if osh.emptystring(output_video):
        output_video = osh.join(fi, bi + "-converted" + "." + input_ext)

    fo, bo, output_ext = osh.folder_name_ext(output_video)

    # If no conversion is required, just copy the streams — but only when
    # the container does not change. Cross-container stream copy (e.g.
    # WebM/VP8 into .mp4) is rejected by ffmpeg because most codecs are
    # not muxable in every container. In that case we transcode to
    # H.264/AAC, which is the lingua franca every MP4-class container
    # accepts.
    if not frame_rate and not width and not height and not without_sound:
        if input_ext.lower() == output_ext.lower():
            ffmpeg.input(input_video).output(output_video, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
        else:
            ffmpeg.input(input_video).output(
                output_video, vcodec='libx264', acodec='aac', pix_fmt='yuv420p',
            ).run(overwrite_output=True, quiet=quiet)
        assert is_valid_video_file(output_video), f"Failed to convert video file:\n\t{output_video}"
        logging.info(f"Video file converted successfully:\n{output_video}")
        return

    # Ensure width and height are even
    if width and width % 2 != 0:
        width -= 1
    if height and height % 2 != 0:
        height -= 1

    # Use temporary files for conversion if needed
    with osh.temporary_filename(suffix=".mp4", mode="wb") as temp_input, \
         osh.temporary_filename(suffix=".mp4", mode="wb") as temp_output:

        # Normalize the input into an .mp4 container before the filter
        # pass. Codec-copy only works when source codecs are already
        # MP4-compatible (h264 + aac); for VP8/VP9/Opus/etc. we must
        # transcode, otherwise ffmpeg refuses the cross-container mux.
        if input_ext.lower() != "mp4":
            transcode_kwargs = {'vcodec': 'libx264', 'pix_fmt': 'yuv420p'}
            if without_sound:
                transcode_kwargs['an'] = None
            else:
                transcode_kwargs['acodec'] = 'aac'
            ffmpeg.input(input_video).output(temp_input, **transcode_kwargs).run(overwrite_output=True, quiet=quiet)
        else:
            osh.copyfile(input_video, temp_input)  # Direct copy if already MP4

        stream = ffmpeg.input(temp_input)

        # Dictionary to store ffmpeg options
        ffmpeg_options = {}

        # Set the frame rate if specified
        if frame_rate:
            ffmpeg_options["r"] = frame_rate

        # Apply video scaling and padding if needed
        if width and height:
            ffmpeg_options["vf"] = f"scale='min({width},iw*{height}/ih):min({height},ih*{width}/iw)',pad='{width}:{height}:(ow-iw)/2:(oh-ih)/2:black'"
        elif width:
            ffmpeg_options["vf"] = f"scale={width}:-1"  # Maintain aspect ratio
        elif height:
            ffmpeg_options["vf"] = f"scale=-1:{height}"  # Maintain aspect ratio

        # Remove audio if specified
        if without_sound:
            ffmpeg_options["an"] = None  # Disable audio stream

        # Perform the conversion with the specified options
        stream = stream.output(temp_output, **ffmpeg_options)
        stream.run(overwrite_output=True, quiet=quiet)

        # If the output format is not MP4, perform final conversion
        if output_ext.lower() != "mp4":
            ffmpeg.input(temp_output).output(output_video, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
        else:
            osh.copyfile(temp_output, output_video)  # Copy to final output if MP4

    # Validate the final output video
    assert is_valid_video_file(output_video), f"Failed to convert video file:\n\t{input_video}\ninto\n\t{output_video}"

    # Retrieve video properties for validation
    d = video_dimensions(output_video)

    # Validate frame rate
    if frame_rate:
        error = round(100 * np.abs(d["frame_rate"] - frame_rate) / frame_rate)
        assert error < 2, f"Failed to set frame rate for video file ({d['frame_rate']} vs {frame_rate}, error = {error}%):\n\t{output_video}"

    # Validate width and height
    if width:
        assert d["width"] == width, f"Failed to set width for video file:\n\t{output_video}"
    if height:
        assert d["height"] == height, f"Failed to set height for video file:\n\t{output_video}"

    # Validate sound removal
    if without_sound:
        assert not d["has_sound"], f"Failed to remove audio from video file:\n\t{output_video}"

    logging.info(f"Video file converted successfully:\n\t{output_video}")







# ──────────────────────────────────────────────────────────────────────────
#  Backend dispatcher for ``extract_frames``
#
#  Three backends with distinct sweet spots, picked automatically (override
#  via the ``backend=`` kwarg). See SPEED_ANALYSIS.md for the empirical
#  evidence behind the routing rules.
#
#  - ``vidgear``      → fastest path for **full sequential decode** on
#                       macOS (OpenCV+AVFoundation + worker thread); the
#                       only backend that supports ``stabilize=True``.
#                       Decodes from t=0 with no real seek, so it pays a
#                       large tax on windowed / sparse reads.
#  - ``pyav``         → fastest for **windowed sequential** and **sparse**
#                       (frame_indices / frame_times) thanks to keyframe
#                       seek. Default for everything that isn't a full
#                       sequential read. Honors ``hwaccel``.
#  - ``ffmpeg-pipe``  → ffmpeg subprocess fallback (true ``-ss``/``-to``
#                       seek). Used only when PyAV isn't installed.
#
#  History: a decord backend was prototyped in v1.4 but removed before
#  release — empirical benchmarks (see SPEED_ANALYSIS.md) showed PyAV
#  beating decord by ~30% on its own sweet-spot (sparse access) while
#  avoiding decord's ffmpeg@4 source-build install pain.
#
#  All backends yield BGR uint8 ndarrays of shape (H, W, 3) for backward
#  compatibility with the OpenCV / VidGear convention.
# ──────────────────────────────────────────────────────────────────────────


_BACKENDS = ("auto", "vidgear", "pyav", "ffmpeg-pipe")


def _resolve_hwaccel(hwaccel: Optional[str]) -> Optional[str]:
    """Translate ``hwaccel="auto"`` into a concrete value supported by the
    locally-installed ffmpeg, or None when no acceleration is available.

    A value of ``None`` (Python None) disables hwaccel — this is the
    default for ``extract_frames`` because the SPEED_ANALYSIS benchmark
    showed VideoToolbox hurting every scenario on a 426×426 H.264 clip
    (the format-conversion overhead eats the decode win on small frames).
    Worth re-evaluating on 4K HEVC content.

    Any explicit string is returned as-is so the caller can opt into
    something exotic without fighting the heuristic.
    """
    if hwaccel != "auto":
        return hwaccel
    if shutil.which("ffmpeg") is None:
        return None
    try:
        supported = subprocess.run(
            ["ffmpeg", "-hide_banner", "-hwaccels"],
            capture_output=True, text=True, check=False,
        ).stdout
    except Exception:
        return None
    system = platform.system().lower()
    if system == "darwin" and "videotoolbox" in supported:
        return "videotoolbox"
    if "cuda" in supported and shutil.which("nvidia-smi") is not None:
        return "cuda"
    if "qsv" in supported:
        return "qsv"
    return None


def _have_pyav() -> bool:
    try:
        import av  # noqa: F401
        return True
    except ImportError:
        return False


def _choose_backend(
    backend: str,
    stabilize: bool,
    sparse: bool,
    full_sequential: bool,
) -> str:
    """Resolve ``backend="auto"`` against installed packages and call shape.

    Routing rules (when ``backend="auto"``):

    - ``stabilize=True``                  → vidgear (forced; only one that supports it)
    - sparse access (indices / times)     → pyav if installed, else vidgear (range+filter fallback)
    - full sequential (start=0, end=total)→ vidgear (4× faster than PyAV on macOS — see SPEED_ANALYSIS.md)
    - windowed sequential                 → pyav if installed, else ffmpeg-pipe if ffmpeg on PATH, else vidgear
    """
    if backend not in _BACKENDS:
        raise ValueError(
            f"Unknown backend {backend!r}; expected one of {_BACKENDS}"
        )
    if stabilize:
        if backend not in ("auto", "vidgear"):
            raise ValueError(
                f"stabilize=True requires the vidgear backend; got backend={backend!r}"
            )
        return "vidgear"
    if backend != "auto":
        return backend

    if sparse:
        # Sparse access: PyAV's keyframe-seek + PTS filter is the fastest
        # option we ship (see SPEED_ANALYSIS.md). VidGear's no-seek loop
        # is a last-resort fallback when PyAV is missing.
        return "pyav" if _have_pyav() else "vidgear"

    if full_sequential:
        # Full sequential reads: VidGear (OpenCV+AVFoundation + worker
        # thread) beats PyAV by 4× on macOS. No reason to give that up.
        return "vidgear"

    # Windowed sequential: PyAV's keyframe seek wins. ffmpeg-pipe is a
    # backup when PyAV is missing; VidGear last because it has no real seek.
    if _have_pyav():
        return "pyav"
    if shutil.which("ffmpeg") is not None:
        return "ffmpeg-pipe"
    return "vidgear"


def _resolve_indices(
    duration: float,
    frame_rate: float,
    start_index: Optional[int],
    end_index: Optional[int],
    start_instant: Optional[float],
    end_instant: Optional[float],
    frame_step: int,
    frame_interval: Optional[float],
    frame_indices: Optional[Sequence[int]],
    frame_times: Optional[Sequence[float]],
):
    """Normalize the public range/sparse API into a single representation.

    Returns
    -------
    indices : list[int] | None
        Concrete indices when sparse access was requested, else None.
    start_index, end_index : int
        Inclusive bounds when sequential access was requested.
    frame_step : int
        Sampling stride (>=1).
    sparse : bool
        True iff the caller specified ``frame_indices`` / ``frame_times``.
    """
    total = int(duration * frame_rate)

    if frame_times is not None:
        frame_indices = [int(round(t * frame_rate)) for t in frame_times]
    if frame_indices is not None:
        indices = sorted({int(i) for i in frame_indices if 0 <= int(i) < total})
        return indices, 0, total - 1, 1, True

    if start_instant is not None:
        start_index = int(start_instant * frame_rate)
    if end_instant is not None:
        end_index = int(end_instant * frame_rate)
    if start_index is None:
        start_index = 0
    if end_index is None:
        end_index = total
    if frame_interval is not None:
        frame_step = max(1, int(frame_interval * frame_rate))
    frame_step = max(1, int(frame_step))

    assert 0 <= start_index <= end_index <= total, (
        f"Invalid frame range:\n\t{start_index} "
        f"({osh.time2str(1.0 * start_index / frame_rate)}) to {end_index} "
        f"({osh.time2str(1.0 * end_index / frame_rate)}).\n"
        f"It should be within 0 to {total} (for {osh.time2str(duration)} "
        f"at {frame_rate} fps)"
    )
    return None, start_index, end_index, frame_step, False


def _extract_via_vidgear(
    video_path: str,
    start_index: int,
    end_index: int,
    frame_step: int,
    stabilize: bool,
) -> Iterator[np.ndarray]:
    """Decode-everything-and-filter loop on top of VidGear / OpenCV.

    Only path that supports software stabilization. Decodes from frame 0
    even when ``start_index > 0`` (no real seek) — accept this cost when
    stabilization is required or when faster backends aren't installed.
    """
    stream = VideoGear(source=video_path, stabilize=stabilize).start()
    current_index = 0
    try:
        while True:
            frame = stream.read()
            if frame is None:
                break
            if current_index < start_index:
                current_index += 1
                continue
            if current_index <= end_index and (current_index - start_index) % frame_step == 0:
                yield frame
            if current_index > end_index:
                break
            current_index += 1
    finally:
        stream.stop()


def _join_http_headers(http_headers: Optional[dict]) -> Optional[str]:
    """ffmpeg / PyAV want a single CRLF-separated header string."""
    if not http_headers:
        return None
    return "\r\n".join(f"{k}: {v}" for k, v in http_headers.items()) + "\r\n"


def _parse_pad_color(pad_color: str) -> Tuple[int, int, int]:
    """Parse opaque ``pad_color`` into a BGR uint8 tuple.

    Accepted values:
    - common names: ``"black"`` / ``"white"`` / ``"red"`` / ``"green"`` / ``"blue"``
    - hex: ``"#RRGGBB"``
    - ``"transparent"`` → :class:`ValueError` (would require 4-channel
      BGRA output, breaking the ``(H, W, 3)`` contract — planned for v1.6.0).
    """
    name = pad_color.lower().strip()
    if name == "transparent":
        raise ValueError(
            "pad_color='transparent' is not supported in v1.5.0 — it would "
            "require 4-channel BGRA / RGBA output, breaking the (H, W, 3) "
            "contract on every destination. Planned for v1.6.0."
        )
    named = {
        "black": (0, 0, 0),
        "white": (255, 255, 255),
        "red": (0, 0, 255),      # BGR
        "green": (0, 255, 0),
        "blue": (255, 0, 0),     # BGR
        "yellow": (0, 255, 255),
        "cyan": (255, 255, 0),
        "magenta": (255, 0, 255),
        "gray": (128, 128, 128),
        "grey": (128, 128, 128),
    }
    if name in named:
        return named[name]
    if name.startswith("#") and len(name) == 7:
        try:
            r = int(name[1:3], 16)
            g = int(name[3:5], 16)
            b = int(name[5:7], 16)
            return (b, g, r)
        except ValueError:
            pass
    raise ValueError(
        f"Unknown pad_color {pad_color!r}; expected one of "
        f"{sorted(named)} / '#RRGGBB' / 'transparent' (transparent → v1.6.0)"
    )


def _apply_output_transform(
    frame: np.ndarray,
    output_width: Optional[int],
    output_height: Optional[int],
    pad_color_bgr: Tuple[int, int, int],
) -> np.ndarray:
    """Resize a BGR frame to (``output_width``, ``output_height``).

    Behavior:
    - Both dimensions set → scale-fit (preserve aspect ratio) then pad
      with ``pad_color_bgr`` so the output is exactly the requested size.
    - Only one dimension set → scale to that dimension preserving aspect
      ratio (the other dimension is derived; no pad).
    - Neither set → return frame unchanged.

    Uses ``cv2.INTER_AREA`` when downscaling (sharper for downsizing)
    and ``cv2.INTER_LINEAR`` when upscaling (cheap, no ringing).
    """
    if output_width is None and output_height is None:
        return frame

    h, w = frame.shape[:2]

    if output_width is not None and output_height is not None:
        scale = min(output_width / w, output_height / h)
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        scaled = cv2.resize(frame, (new_w, new_h), interpolation=interp)
        pad_top = (output_height - new_h) // 2
        pad_bottom = output_height - new_h - pad_top
        pad_left = (output_width - new_w) // 2
        pad_right = output_width - new_w - pad_left
        return cv2.copyMakeBorder(
            scaled,
            pad_top, pad_bottom, pad_left, pad_right,
            cv2.BORDER_CONSTANT,
            value=list(pad_color_bgr),
        )

    if output_width is not None:
        scale = output_width / w
        new_h = max(1, int(round(h * scale)))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
        return cv2.resize(frame, (output_width, new_h), interpolation=interp)

    # output_height is not None
    scale = output_height / h
    new_w = max(1, int(round(w * scale)))
    interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LINEAR
    return cv2.resize(frame, (new_w, output_height), interpolation=interp)


def _extract_via_pyav(
    video_path: str,
    start_index: int,
    end_index: int,
    frame_step: int,
    sparse_indices: Optional[Sequence[int]],
    frame_rate: float,
    hwaccel: Optional[str],
    http_headers: Optional[dict] = None,
) -> Iterator[np.ndarray]:
    """PyAV-based decode with keyframe seek and optional hardware accel.

    Notes
    -----
    PyAV's ``container.seek`` accepts an offset in ``AV_TIME_BASE`` units
    (microseconds) when no ``stream`` is passed. We rely on that and
    recover the exact frame index from ``frame.pts * stream.time_base``,
    so a coarse keyframe seek is fine — we just drop everything before the
    requested index.

    Hardware acceleration is wired through ``av.codec.hwaccel.HWAccel``
    (not the format-context ``options=`` kwarg, which is silently ignored
    for hwaccel — that bug existed in v1.4.0-dev and inflated all
    ``hwaccel="auto"`` cells in SPEED_ANALYSIS.md to be no-ops).
    """
    import av  # lazy

    # HTTP headers (User-Agent / Referer / Cookie / Authorization) are
    # fed to libavformat via the AVFormatContext options dict — that's
    # the right place for them (unlike hwaccel, which the same kwarg
    # silently ignores; see _extract_via_pyav notes above).
    open_options: Optional[dict] = None
    headers_str = _join_http_headers(http_headers)
    if headers_str:
        open_options = {"headers": headers_str}

    if hwaccel:
        try:
            hw = av.codec.hwaccel.HWAccel(device_type=hwaccel)
            container = av.open(video_path, hwaccel=hw, options=open_options) \
                if open_options else av.open(video_path, hwaccel=hw)
        except (av.error.ValueError, ValueError) as exc:
            logging.warning(
                "PyAV hwaccel=%r unavailable (%s); falling back to software decode",
                hwaccel, exc,
            )
            container = av.open(video_path, options=open_options) \
                if open_options else av.open(video_path)
    else:
        container = av.open(video_path, options=open_options) \
            if open_options else av.open(video_path)
    try:
        stream = container.streams.video[0]
        stream.thread_type = "AUTO"

        def _seek_to_seconds(seconds: float) -> None:
            # AV_TIME_BASE is 1 µs; convert seconds → microseconds.
            offset_us = max(0, int(seconds * 1_000_000))
            container.seek(offset_us, any_frame=False, backward=True)

        def _index_of(frame) -> int:
            if frame.pts is None:
                return -1
            return int(round(float(frame.pts * stream.time_base) * frame_rate))

        if sparse_indices is not None and len(sparse_indices) > 0:
            wanted = sorted(set(sparse_indices))
            wanted_set = set(wanted)
            _seek_to_seconds(wanted[0] / frame_rate)
            for frame in container.decode(stream):
                index = _index_of(frame)
                if index in wanted_set:
                    yield frame.to_ndarray(format="bgr24")
                    wanted_set.discard(index)
                    if not wanted_set:
                        break
            return

        # Sequential range: seek to a keyframe at-or-before start_index,
        # then PTS-filter to the exact bounds.
        if start_index > 0:
            _seek_to_seconds(start_index / frame_rate)
        for frame in container.decode(stream):
            index = _index_of(frame)
            if index < start_index:
                continue
            if index > end_index:
                break
            if (index - start_index) % frame_step == 0:
                yield frame.to_ndarray(format="bgr24")
    finally:
        container.close()


def _extract_via_ffmpeg_pipe(
    video_path: str,
    start_index: int,
    end_index: int,
    frame_step: int,
    frame_rate: float,
    width: int,
    height: int,
    hwaccel: Optional[str],
    http_headers: Optional[dict] = None,
) -> Iterator[np.ndarray]:
    """ffmpeg subprocess with -ss/-to true seek and raw bgr24 over a pipe.

    Sequential only (no sparse). Useful when PyAV is unavailable but
    ffmpeg is. Hwaccel is honored when supported by the local build.
    HTTP headers (``http_headers``) are passed via ``-headers`` and
    placed before ``-i`` so they reach the input demuxer.
    """
    start_s = start_index / frame_rate
    end_s = (end_index + 1) / frame_rate
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]
    if hwaccel:
        cmd += ["-hwaccel", hwaccel]
    headers_str = _join_http_headers(http_headers)
    if headers_str:
        cmd += ["-headers", headers_str]
    cmd += ["-ss", f"{start_s:.6f}", "-to", f"{end_s:.6f}", "-i", video_path]
    if frame_step > 1:
        # Sample every Nth frame after the seek.
        cmd += ["-vf", f"select=not(mod(n\\,{frame_step}))", "-vsync", "vfr"]
    cmd += ["-f", "rawvideo", "-pix_fmt", "bgr24", "-"]

    frame_size = width * height * 3
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        while True:
            raw = proc.stdout.read(frame_size)
            if not raw or len(raw) < frame_size:
                break
            yield np.frombuffer(raw, dtype=np.uint8).reshape((height, width, 3)).copy()
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        # Drain stderr for diagnostics.
        err = proc.stderr.read().decode("utf-8", errors="replace").strip()
        if err and proc.returncode not in (0, None):
            logging.warning("ffmpeg stderr: %s", err)


# ──────────────────────────────────────────────────────────────────────────
#  Destination converter — yields frames in the user's preferred form
#  with the **conventional** colorspace and axis layout for that framework.
#
#  Shapes & colorspaces (the cheat sheet)
#  ----------------------------------------
#  Notation: N = batch size, T = time (frames in a video), C = channels
#  (always 3), H = height, W = width.
#
#  destination="numpy"  (OpenCV-compatible: BGR uint8, channels last)
#  ┌──────────┬─────────────┬────────────────────────┐
#  │ layout   │ batch_size  │ shape (BGR uint8)      │
#  ├──────────┼─────────────┼────────────────────────┤
#  │  any     │   None      │ (H, W, 3)       HWC    │
#  │  image   │   N         │ (N, H, W, 3)    NHWC   │
#  │  video   │   N         │ (N, H, W, 3)    THWC   │  (same memory as NHWC; T == N)
#  └──────────┴─────────────┴────────────────────────┘
#
#  destination="torch"  (PyTorch-conventional: RGB uint8, channels first)
#  ┌──────────┬─────────────┬────────────────────────┐
#  │ layout   │ batch_size  │ shape (RGB uint8)      │
#  ├──────────┼─────────────┼────────────────────────┤
#  │  any     │   None      │ (3, H, W)       CHW    │
#  │  image   │   N         │ (N, 3, H, W)    NCHW   │  (batch of independent images)
#  │  video   │   N         │ (3, N, H, W)    CTHW   │  (single video clip, T == N)
#  └──────────┴─────────────┴────────────────────────┘
#
#  destination="pil"  (PIL/Pillow convention: RGB, size = (W, H), no batch)
#  Each yield is a single ``PIL.Image.Image`` with ``mode="RGB"`` and
#  ``size = (W, H)``. ``batch_size`` is not supported (Pillow has no
#  batched image type); ``layout`` is ignored. Pillow is imported lazily.
#  Use this destination for code that calls PIL/Pillow methods (filters,
#  paste, draw, …); otherwise numpy or torch are cheaper.
#
#  Notes:
#  - ``layout`` only matters when ``batch_size`` is set (for numpy/torch).
#    Without batching, each yield is a single frame (HWC numpy / CHW
#    torch / PIL image) regardless.
#  - For numpy the layout choice is purely *semantic* (NHWC and THWC
#    share the same memory). For torch it's a real permutation
#    (NCHW vs CTHW differ in axis order).
#  - The BGR→RGB conversion for torch happens via ``tensor.flip(-1)``
#    on the channel axis (cheap, view-style until ``.contiguous()``).
#  - When ``destination`` is ``"torch"`` / ``"pil"``, the corresponding
#    library is imported lazily — video-helper itself does NOT take torch
#    or Pillow as a dependency. Install via the ``[torch]`` / ``[pil]``
#    extras (or bring your own).
# ──────────────────────────────────────────────────────────────────────────


def _have_torch() -> bool:
    try:
        import torch  # noqa: F401
        return True
    except ImportError:
        return False


def _have_pil() -> bool:
    try:
        import PIL.Image  # noqa: F401
        return True
    except ImportError:
        return False


def _resolve_torch_device(device: str):
    """Translate ``device`` ("auto" / "cpu" / "mps" / "cuda") into a torch.device.

    "auto" → cuda if available, else mps if available, else cpu.
    """
    import torch  # lazy

    if device == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    return torch.device(device)


def _bgr_hwc_to_torch_chw_rgb(np_frame: np.ndarray, device):
    """Convert one numpy HWC BGR uint8 frame to a torch CHW RGB uint8 tensor."""
    import torch  # lazy
    # flip(-1): reverse the channel axis (BGR → RGB).
    # permute(2, 0, 1): HWC → CHW.
    # contiguous(): force a single copy so downstream ops don't trip on a
    # non-contiguous tensor; the .to(device) call below would do its own
    # copy anyway, so this is essentially free.
    return torch.from_numpy(np_frame).flip(-1).permute(2, 0, 1).contiguous().to(device)


def _bgr_to_torch_image_batch(np_batch_nhwc: np.ndarray, device):
    """Convert numpy NHWC BGR uint8 batch → torch NCHW RGB uint8 on device."""
    import torch
    return (
        torch.from_numpy(np_batch_nhwc)
        .flip(-1)                  # NHWC BGR → NHWC RGB
        .permute(0, 3, 1, 2)       # NHWC → NCHW
        .contiguous()
        .to(device)
    )


def _bgr_to_torch_video_clip(np_clip_thwc: np.ndarray, device):
    """Convert numpy THWC BGR uint8 clip → torch CTHW RGB uint8 on device."""
    import torch
    return (
        torch.from_numpy(np_clip_thwc)
        .flip(-1)                  # THWC BGR → THWC RGB
        .permute(3, 0, 1, 2)       # THWC → CTHW
        .contiguous()
        .to(device)
    )


def _to_destination(
    np_frames: Iterator[np.ndarray],
    destination: str,
    device: str,
    batch_size: Optional[int],
    layout: str,
):
    """Convert/batch the upstream numpy-frame iterator into the requested destination.

    See the cheat-sheet at the top of this section for shapes / colorspaces.
    """
    if destination not in ("numpy", "torch", "pil"):
        raise ValueError(
            f"Unknown destination {destination!r}; "
            "expected 'numpy', 'torch', or 'pil'"
        )
    if destination == "pil" and batch_size is not None:
        raise ValueError(
            "destination='pil' does not support batch_size — Pillow has no "
            "batched image type. Iterate per-frame, or use destination='numpy' "
            "/ 'torch' for batched tensors."
        )
    if layout not in ("image", "video"):
        raise ValueError(
            f"Unknown layout {layout!r}; expected 'image' or 'video'"
        )
    if batch_size is not None and batch_size < 1:
        raise ValueError(f"batch_size must be >= 1, got {batch_size}")

    # ------------ destination="numpy" -----------------------------------
    if destination == "numpy":
        if batch_size is None:
            # HWC BGR uint8 — pass-through, no copy.
            yield from np_frames
            return
        # NHWC == THWC for numpy (only the semantic name differs); we stack
        # along axis 0 regardless of layout.
        batch: list = []
        for frame in np_frames:
            batch.append(frame)
            if len(batch) == batch_size:
                yield np.stack(batch, axis=0)
                batch = []
        if batch:
            yield np.stack(batch, axis=0)
        return

    # ------------ destination="pil" -------------------------------------
    if destination == "pil":
        if not _have_pil():
            raise ImportError(
                "destination='pil' requires Pillow. Install with: "
                "pip install 'video-helper[pil]' (or bring your own PIL)"
            )
        from PIL import Image  # lazy
        for frame in np_frames:
            # Flip BGR → RGB before handing to PIL (which is RGB-native).
            yield Image.fromarray(frame[:, :, ::-1])
        return

    # ------------ destination="torch" -----------------------------------
    if not _have_torch():
        raise ImportError(
            "destination='torch' requires PyTorch. Install with: pip install 'video-helper[torch]' "
            "(or bring your own torch)"
        )

    dev = _resolve_torch_device(device)

    if batch_size is None:
        # CHW RGB uint8 per yielded frame. layout is irrelevant here
        # (each yield is a single frame, no time / batch axis).
        for frame in np_frames:
            yield _bgr_hwc_to_torch_chw_rgb(frame, dev)
        return

    # Batched: layout chooses the axis convention.
    batch = []
    for frame in np_frames:
        batch.append(frame)
        if len(batch) == batch_size:
            stacked = np.stack(batch, axis=0)        # NHWC == THWC, BGR
            if layout == "image":
                yield _bgr_to_torch_image_batch(stacked, dev)    # NCHW RGB
            else:  # "video"
                yield _bgr_to_torch_video_clip(stacked, dev)     # CTHW RGB
            batch = []
    if batch:
        stacked = np.stack(batch, axis=0)
        if layout == "image":
            yield _bgr_to_torch_image_batch(stacked, dev)
        else:
            yield _bgr_to_torch_video_clip(stacked, dev)


def extract_frames(
    video_path: str,
    start_index: Optional[int] = None,
    end_index: Optional[int] = None,
    start_instant: Optional[float] = None,
    end_instant: Optional[float] = None,
    stabilize: bool = False,
    frame_step: int = 1,
    frame_interval: Optional[float] = None,
    frame_indices: Optional[Sequence[int]] = None,
    frame_times: Optional[Sequence[float]] = None,
    backend: str = "auto",
    hwaccel: Optional[str] = None,
    http_headers: Optional[dict] = None,
    output_width: Optional[int] = None,
    output_height: Optional[int] = None,
    pad_color: str = "black",
    destination: str = "numpy",
    device: str = "cpu",
    batch_size: Optional[int] = None,
    layout: str = "image",
) -> Iterator:
    """
    Extract frames from a video, dispatching to the best available backend.

    The function picks a backend automatically based on the requested
    access pattern and what's installed locally; pass ``backend=...`` to
    override. Frames are yielded in the user's preferred form via
    ``destination`` (numpy array or torch tensor on a chosen device),
    optionally **batched** to amortize the host→device transfer.

    Backends
    --------
    - ``vidgear`` — OpenCV+VidGear with a producer thread. **Fastest path
      for full sequential decode** up to ~720p on macOS (uses
      AVFoundation under the hood) and the **only backend that supports**
      ``stabilize=True``. Decodes from t=0 with no real seek.
    - ``pyav`` — direct ffmpeg libav bindings. **Best default for
      windowed sequential, sparse reads, and any "torch on GPU"
      destination** thanks to keyframe seek + hwaccel support.
    - ``ffmpeg-pipe`` — ffmpeg subprocess fallback. Useful when PyAV
      isn't installed. Sequential only; honors ``hwaccel``.

    Parameters
    ----------
    video_path : str
        Path to the input video file.
    start_index, end_index : int, optional
        Inclusive frame-index bounds. If None, defaults to start-of-file
        and end-of-file respectively.
    start_instant, end_instant : float, optional
        Same bounds expressed in seconds. When provided, they override the
        index form.
    stabilize : bool, optional
        If True, runs VidGear's software stabilizer. Forces ``backend="vidgear"``.
    frame_step : int, optional
        Sampling stride within the range (every Nth frame). Defaults to 1.
    frame_interval : float, optional
        Sampling period in seconds. Overrides ``frame_step`` when given.
    frame_indices : list[int], optional
        Explicit set of frame indices to read (sparse / random access).
        When provided, range parameters are ignored.
    frame_times : list[float], optional
        Same as ``frame_indices`` but in seconds; converted internally.
    backend : str, optional
        ``"auto"`` (default), ``"vidgear"``, ``"pyav"``, or ``"ffmpeg-pipe"``.
    hwaccel : str, optional
        Hardware-accelerated decoder. Default ``None``. Pass ``"auto"`` to
        enable platform-appropriate accel (``"videotoolbox"`` on macOS,
        ``"cuda"`` on Linux+NVIDIA), or an explicit value. Honored only
        by ``pyav`` and ``ffmpeg-pipe``. For ``destination="torch"``
        with a GPU device, ``"auto"`` is enabled by default since the
        wall-time penalty observed on numpy-destination cells doesn't
        apply (the frames go through one numpy stack and then host→device
        in one shot — see SPEED_ANALYSIS.md).
    http_headers : dict[str, str], optional
        HTTP headers forwarded to the underlying decoder. Required for
        URLs that need a specific ``User-Agent`` / ``Referer`` / ``Cookie``
        / ``Authorization`` — e.g. yt-dlp-resolved YouTube live streams,
        members-only / age-gated content, Vimeo private videos, Twitch.
        Joined into ffmpeg's ``-headers`` CRLF string under the hood.
        Honored by ``pyav`` and ``ffmpeg-pipe``; the ``vidgear`` backend
        logs a warning and ignores them (OpenCV's HTTP layer doesn't
        surface headers cleanly).
    output_width, output_height : int, optional
        Exact output frame size in pixels. Behavior:

        - **Both** set → scale-fit (aspect-preserving) then pad with
          ``pad_color`` so the output is exactly ``output_width × output_height``.
          Typical for ML pipelines that need a fixed input shape.
        - **Only one** set → scale to that dimension preserving aspect
          ratio; the other dimension is derived. No padding.
        - **Neither** set (default) → frame keeps its native dimensions.

        The transform runs in numpy via ``cv2.resize`` + ``cv2.copyMakeBorder``
        post-decode. Same behavior across all backends (vidgear / pyav /
        ffmpeg-pipe).
    pad_color : str, optional
        Padding color when scale-fit-and-pad applies (i.e. both
        ``output_width`` and ``output_height`` are set, and the source's
        aspect ratio differs from the target). Accepts:

        - common names: ``"black"`` (default), ``"white"``, ``"red"``,
          ``"green"``, ``"blue"``, ``"yellow"``, ``"cyan"``, ``"magenta"``,
          ``"gray"`` / ``"grey"``
        - ``"#RRGGBB"`` hex
        - ``"transparent"`` raises ``ValueError`` in v1.5.0 — it would
          require 4-channel BGRA output, breaking the ``(H, W, 3)``
          contract. Planned for v1.6.0.
    destination : str, optional
        Where frames land. Default ``"numpy"``.

        - ``"numpy"`` — **BGR uint8** ``np.ndarray`` in OpenCV's
          channels-last layout.
        - ``"torch"`` — **RGB uint8** ``torch.Tensor`` in PyTorch's
          channels-first layout. PyTorch imported lazily.
        - ``"pil"`` — ``PIL.Image.Image`` (mode ``"RGB"``, ``size=(W, H)``
          per Pillow convention). Pillow imported lazily.
          ``batch_size`` not supported (Pillow has no batched type).

        See the layout table for exact shapes.
    device : str, optional
        Target device when ``destination="torch"``. ``"cpu"`` (default),
        ``"mps"`` (Apple Silicon), ``"cuda"`` (NVIDIA), or ``"auto"``
        (cuda > mps > cpu). Ignored when ``destination="numpy"``.
    batch_size : int, optional
        If provided, yield a batched tensor / array per batch instead of
        one frame at a time. The last batch may be smaller. Strongly
        recommended with ``destination="torch"`` + GPU device: one
        host→device transfer per batch instead of one per frame
        (typical 5-20× win).
    layout : str, optional
        Axis convention for **batched** yields (ignored when
        ``batch_size`` is None and for ``destination="pil"``).
        ``"image"`` (default) — each batch is a stack of independent
        images; ``"video"`` — each batch is a video clip with a time
        axis.

        Concrete shapes per (destination, layout, batch_size):

        ============ ============== ============= ===========================================
        destination  layout         batch_size    yield
        ============ ============== ============= ===========================================
        ``"numpy"``  any            None          ``(H, W, 3)``      HWC, BGR uint8
        ``"numpy"``  ``"image"``    N             ``(N, H, W, 3)``   NHWC, BGR uint8
        ``"numpy"``  ``"video"``    N             ``(N, H, W, 3)``   THWC, BGR uint8 (same mem; T == N)
        ``"torch"``  any            None          ``(3, H, W)``      CHW, RGB uint8
        ``"torch"``  ``"image"``    N             ``(N, 3, H, W)``   NCHW, RGB uint8 (batch of images)
        ``"torch"``  ``"video"``    N             ``(3, N, H, W)``   CTHW, RGB uint8 (video clip; T == N)
        ``"pil"``    n/a            **forbidden** ``PIL.Image``      mode=``"RGB"``, size=``(W, H)``
        ============ ============== ============= ===========================================

    Yields
    ------
    numpy.ndarray
        Successive frames as ``(H, W, 3)`` BGR uint8 arrays — same
        convention as OpenCV and the previous VidGear-only implementation.

    Examples
    --------
    >>> # Sequential time range — dispatcher picks PyAV (windowed)
    >>> for frame in extract_frames("clip.mp4", start_instant=10, end_instant=20, frame_step=5):
    ...     process(frame)

    >>> # Sparse access at specific times — routed to PyAV
    >>> list(extract_frames("clip.mp4", frame_times=[1.5, 12.0, 47.0]))

    >>> # Stream as torch tensors on Apple Silicon, batched for one transfer per 32 frames
    >>> for batch in extract_frames("clip.mp4",
    ...                             destination="torch", device="mps", batch_size=32):
    ...     # batch.shape == (N, H, W, 3); N == 32 for all but the last batch
    ...     model(batch)
    """
    assert is_valid_video_file(video_path), f"Video file not okay:\n\t{video_path}"

    d = video_dimensions(video_path)
    duration = d["duration"]
    frame_rate = d["frame_rate"]
    width = d["width"]
    height = d["height"]
    total_frames = int(duration * frame_rate)

    indices, s_idx, e_idx, step, sparse = _resolve_indices(
        duration=duration,
        frame_rate=frame_rate,
        start_index=start_index,
        end_index=end_index,
        start_instant=start_instant,
        end_instant=end_instant,
        frame_step=frame_step,
        frame_interval=frame_interval,
        frame_indices=frame_indices,
        frame_times=frame_times,
    )

    # "Full sequential" = start at 0, end at (or past) the last frame,
    # step 1 — the regime where VidGear's threaded AVFoundation pipeline
    # beats PyAV by ~4× at ≤720p on macOS (see SPEED_ANALYSIS.md). PyAV
    # catches up and wins at 1080p+; we keep the rule simple here.
    full_sequential = (
        not sparse
        and s_idx == 0
        and e_idx >= total_frames - 1
        and step == 1
    )

    # For destination="torch" with a GPU device, PyAV is the right backend
    # (only one with hwaccel, and the dispatcher should never pick vidgear
    # for a GPU-destined pipeline since vidgear can't be hardware-accelerated).
    torch_gpu = destination == "torch" and device in ("mps", "cuda", "auto")
    if torch_gpu and backend == "auto":
        backend = "pyav"
        if hwaccel is None:
            # For the torch+GPU destination, hwaccel auto-enables: the
            # per-frame numpy materialisation is unavoidable today, but
            # the batched torch path makes the offloaded decode worth it.
            hwaccel = "auto"

    chosen = _choose_backend(
        backend=backend, stabilize=stabilize, sparse=sparse, full_sequential=full_sequential,
    )
    resolved_hwaccel = _resolve_hwaccel(hwaccel) if chosen in ("pyav", "ffmpeg-pipe") else None

    logging.debug(
        "extract_frames: backend=%s hwaccel=%s sparse=%s full_seq=%s range=[%s,%s] step=%s "
        "destination=%s device=%s batch_size=%s",
        chosen, resolved_hwaccel, sparse, full_sequential, s_idx, e_idx, step,
        destination, device, batch_size,
    )

    if chosen == "vidgear":
        if http_headers:
            logging.warning(
                "vidgear backend ignores http_headers — OpenCV doesn't surface "
                "them cleanly. Auth-protected URLs (YouTube live, members-only, "
                "age-gated content from yt-helper) will likely 403. Use "
                "backend='pyav' or 'ffmpeg-pipe' for those."
            )
        np_iter = _extract_via_vidgear(video_path, s_idx, e_idx, step, stabilize)
    elif chosen == "pyav":
        if not _have_pyav():
            raise ImportError(
                "backend='pyav' requires PyAV. Install with: pip install 'video-helper[pyav]'"
            )
        np_iter = _extract_via_pyav(
            video_path, s_idx, e_idx, step, indices, frame_rate, resolved_hwaccel,
            http_headers=http_headers,
        )
    elif chosen == "ffmpeg-pipe":
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("backend='ffmpeg-pipe' requires ffmpeg on PATH")
        if sparse:
            raise ValueError(
                "backend='ffmpeg-pipe' does not support sparse access; "
                "use backend='pyav' instead."
            )
        np_iter = _extract_via_ffmpeg_pipe(
            video_path, s_idx, e_idx, step, frame_rate, width, height, resolved_hwaccel,
            http_headers=http_headers,
        )
    else:
        raise AssertionError(f"unreachable backend {chosen!r}")

    # Optional resize + pad pass — validate early so we fail fast.
    if output_width is not None or output_height is not None:
        if output_width is not None and output_width <= 0:
            raise ValueError(f"output_width must be > 0, got {output_width}")
        if output_height is not None and output_height <= 0:
            raise ValueError(f"output_height must be > 0, got {output_height}")
        pad_bgr = _parse_pad_color(pad_color)

        def _resize_pad_iter(src):
            for frame in src:
                yield _apply_output_transform(frame, output_width, output_height, pad_bgr)
        np_iter = _resize_pad_iter(np_iter)

    # Final stage: convert/batch into the requested destination form.
    # The fast-path destination="numpy" + batch_size=None is a no-op
    # pass-through (no extra copy, no stacking).
    yield from _to_destination(np_iter, destination, device, batch_size, layout)


def dump_frames(frames_list: List[np.ndarray], output_movie: str, fps: int = 30) -> None:
    """
    Save frames to a video file.

    Parameters
    ----------
    frames_list : List[np.ndarray]
        A list of frames as numpy arrays.
    output_movie : str
        Path to the output video file.
    fps : int, optional
        Frame rate of the output video file. Defaults to 30.

    Notes
    -----
    The function uses VidGear to write the frames to a video file.

    Usage
    -----
    >>> frames = [frame1, frame2, frame3]
    >>> dump_frames(frames, "output.mp4")
    """
    assert len(frames_list) > 0, "No frames to dump!"

    height, width, channels = frames_list[0].shape
    assert all(frame.shape == (height, width, channels) for frame in frames_list), "Frames do not have consistent dimensions!"

    _, _, output_ext = osh.folder_name_ext(output_movie)
    quiet = osh.verbosity() <= 0

    with osh.temporary_folder() as temp_folder:
        try:
            frame_pattern = osh.join([temp_folder, "frame_%09d.png"])
            for i, frame in enumerate(frames_list):
                frame_path = frame_pattern % i
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) # BGR convention of opencv
                cv2.imwrite(frame_path, frame_bgr)

            temp_movie = osh.join([temp_folder, "temp_movie.mp4"])
            ffmpeg.input(frame_pattern, framerate=fps).output(temp_movie).run(overwrite_output=True, quiet=quiet)

            if output_ext.lower() != "mp4":
                ffmpeg.input(temp_movie).output(output_movie, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
            else:
                osh.copyfile(temp_movie, output_movie)

        except Exception as e:
            raise Exception(f"Error occurred while dumping frames to video: {e}")

    logging.info(f"Video saved successfully: {output_movie}")



def extract_video_chunk(input_video: str, sample_start: float, sample_end: float, output_video: str) -> None:
    """
    Extract a chunk of video from the specified start to end time and save it to a new file.

    Parameters
    ----------
    input_video : str
        Path to the input video file.
    sample_start : float
        Start time in seconds for the extraction.
    sample_end : float
        End time in seconds for the extraction.
    output_video : str
        Path to save the extracted video chunk.

    Usage
    -----
    >>> extract_video_chunk("input.mp4", 10.0, 20.0, "output_chunk.mp4")
    """
    assert is_valid_video_file(input_video), f"Video file not okay:\n\t{input_video}"
    metadata = video_dimensions(input_video)
    duration = metadata["duration"]
    assert sample_end>sample_start and duration >= sample_end and duration > sample_start, f"Temporal crop is inconsistent (start: {sample_start}, end: {sample_end}, duration: {duration})"

    _, _, input_ext = osh.folder_name_ext(input_video)
    _, _, output_ext = osh.folder_name_ext(output_video)

    quiet = True


    with osh.temporary_filename(suffix=".mp4", mode="wb") as temp_input, \
         osh.temporary_filename(suffix=".mp4", mode="wb") as temp_output:

        # Normalize the input into an .mp4 container before the temporal
        # cut. Codec-copy only works when source codecs are already
        # MP4-compatible (h264 + aac); for arbitrary inputs we transcode
        # to H.264/AAC, which every MP4-class container accepts.
        if input_ext.lower() != "mp4":
            ffmpeg.input(input_video).output(
                temp_input, vcodec='libx264', acodec='aac', pix_fmt='yuv420p',
            ).run(overwrite_output=True, quiet=quiet)
        else:
            osh.copyfile(input_video, temp_input)  # Direct copy if already MP4

        # Actually do the temporal selection
        ffmpeg.input(temp_input, ss=sample_start, to=sample_end).output(temp_output).run(overwrite_output=True)

        # If the output format is not MP4, perform final conversion
        if output_ext.lower() != "mp4":
            ffmpeg.input(temp_output).output(output_video, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
        else:
            osh.copyfile(temp_output, output_video)  # Copy to final output if MP4

    if is_valid_video_file(output_video):
        logging.info(f"Video chunk extracted successfully:\n\t{output_video}")
    else:
        raise RuntimeError(
            f"Video could not be cropped (original: {input_video}, "
            f"start: {sample_start}, end: {sample_end}, duration: {duration})"
        )

# ──────────────────────────────────────────────────────────────────────────
#  Pipeline helpers — composition primitives shared by video editors that
#  need to glue clips, generate stand-ins (solid color, looped still),
#  overlay graphics with time-varying expressions, burn subtitles, mux a
#  voice track, or read a duration without re-implementing ffprobe glue.
# ──────────────────────────────────────────────────────────────────────────


def video_duration(input_video: str) -> float:
    """
    Return the duration (seconds) of a video file.

    Parameters
    ----------
    input_video : str
        Path to the input video file.

    Returns
    -------
    float
        Duration in seconds.

    Notes
    -----
    Mirror of ``audio_helper.get_audio_duration`` for the video side.
    Uses ``video_dimensions`` under the hood, which already calls
    ``ffmpeg.probe`` — kept as a top-level convenience so callers don't
    have to remember the dict key.

    Examples
    --------
    >>> video_duration("clip.mp4")
    12.34
    """
    osh.checkfile(input_video, msg=f"Video file not found: {input_video}")
    return float(video_dimensions(input_video)["duration"])


def black_video(
    duration: float,
    width: int,
    height: int,
    output_video: str,
    frame_rate: int = 30,
) -> None:
    """
    Generate a silent solid-black video of ``duration`` seconds.

    Parameters
    ----------
    duration : float
        Output duration in seconds.
    width : int
        Output frame width in pixels (rounded down to even — H.264 yuv420p
        requires even dimensions).
    height : int
        Output frame height in pixels (rounded down to even).
    output_video : str
        Path to the output video file (.mp4 recommended).
    frame_rate : int, optional
        Output frame rate (default 30).

    Notes
    -----
    Useful as a "buffer" / breathing clip between two visuals in a montage,
    or as a placeholder when an asset is missing. Encoded as H.264 yuv420p
    with no audio track.

    Examples
    --------
    >>> black_video(0.5, 1920, 1080, "buffer.mp4")
    """
    assert duration > 0, f"black_video duration must be > 0, got {duration}"
    assert width > 0 and height > 0, f"black_video needs positive dims, got {width}x{height}"
    if width % 2: width -= 1
    if height % 2: height -= 1
    quiet = osh.verbosity() <= 0

    (
        ffmpeg
        .input(f"color=c=black:s={width}x{height}:r={frame_rate}",
               f="lavfi", t=duration)
        .output(output_video, vcodec="libx264", pix_fmt="yuv420p",
                preset="medium", crf=20, an=None)
        .run(overwrite_output=True, quiet=quiet)
    )
    assert is_valid_video_file(output_video), \
        f"Failed to write black_video:\n\t{output_video}"


def image_loop_to_video(
    image: str,
    duration: float,
    output_video: str,
    frame_rate: int = 30,
    width: int = None,
    height: int = None,
) -> None:
    """
    Loop a still image for ``duration`` seconds into a silent video.

    Parameters
    ----------
    image : str
        Path to the input still (PNG, JPG, …).
    duration : float
        Output duration in seconds.
    output_video : str
        Path to the output video file (.mp4 recommended).
    frame_rate : int, optional
        Output frame rate (default 30).
    width, height : int, optional
        If both provided, the image is letterboxed (scale + pad with black)
        to the target viewport. Width and height are rounded down to even.

    Notes
    -----
    Common in title cards, screenshot scenes, slide-style montages.
    Encoded as H.264 yuv420p with no audio track.

    Examples
    --------
    >>> image_loop_to_video("title.png", 3.0, "title.mp4",
    ...                     width=1920, height=1080)
    """
    osh.checkfile(image, msg=f"Image not found: {image}")
    assert duration > 0, f"image_loop_to_video duration must be > 0, got {duration}"
    quiet = osh.verbosity() <= 0

    stream = ffmpeg.input(image, loop=1, framerate=frame_rate, t=duration)
    out_kwargs = {
        "vcodec": "libx264", "pix_fmt": "yuv420p",
        "preset": "medium", "crf": 20, "an": None,
        "t": duration,
    }
    if width and height:
        if width % 2: width -= 1
        if height % 2: height -= 1
        out_kwargs["vf"] = (
            f"scale='min({width},iw*{height}/ih):min({height},ih*{width}/iw)',"
            f"pad='{width}:{height}:(ow-iw)/2:(oh-ih)/2:black',"
            f"format=yuv420p,fps={frame_rate}"
        )
    elif width:
        if width % 2: width -= 1
        out_kwargs["vf"] = f"scale={width}:-1,format=yuv420p,fps={frame_rate}"
    elif height:
        if height % 2: height -= 1
        out_kwargs["vf"] = f"scale=-1:{height},format=yuv420p,fps={frame_rate}"
    else:
        out_kwargs["vf"] = f"format=yuv420p,fps={frame_rate}"

    stream.output(output_video, **out_kwargs).run(overwrite_output=True, quiet=quiet)
    assert is_valid_video_file(output_video), \
        f"Failed to write image_loop_to_video:\n\t{output_video}"


def concat_videos(
    input_videos: List[str],
    output_video: str,
    reencode: bool = True,
    frame_rate: int = None,
) -> None:
    """
    Concatenate ``input_videos`` end-to-end into ``output_video``.

    Parameters
    ----------
    input_videos : List[str]
        Ordered list of input video paths.
    output_video : str
        Path to the output video file (.mp4 recommended).
    reencode : bool, optional
        Whether to re-encode (libx264). Default ``True`` — strongly
        recommended when the inputs come from different sources, since
        the concat demuxer's stream-copy path requires identical codec,
        timebase, frame rate and resolution; mismatched inputs produce
        audio/video drift or hard ffmpeg errors. Set ``False`` only when
        the inputs are guaranteed bit-identical containers.
    frame_rate : int, optional
        Force this output frame rate (only used when ``reencode=True``).

    Notes
    -----
    Uses the ffmpeg ``concat`` *demuxer* (text manifest) which is the
    only correct way to concatenate variable-length clips end-to-end
    without re-timing artefacts. The temporary manifest is written to a
    process-temp file and removed automatically.

    Examples
    --------
    >>> concat_videos(["intro.mp4", "body.mp4", "outro.mp4"], "final.mp4")
    """
    assert len(input_videos) > 0, "concat_videos: empty input list"
    for v in input_videos:
        osh.checkfile(v, msg=f"Input video not found: {v}")
    quiet = osh.verbosity() <= 0

    with osh.temporary_filename(suffix=".txt", mode="w") as manifest:
        with open(manifest, "w") as fh:
            for v in input_videos:
                # ffmpeg concat demuxer: single-quote the path, escape inner quotes
                p = os.path.abspath(v).replace("'", r"'\''")
                fh.write(f"file '{p}'\n")

        stream = ffmpeg.input(manifest, format="concat", safe=0)
        out_kwargs = {}
        if reencode:
            out_kwargs.update({
                "vcodec": "libx264", "pix_fmt": "yuv420p",
                "preset": "medium", "crf": 20, "an": None,
            })
            if frame_rate:
                out_kwargs["r"] = frame_rate
        else:
            out_kwargs.update({"vcodec": "copy", "acodec": "copy"})

        stream.output(output_video, **out_kwargs).run(
            overwrite_output=True, quiet=quiet,
        )

    assert is_valid_video_file(output_video), \
        f"Failed to write concat_videos:\n\t{output_video}"


def overlay_image(
    input_video: str,
    image: str,
    output_video: str,
    x: str = "0",
    y: str = "0",
    scale_width: int = None,
) -> None:
    """
    Overlay a still image (PNG with alpha works) on top of a video.

    Parameters
    ----------
    input_video : str
        Path to the base video.
    image : str
        Path to the overlay image (PNG with alpha is the typical case —
        cursors, watermarks, logos).
    output_video : str
        Path to the output video file (.mp4 recommended).
    x, y : str, optional
        Overlay positions. Plain integers (``"10"``) place the image
        statically; ffmpeg overlay expressions (``"if(lt(t,1.0),0,100)"``,
        ``"W/2-w/2"``, …) move the overlay over time. Default ``"0"``,
        ``"0"`` (top-left).
    scale_width : int, optional
        If provided, scale the overlay to this width keeping aspect ratio
        — useful for cursor PNGs that come at a different size than the
        target frame.

    Notes
    -----
    Time-varying expressions are evaluated per-frame
    (``eval=frame``) so animations stay smooth at any framerate. The
    underlying video stream is re-encoded (libx264) and the original
    audio track, if any, is preserved.

    Examples
    --------
    >>> overlay_image("clip.mp4", "cursor.png", "out.mp4",
    ...               x="if(lt(t,2),100,400)", y="200",
    ...               scale_width=24)
    """
    osh.checkfile(input_video, msg=f"Input video not found: {input_video}")
    osh.checkfile(image, msg=f"Overlay image not found: {image}")
    quiet = osh.verbosity() <= 0

    in_v = ffmpeg.input(input_video)
    in_img = ffmpeg.input(image)
    if scale_width:
        in_img = in_img.filter("scale", scale_width, -1)
    overlaid = ffmpeg.overlay(in_v.video, in_img,
                              x=x, y=y, eval="frame", format="auto")

    out_kwargs = {"vcodec": "libx264", "pix_fmt": "yuv420p",
                  "preset": "medium", "crf": 20}
    # Preserve the original audio stream if present (probe lazily).
    has_audio = video_dimensions(input_video).get("has_sound", False)
    if has_audio:
        out = ffmpeg.output(overlaid, in_v.audio, output_video,
                            acodec="copy", **out_kwargs)
    else:
        out = ffmpeg.output(overlaid, output_video, an=None, **out_kwargs)
    out.run(overwrite_output=True, quiet=quiet)
    assert is_valid_video_file(output_video), \
        f"Failed to write overlay_image:\n\t{output_video}"


def extract_audio_track(
    input_video: str,
    output_audio: str,
    sample_rate: int = 44100,
    channels: int = 2,
    encoding: str = "pcm_s16le",
) -> None:
    """
    Extract the audio track of a video file into a standalone audio file.

    Parameters
    ----------
    input_video : str
        Path to the input video file (any container ffmpeg can read).
    output_audio : str
        Path to the output audio file. The extension picks the container;
        ``.wav`` pairs naturally with ``encoding="pcm_s16le"`` for a
        lossless extract.
    sample_rate : int, optional
        Output sample rate in Hz (default 44100).
    channels : int, optional
        Output channel count (default 2 — stereo). Use ``1`` for mono.
    encoding : str, optional
        Audio codec (default ``"pcm_s16le"``). For non-WAV outputs use
        a codec compatible with the container (e.g. ``"aac"`` for .m4a,
        ``"libmp3lame"`` for .mp3).

    Notes
    -----
    Source-of-truth companion to ``audio_helper.sound_converter`` for the
    case where the *input* is a video — ``sound_converter`` rejects
    video extensions in its input-validation pass, hence the dedicated
    function here. Drops the video stream (``-vn``) and re-encodes only
    the audio.

    Examples
    --------
    >>> extract_audio_track("interview.mp4", "interview.wav")
    >>> extract_audio_track("clip.mov", "clip.mp3",
    ...                     encoding="libmp3lame", sample_rate=22050)
    """
    osh.checkfile(input_video, msg=f"Input video not found: {input_video}")
    assert is_valid_video_file(input_video), \
        f"Invalid input video file: {input_video}"
    quiet = osh.verbosity() <= 0

    ffmpeg.input(input_video).output(
        output_audio,
        vn=None,                # drop the video stream
        ac=channels,
        ar=sample_rate,
        acodec=encoding,
    ).run(overwrite_output=True, quiet=quiet)

    osh.checkfile(
        output_audio,
        msg=f"Failed to extract audio: {output_audio}",
    )


def mux_audio_video(
    input_video: str,
    input_audio: str,
    output_video: str,
    audio_codec: str = "aac",
    audio_bitrate: str = "192k",
    shortest: bool = False,
) -> None:
    """
    Mux a separate audio track onto a (typically silent) video.

    Parameters
    ----------
    input_video : str
        Path to the video file. Any existing audio track is replaced.
    input_audio : str
        Path to the audio file (WAV, MP3, AAC, …).
    output_video : str
        Path to the output video file (.mp4 recommended).
    audio_codec : str, optional
        Audio codec for the output stream (default ``"aac"``). Use
        ``"copy"`` if the input audio is already in a container-compatible
        codec.
    audio_bitrate : str, optional
        Audio bitrate when re-encoding (default ``"192k"``); ignored when
        ``audio_codec="copy"``.
    shortest : bool, optional
        If ``True``, the output stops when the shorter of the two streams
        ends. If ``False`` (default), the output keeps the video length and
        the audio is padded with silence (or truncated) by the muxer.

    Notes
    -----
    Video stream is copied — no re-encoding — so the muxing is fast and
    lossless on the video side. Use this after assembling a silent
    ``visuals.mp4`` and a separate ``narration.wav`` track.

    Examples
    --------
    >>> mux_audio_video("silent.mp4", "voice.wav", "final.mp4")
    """
    osh.checkfile(input_video, msg=f"Input video not found: {input_video}")
    osh.checkfile(input_audio, msg=f"Input audio not found: {input_audio}")
    quiet = osh.verbosity() <= 0

    in_v = ffmpeg.input(input_video)
    in_a = ffmpeg.input(input_audio)
    out_kwargs = {"vcodec": "copy", "acodec": audio_codec}
    if audio_codec != "copy":
        out_kwargs["audio_bitrate"] = audio_bitrate
    if shortest:
        out_kwargs["shortest"] = None
    ffmpeg.output(in_v.video, in_a.audio, output_video, **out_kwargs).run(
        overwrite_output=True, quiet=quiet,
    )
    assert is_valid_video_file(output_video), \
        f"Failed to write mux_audio_video:\n\t{output_video}"


def burn_subtitles(
    input_video: str,
    subtitles_file: str,
    output_video: str,
    force_style: str = None,
) -> None:
    """
    Burn subtitles from an .srt / .vtt / .ass file into the video frames.

    Parameters
    ----------
    input_video : str
        Path to the input video file.
    subtitles_file : str
        Path to a subtitles file in one of the formats libass understands:

        * **.srt** — plain SubRip. Renders in the libass default style;
          ``<font color="…">`` tags are honored.
        * **.vtt** — WebVTT. Cue-class colors (``<c.red>…</c>``) and any
          inline ``::cue`` rules from a ``STYLE`` block are honored.
          The companion ``srt2vtt()`` writes both pieces in one shot.
        * **.ass** / **.ssa** — Advanced SubStation Alpha. All
          per-cue formatting (font, color, outline, position) is
          honored as authored.

    output_video : str
        Path to the output video file (.mp4 recommended).
    force_style : str, optional
        ASS-style override forwarded to the ``subtitles`` filter's
        ``force_style`` argument — e.g.
        ``"FontName=Helvetica,FontSize=24,PrimaryColour=&H00FFFFFF&"``.
        Useful for SRT (which has no native styling) or to override a
        global property of a VTT/ASS file without editing it. Per-cue
        colors from VTT/ASS still win against ``force_style`` keys they
        explicitly set.

    Notes
    -----
    A single backend (libass through ffmpeg's ``subtitles`` filter)
    handles all three formats, so there is no need for separate
    ``burn_srt`` / ``burn_vtt`` / ``burn_ass`` functions. The filter
    mounts the file by path; we escape ``:`` to ``\\:`` and ``'`` to
    ``\\'`` so absolute paths on macOS / Windows behave. Video is
    re-encoded (the filter rewrites every frame), audio is copied if
    present.

    Examples
    --------
    Plain SRT, default style:

    >>> burn_subtitles("clip.mp4", "subs.srt", "captioned.mp4")

    Colored WebVTT (cue classes carry their own colors):

    >>> burn_subtitles("clip.mp4", "subs.vtt", "captioned.mp4")

    Force a font + size on top of any source format:

    >>> burn_subtitles("clip.mp4", "subs.vtt", "captioned.mp4",
    ...                force_style="FontName=Helvetica,FontSize=28,Outline=2")
    """
    osh.checkfile(input_video, msg=f"Input video not found: {input_video}")
    osh.checkfile(subtitles_file,
                  msg=f"Subtitles file not found: {subtitles_file}")
    quiet = osh.verbosity() <= 0

    # Check the obvious user error first (wrong file format) so callers on a
    # libass-less ffmpeg still get a clear ValueError on a bogus path instead
    # of the generic "libass missing" RuntimeError.
    _, _, ext = osh.folder_name_ext(subtitles_file)
    if ext.lower() not in {"srt", "vtt", "ass", "ssa"}:
        raise ValueError(
            f"burn_subtitles only accepts .srt / .vtt / .ass / .ssa "
            f"(got .{ext}). For other formats, convert first — e.g. "
            f"srt2vtt() in this same module."
        )

    # The `subtitles` filter is provided by libass — ffmpeg builds without
    # `--enable-libass` (some Homebrew formulae, minimal docker images, …)
    # silently lack it and produce a cryptic "Error parsing filterchain".
    # Fail fast with an actionable error instead.
    import subprocess as _sp
    _filters = _sp.run(["ffmpeg", "-hide_banner", "-filters"],
                       capture_output=True, text=True, check=False).stdout
    if "subtitles" not in _filters:
        raise RuntimeError(
            "ffmpeg has no `subtitles` filter (libass missing). Rebuild "
            "ffmpeg with `--enable-libass`, or on macOS: "
            "`brew uninstall ffmpeg && brew install ffmpeg --HEAD` "
            "(homebrew-core's bottle ships without libass on some archs)."
        )

    # Escape special chars for the subtitles filter — colons mainly, also
    # backslashes and single quotes. Order matters: backslash first.
    subs_abs = os.path.abspath(subtitles_file)
    subs_esc = (subs_abs
                .replace("\\", "\\\\")
                .replace(":", r"\:")
                .replace("'", r"\'"))

    vf = f"subtitles='{subs_esc}'"
    if not osh.emptystring(force_style):
        vf += f":force_style='{force_style}'"

    in_stream = ffmpeg.input(input_video)
    has_audio = video_dimensions(input_video).get("has_sound", False)
    out_kwargs = {"vcodec": "libx264", "pix_fmt": "yuv420p",
                  "preset": "medium", "crf": 20, "vf": vf}
    if has_audio:
        out_kwargs["acodec"] = "copy"
    else:
        out_kwargs["an"] = None
    in_stream.output(output_video, **out_kwargs).run(
        overwrite_output=True, quiet=quiet,
    )
    assert is_valid_video_file(output_video), \
        f"Failed to write burn_subtitles:\n\t{output_video}"
