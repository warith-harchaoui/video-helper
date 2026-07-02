"""
Video Helper — argparse-based command-line interface.

Thin wrapper around the pure functions in :mod:`video_helper.main` that
exposes the whole toolkit as subcommands under a single ``video-helper``
entry point. Written with :mod:`argparse` from the standard library so
the CLI works out of the box on any Python install that has the package
installed — no extra dependency required.

Subcommands
-----------
- ``validate``      — probe a video file / URL for validity (boolean)
- ``dimensions``    — dump width/height/duration/frame_rate/has_sound as JSON
- ``duration``      — print the duration in seconds of a video
- ``convert``       — re-encode / resize / drop audio
- ``chunk``         — extract a ``[start, end]`` slice
- ``black``         — synthesize a silent solid-black clip
- ``image-loop``    — loop a still image into a silent clip
- ``concat``        — concatenate several videos head-to-tail
- ``overlay``       — overlay a still image on a video (watermark / cursor)
- ``extract-audio`` — dump the audio track of a video
- ``mux-audio``     — mux a separate audio track onto a video
- ``burn-subs``     — burn ``.srt`` / ``.vtt`` / ``.ass`` into the frames
- ``srt2vtt``       — SRT → WebVTT with color-preserving CSS
- ``extract-frames``— stream frames to disk (one PNG per sampled frame)

Usage Example
-------------
>>> #   video-helper validate      --input clip.mp4
>>> #   video-helper dimensions    --input clip.mp4
>>> #   video-helper duration      --input clip.mp4
>>> #   video-helper convert       --input in.mov --output out.mp4 --width 640 --height 480
>>> #   video-helper chunk         --input in.mp4 --start 10 --end 20 --output cut.mp4
>>> #   video-helper black         --duration 3 --width 1920 --height 1080 --output buffer.mp4
>>> #   video-helper image-loop    --image title.png --duration 4 --output title.mp4 --width 1920 --height 1080
>>> #   video-helper concat        --inputs a.mp4 b.mp4 c.mp4 --output final.mp4
>>> #   video-helper overlay       --input clip.mp4 --image logo.png --output watermarked.mp4 --x 10 --y 10
>>> #   video-helper extract-audio --input clip.mp4 --output audio.wav
>>> #   video-helper mux-audio     --input silent.mp4 --audio voice.wav --output final.mp4
>>> #   video-helper burn-subs     --input clip.mp4 --subs subs.srt --output captioned.mp4
>>> #   video-helper srt2vtt       --input subs.srt
>>> #   video-helper extract-frames --input clip.mp4 --output-dir frames/ --frame-step 5

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Sequence

# Import the pure functions once here — every subcommand is a thin dispatch
# on top of these, no logic duplication.
from . import (
    black_video,
    burn_subtitles,
    concat_videos,
    dump_frames,
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
# Subcommand handlers
#
# Each handler receives the parsed ``argparse.Namespace`` and returns a
# process exit code (``0`` on success). Handlers stay short: they translate
# CLI arguments into keyword arguments for the underlying library function,
# print a machine-friendly result (JSON for structured outputs, plain path
# for single-file outputs), and let exceptions propagate as non-zero exit
# codes.
# ---------------------------------------------------------------------------


def _handle_validate(ns: argparse.Namespace) -> int:
    # is_valid_video_file returns bool; emit lowercase JSON so the exit
    # code matches shell expectations (0 = ok, 1 = invalid) but stdout
    # still carries a machine-friendly value.
    ok = is_valid_video_file(ns.input)
    print("true" if ok else "false")
    return 0 if ok else 1


def _handle_dimensions(ns: argparse.Namespace) -> int:
    # video_dimensions returns a dict — pass http_headers through when
    # the input is a URL (e.g. yt-dlp-resolved streams that need cookies).
    headers = _parse_headers(ns.header) if ns.header else None
    info = video_dimensions(ns.input, http_headers=headers)
    print(json.dumps(info, indent=2))
    return 0


def _handle_duration(ns: argparse.Namespace) -> int:
    # video_duration returns a float in seconds.
    print(f"{video_duration(ns.input):.6f}")
    return 0


def _handle_convert(ns: argparse.Namespace) -> int:
    # video_converter re-encodes / resizes / drops audio in one pass.
    video_converter(
        input_video=ns.input,
        output_video=ns.output,
        frame_rate=ns.frame_rate,
        width=ns.width,
        height=ns.height,
        without_sound=ns.without_sound,
    )
    print(ns.output)
    return 0


def _handle_chunk(ns: argparse.Namespace) -> int:
    # extract_video_chunk cuts a [start, end] slice into a new file.
    extract_video_chunk(
        input_video=ns.input,
        sample_start=ns.start,
        sample_end=ns.end,
        output_video=ns.output,
    )
    print(ns.output)
    return 0


def _handle_black(ns: argparse.Namespace) -> int:
    # Silent solid-black clip — buffer / breathing shot in a montage.
    black_video(
        duration=ns.duration,
        width=ns.width,
        height=ns.height,
        output_video=ns.output,
        frame_rate=ns.frame_rate,
    )
    print(ns.output)
    return 0


def _handle_image_loop(ns: argparse.Namespace) -> int:
    # Loop a still image into a silent video — title-card / slide use case.
    image_loop_to_video(
        image=ns.image,
        duration=ns.duration,
        output_video=ns.output,
        frame_rate=ns.frame_rate,
        width=ns.width,
        height=ns.height,
    )
    print(ns.output)
    return 0


def _handle_concat(ns: argparse.Namespace) -> int:
    # concat_videos joins N files via ffmpeg's concat demuxer.
    concat_videos(
        input_videos=list(ns.inputs),
        output_video=ns.output,
        reencode=ns.reencode,
        frame_rate=ns.frame_rate,
    )
    print(ns.output)
    return 0


def _handle_overlay(ns: argparse.Namespace) -> int:
    # Overlay a still image (PNG with alpha typical) on the video.
    overlay_image(
        input_video=ns.input,
        image=ns.image,
        output_video=ns.output,
        x=ns.x,
        y=ns.y,
        scale_width=ns.scale_width,
    )
    print(ns.output)
    return 0


def _handle_extract_audio(ns: argparse.Namespace) -> int:
    # Dump the audio track of a video into a standalone audio file.
    extract_audio_track(
        input_video=ns.input,
        output_audio=ns.output,
        sample_rate=ns.sample_rate,
        channels=ns.channels,
        encoding=ns.encoding,
    )
    print(ns.output)
    return 0


def _handle_mux_audio(ns: argparse.Namespace) -> int:
    # Replace the video's audio track with a separate audio file.
    mux_audio_video(
        input_video=ns.input,
        input_audio=ns.audio,
        output_video=ns.output,
        audio_codec=ns.audio_codec,
        audio_bitrate=ns.audio_bitrate,
        shortest=ns.shortest,
    )
    print(ns.output)
    return 0


def _handle_burn_subs(ns: argparse.Namespace) -> int:
    # Burn subtitles into the video frames via libass.
    burn_subtitles(
        input_video=ns.input,
        subtitles_file=ns.subs,
        output_video=ns.output,
        force_style=ns.force_style,
    )
    print(ns.output)
    return 0


def _handle_srt2vtt(ns: argparse.Namespace) -> int:
    # SRT → WebVTT with color-preserving CSS sidecar.
    srt2vtt(
        srt_file_path=ns.input,
        vtt_file_path=ns.output,
        css_file_path=ns.css,
    )
    # srt2vtt writes both files without returning paths — emit the vtt path
    # (derived from stem when --output omitted) so pipelines can chain.
    if ns.output:
        print(ns.output)
    else:
        stem, _ = os.path.splitext(ns.input)
        print(stem + ".vtt")
    return 0


def _handle_extract_frames(ns: argparse.Namespace) -> int:
    # Stream frames to disk as PNGs. Frame indexing lets us name files
    # with a zero-padded counter that matches the sampled order.
    import cv2  # noqa: WPS433 — deferred so `--help` stays cheap

    os.makedirs(ns.output_dir, exist_ok=True)
    written: list[str] = []
    # We iterate lazily — extract_frames yields BGR uint8 numpy arrays
    # matching OpenCV's convention, so cv2.imwrite writes them verbatim.
    iterator = extract_frames(
        video_path=ns.input,
        frame_step=ns.frame_step,
        frame_interval=ns.frame_interval,
        start_instant=ns.start,
        end_instant=ns.end,
        backend=ns.backend,
    )
    for i, frame in enumerate(iterator):
        path = os.path.join(ns.output_dir, f"frame_{i:09d}.png")
        cv2.imwrite(path, frame)
        written.append(path)
    # Emit the manifest as JSON so downstream tools can pick up the file
    # list without re-scanning the directory.
    print(json.dumps({"frames": written, "count": len(written)}, indent=2))
    return 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_headers(pairs: Sequence[str]) -> dict:
    """Turn ``["User-Agent: X", "Referer: Y"]`` into a headers dict."""
    out: dict = {}
    for p in pairs:
        # Split only on the first ':' — header values may legitimately contain colons.
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        out[k.strip()] = v.strip()
    return out


# ---------------------------------------------------------------------------
# Parser construction
#
# One helper per subcommand keeps ``build_parser`` readable and lets the
# click twin (:mod:`video_helper.cli_click`) mirror the exact same flag
# names without any risk of drift.
# ---------------------------------------------------------------------------


def _add_validate(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("validate", help="Probe a video file / URL for validity.")
    p.add_argument("--input", required=True, help="Path or HTTP(S) URL to a video.")
    p.set_defaults(func=_handle_validate)


def _add_dimensions(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("dimensions", help="Emit width/height/duration/frame_rate/has_sound as JSON.")
    p.add_argument("--input", required=True, help="Path or HTTP(S) URL to a video.")
    p.add_argument(
        "--header",
        action="append",
        default=[],
        help='HTTP header as "Name: value" (repeat --header). Forwarded to ffprobe for URL inputs.',
    )
    p.set_defaults(func=_handle_dimensions)


def _add_duration(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("duration", help="Print the duration of a video, in seconds.")
    p.add_argument("--input", required=True, help="Path to a video file.")
    p.set_defaults(func=_handle_duration)


def _add_convert(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("convert", help="Re-encode / resize / drop audio in one pass.")
    p.add_argument("--input", required=True, help="Input video path.")
    p.add_argument("--output", required=True, help="Output video path.")
    p.add_argument("--frame-rate", type=int, default=None, dest="frame_rate", help="Target frame rate.")
    p.add_argument("--width", type=int, default=None, help="Target width in pixels.")
    p.add_argument("--height", type=int, default=None, help="Target height in pixels.")
    p.add_argument(
        "--without-sound",
        action="store_true",
        default=False,
        dest="without_sound",
        help="Drop the audio stream.",
    )
    p.set_defaults(func=_handle_convert)


def _add_chunk(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("chunk", help="Extract a [start, end] slice of a video.")
    p.add_argument("--input", required=True)
    p.add_argument("--start", type=float, required=True, help="Start time in seconds.")
    p.add_argument("--end", type=float, required=True, help="End time in seconds.")
    p.add_argument("--output", required=True, help="Output video path.")
    p.set_defaults(func=_handle_chunk)


def _add_black(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("black", help="Synthesize a silent solid-black clip.")
    p.add_argument("--duration", type=float, required=True, help="Duration in seconds.")
    p.add_argument("--width", type=int, required=True)
    p.add_argument("--height", type=int, required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--frame-rate", type=int, default=30, dest="frame_rate")
    p.set_defaults(func=_handle_black)


def _add_image_loop(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("image-loop", help="Loop a still image into a silent video.")
    p.add_argument("--image", required=True, help="Path to the input still (PNG / JPG / …).")
    p.add_argument("--duration", type=float, required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--frame-rate", type=int, default=30, dest="frame_rate")
    p.add_argument("--width", type=int, default=None, help="Letterbox target width.")
    p.add_argument("--height", type=int, default=None, help="Letterbox target height.")
    p.set_defaults(func=_handle_image_loop)


def _add_concat(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("concat", help="Concatenate several videos head-to-tail.")
    p.add_argument("--inputs", nargs="+", required=True, help="Videos, in order.")
    p.add_argument("--output", required=True)
    p.add_argument(
        "--reencode",
        action="store_true",
        default=True,
        help="Re-encode via libx264 (default; recommended for mixed sources).",
    )
    p.add_argument(
        "--no-reencode",
        dest="reencode",
        action="store_false",
        help="Stream-copy — inputs must be bit-identical containers.",
    )
    p.add_argument("--frame-rate", type=int, default=None, dest="frame_rate")
    p.set_defaults(func=_handle_concat)


def _add_overlay(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("overlay", help="Overlay a still image on a video.")
    p.add_argument("--input", required=True)
    p.add_argument("--image", required=True, help="Overlay image (PNG with alpha typical).")
    p.add_argument("--output", required=True)
    p.add_argument("--x", default="0", help='X position or ffmpeg overlay expression (default "0").')
    p.add_argument("--y", default="0", help='Y position or ffmpeg overlay expression (default "0").')
    p.add_argument("--scale-width", type=int, default=None, dest="scale_width", help="Scale overlay to this width.")
    p.set_defaults(func=_handle_overlay)


def _add_extract_audio(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("extract-audio", help="Dump the audio track of a video.")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True, help="Output audio path (extension picks the container).")
    p.add_argument("--sample-rate", type=int, default=44100, dest="sample_rate")
    p.add_argument("--channels", type=int, default=2, help="Channel count (default 2).")
    p.add_argument("--encoding", default="pcm_s16le", help="Audio codec (default pcm_s16le).")
    p.set_defaults(func=_handle_extract_audio)


def _add_mux_audio(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("mux-audio", help="Mux a separate audio track onto a video.")
    p.add_argument("--input", required=True, help="Video file (existing audio is replaced).")
    p.add_argument("--audio", required=True, help="Audio file.")
    p.add_argument("--output", required=True)
    p.add_argument("--audio-codec", default="aac", dest="audio_codec")
    p.add_argument("--audio-bitrate", default="192k", dest="audio_bitrate")
    p.add_argument(
        "--shortest",
        action="store_true",
        default=False,
        help="Stop the output when the shorter stream ends.",
    )
    p.set_defaults(func=_handle_mux_audio)


def _add_burn_subs(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("burn-subs", help="Burn subtitles (.srt / .vtt / .ass) into the video frames.")
    p.add_argument("--input", required=True)
    p.add_argument("--subs", required=True, help="Subtitles file.")
    p.add_argument("--output", required=True)
    p.add_argument(
        "--force-style",
        default=None,
        dest="force_style",
        help="ASS-style override (e.g. 'FontName=Helvetica,FontSize=24').",
    )
    p.set_defaults(func=_handle_burn_subs)


def _add_srt2vtt(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("srt2vtt", help="Convert an SRT to WebVTT + companion CSS.")
    p.add_argument("--input", required=True, help="Input .srt path.")
    p.add_argument("--output", default=None, help="Output .vtt (default: sibling of input).")
    p.add_argument("--css", default=None, help="Output .css (default: sibling of input).")
    p.set_defaults(func=_handle_srt2vtt)


def _add_extract_frames(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser(
        "extract-frames",
        help="Stream frames to disk as one PNG per sampled frame.",
    )
    p.add_argument("--input", required=True, help="Input video path or URL.")
    p.add_argument("--output-dir", required=True, dest="output_dir", help="Destination folder for PNGs.")
    p.add_argument("--frame-step", type=int, default=1, dest="frame_step", help="Sampling stride (default 1).")
    p.add_argument("--frame-interval", type=float, default=None, dest="frame_interval", help="Sampling period in seconds.")
    p.add_argument("--start", type=float, default=None, help="Start instant in seconds.")
    p.add_argument("--end", type=float, default=None, help="End instant in seconds.")
    p.add_argument(
        "--backend",
        default="auto",
        choices=["auto", "vidgear", "pyav", "ffmpeg-pipe"],
        help="Frame-extraction backend (default auto).",
    )
    p.set_defaults(func=_handle_extract_frames)


def build_parser() -> argparse.ArgumentParser:
    """
    Assemble the top-level ``video-helper`` argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Fully wired parser with every subcommand attached.
    """
    parser = argparse.ArgumentParser(
        prog="video-helper",
        description=(
            "Video Helper — utility CLI for validate / dimensions / duration / "
            "convert / chunk / black / image-loop / concat / overlay / "
            "extract-audio / mux-audio / burn-subs / srt2vtt / extract-frames."
        ),
    )
    # Every non-trivial CLI benefits from `--version` — cheap to add and
    # oncall people always look for it.
    try:
        from importlib.metadata import version as _pkg_version

        parser.add_argument(
            "--version",
            action="version",
            version=f"%(prog)s {_pkg_version('video-helper')}",
        )
    except Exception:  # pragma: no cover — never fatal
        pass

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # Register every subcommand. Order matters for help output only.
    _add_validate(subparsers)
    _add_dimensions(subparsers)
    _add_duration(subparsers)
    _add_convert(subparsers)
    _add_chunk(subparsers)
    _add_black(subparsers)
    _add_image_loop(subparsers)
    _add_concat(subparsers)
    _add_overlay(subparsers)
    _add_extract_audio(subparsers)
    _add_mux_audio(subparsers)
    _add_burn_subs(subparsers)
    _add_srt2vtt(subparsers)
    _add_extract_frames(subparsers)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Entry point invoked by ``video-helper`` (see ``[project.scripts]``).

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns
    -------
    int
        Process exit code (``0`` on success).
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    # Every subparser sets ``func`` via ``set_defaults`` — no dispatch table
    # needed, argparse resolved it for us.
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
