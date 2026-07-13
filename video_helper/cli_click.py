"""
Video Helper — click-based command-line interface.

Twin of :mod:`video_helper.cli_argparse`: same public surface (identical
subcommand names, identical flag semantics), but implemented with
:mod:`click` so users who already have a click-native shell setup
(bash / zsh completion via ``click.shell_completion``, colored ``--help``,
nested command groups) can plug it in without friction. Installed as
the ``video-helper-click`` entry point in ``pyproject.toml``.

Design notes
------------
- Subcommands mirror ``video-helper`` (the argparse twin) so both CLIs
  can be introspected identically by higher layers (FastAPI, MCP).
- Flags reuse the argparse names (``--input`` / ``--output`` / …) rather
  than the more idiomatic click positional style — consistency across
  the two CLIs beats micro-idiomaticity here.
- Errors from the library propagate unchanged; click handles the
  formatting.

Usage Example
-------------
>>> #   video-helper-click validate      --input clip.mp4
>>> #   video-helper-click dimensions    --input clip.mp4
>>> #   video-helper-click convert       --input in.mov --output out.mp4 --width 640 --height 480
>>> #   video-helper-click chunk         --input in.mp4 --start 10 --end 20 --output cut.mp4
>>> #   video-helper-click extract-frames --input clip.mp4 --output-dir frames/ --frame-step 5

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import json
import os

try:
    import click
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "The click CLI requires the [cli] extra. "
        "Install with: pip install 'video-helper[cli]'"
    ) from exc

# Same underlying functions as the argparse twin — one source of truth.
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
# Top-level group
#
# ``invoke_without_command=False`` forces the user to name a subcommand;
# ``context_settings`` widens the help output so long option lists stay
# readable on modern terminals.
# ---------------------------------------------------------------------------


@click.group(
    context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 100},
)
@click.version_option(package_name="video-helper", prog_name="video-helper-click")
def cli() -> None:
    """Video Helper — click twin of the argparse CLI. Same subcommands."""
    # Nothing to do at the group level — every subcommand carries its
    # own arguments and side effects.


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--input", "input_", required=True, help="Path or HTTP(S) URL to a video.")
def validate(input_: str) -> None:
    """Probe a video file / URL for validity (boolean)."""
    ok = is_valid_video_file(input_)
    click.echo("true" if ok else "false")
    # Non-zero exit code when invalid keeps shell short-circuits usable.
    if not ok:
        raise SystemExit(1)


# ---------------------------------------------------------------------------
# dimensions
# ---------------------------------------------------------------------------


def _parse_headers(pairs: tuple[str, ...]) -> dict | None:
    """Turn ``('User-Agent: X', 'Referer: Y')`` into a headers dict (or None)."""
    if not pairs:
        return None
    out: dict = {}
    for p in pairs:
        # Split only on the first ':' — header values may legitimately contain colons.
        if ":" not in p:
            continue
        k, v = p.split(":", 1)
        out[k.strip()] = v.strip()
    return out or None


@cli.command()
@click.option("--input", "input_", required=True, help="Path or HTTP(S) URL to a video.")
@click.option(
    "--header",
    multiple=True,
    help='HTTP header as "Name: value" (repeat --header). Forwarded to ffprobe for URL inputs.',
)
def dimensions(input_: str, header: tuple[str, ...]) -> None:
    """Emit width/height/duration/frame_rate/has_sound as JSON."""
    info = video_dimensions(input_, http_headers=_parse_headers(header))
    click.echo(json.dumps(info, indent=2))


# ---------------------------------------------------------------------------
# duration
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
def duration(input_: str) -> None:
    """Print the duration of a video, in seconds."""
    click.echo(f"{video_duration(input_):.6f}")


# ---------------------------------------------------------------------------
# convert
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
@click.option("--output", required=True, type=click.Path())
@click.option("--frame-rate", "frame_rate", type=int, default=None)
@click.option("--width", type=int, default=None)
@click.option("--height", type=int, default=None)
@click.option("--without-sound", "without_sound", is_flag=True, default=False, help="Drop the audio stream.")
def convert(
    input_: str,
    output: str,
    frame_rate: int | None,
    width: int | None,
    height: int | None,
    without_sound: bool,
) -> None:
    """Re-encode / resize / drop audio in one pass."""
    video_converter(
        input_video=input_,
        output_video=output,
        frame_rate=frame_rate,
        width=width,
        height=height,
        without_sound=without_sound,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# chunk
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
@click.option("--start", type=float, required=True)
@click.option("--end", type=float, required=True)
@click.option("--output", required=True, type=click.Path())
def chunk(input_: str, start: float, end: float, output: str) -> None:
    """Extract a ``[start, end]`` slice of a video."""
    extract_video_chunk(
        input_video=input_,
        sample_start=start,
        sample_end=end,
        output_video=output,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# black
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--duration", "duration_", type=float, required=True)
@click.option("--width", type=int, required=True)
@click.option("--height", type=int, required=True)
@click.option("--output", required=True, type=click.Path())
@click.option("--frame-rate", "frame_rate", type=int, default=30, show_default=True)
def black(duration_: float, width: int, height: int, output: str, frame_rate: int) -> None:
    """Synthesize a silent solid-black clip."""
    black_video(
        duration=duration_,
        width=width,
        height=height,
        output_video=output,
        frame_rate=frame_rate,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# image-loop
# ---------------------------------------------------------------------------


@cli.command("image-loop")
@click.option("--image", required=True, type=click.Path(exists=True))
@click.option("--duration", "duration_", type=float, required=True)
@click.option("--output", required=True, type=click.Path())
@click.option("--frame-rate", "frame_rate", type=int, default=30, show_default=True)
@click.option("--width", type=int, default=None)
@click.option("--height", type=int, default=None)
def image_loop(
    image: str,
    duration_: float,
    output: str,
    frame_rate: int,
    width: int | None,
    height: int | None,
) -> None:
    """Loop a still image into a silent video."""
    image_loop_to_video(
        image=image,
        duration=duration_,
        output_video=output,
        frame_rate=frame_rate,
        width=width,
        height=height,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# concat
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--inputs",
    required=True,
    multiple=True,
    type=click.Path(exists=True),
    help="Videos, in order (repeat --inputs for each).",
)
@click.option("--output", required=True, type=click.Path())
@click.option("--reencode/--no-reencode", default=True, show_default=True)
@click.option("--frame-rate", "frame_rate", type=int, default=None)
def concat(inputs: tuple[str, ...], output: str, reencode: bool, frame_rate: int | None) -> None:
    """Concatenate several videos head-to-tail."""
    concat_videos(
        input_videos=list(inputs),
        output_video=output,
        reencode=reencode,
        frame_rate=frame_rate,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# overlay
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
@click.option("--image", required=True, type=click.Path(exists=True))
@click.option("--output", required=True, type=click.Path())
@click.option("--x", default="0", show_default=True)
@click.option("--y", default="0", show_default=True)
@click.option("--scale-width", "scale_width", type=int, default=None)
def overlay(input_: str, image: str, output: str, x: str, y: str, scale_width: int | None) -> None:
    """Overlay a still image on a video."""
    overlay_image(
        input_video=input_,
        image=image,
        output_video=output,
        x=x,
        y=y,
        scale_width=scale_width,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# extract-audio
# ---------------------------------------------------------------------------


@cli.command("extract-audio")
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
@click.option("--output", required=True, type=click.Path())
@click.option("--sample-rate", "sample_rate", type=int, default=44100, show_default=True)
@click.option("--channels", type=int, default=2, show_default=True)
@click.option("--encoding", default="pcm_s16le", show_default=True)
def extract_audio(input_: str, output: str, sample_rate: int, channels: int, encoding: str) -> None:
    """Dump the audio track of a video."""
    extract_audio_track(
        input_video=input_,
        output_audio=output,
        sample_rate=sample_rate,
        channels=channels,
        encoding=encoding,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# mux-audio
# ---------------------------------------------------------------------------


@cli.command("mux-audio")
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
@click.option("--audio", required=True, type=click.Path(exists=True))
@click.option("--output", required=True, type=click.Path())
@click.option("--audio-codec", "audio_codec", default="aac", show_default=True)
@click.option("--audio-bitrate", "audio_bitrate", default="192k", show_default=True)
@click.option("--shortest", is_flag=True, default=False)
def mux_audio(
    input_: str,
    audio: str,
    output: str,
    audio_codec: str,
    audio_bitrate: str,
    shortest: bool,
) -> None:
    """Mux a separate audio track onto a video."""
    mux_audio_video(
        input_video=input_,
        input_audio=audio,
        output_video=output,
        audio_codec=audio_codec,
        audio_bitrate=audio_bitrate,
        shortest=shortest,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# burn-subs
# ---------------------------------------------------------------------------


@cli.command("burn-subs")
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
@click.option("--subs", required=True, type=click.Path(exists=True))
@click.option("--output", required=True, type=click.Path())
@click.option("--force-style", "force_style", default=None, help="ASS-style override.")
def burn_subs(input_: str, subs: str, output: str, force_style: str | None) -> None:
    """Burn subtitles (.srt / .vtt / .ass) into the video frames."""
    burn_subtitles(
        input_video=input_,
        subtitles_file=subs,
        output_video=output,
        force_style=force_style,
    )
    click.echo(output)


# ---------------------------------------------------------------------------
# srt2vtt
# ---------------------------------------------------------------------------


@cli.command("srt2vtt")
@click.option("--input", "input_", required=True, type=click.Path(exists=True))
@click.option("--output", type=click.Path(), default=None, help="Output .vtt (default: sibling of input).")
@click.option("--css", type=click.Path(), default=None, help="Output .css (default: sibling of input).")
def srt2vtt_cmd(input_: str, output: str | None, css: str | None) -> None:
    """Convert an SRT to WebVTT + companion CSS."""
    srt2vtt(srt_file_path=input_, vtt_file_path=output, css_file_path=css)
    if output:
        click.echo(output)
    else:
        stem, _ = os.path.splitext(input_)
        click.echo(stem + ".vtt")


# ---------------------------------------------------------------------------
# extract-frames
# ---------------------------------------------------------------------------


@cli.command("extract-frames")
@click.option("--input", "input_", required=True)
@click.option("--output-dir", "output_dir", required=True, type=click.Path())
@click.option("--frame-step", "frame_step", type=int, default=1, show_default=True)
@click.option("--frame-interval", "frame_interval", type=float, default=None)
@click.option("--start", type=float, default=None, help="Start instant in seconds.")
@click.option("--end", type=float, default=None, help="End instant in seconds.")
@click.option(
    "--backend",
    default="auto",
    type=click.Choice(["auto", "vidgear", "pyav", "ffmpeg-pipe"]),
    show_default=True,
)
def extract_frames_cmd(
    input_: str,
    output_dir: str,
    frame_step: int,
    frame_interval: float | None,
    start: float | None,
    end: float | None,
    backend: str,
) -> None:
    """Stream frames to disk as one PNG per sampled frame."""
    import cv2  # noqa: WPS433 — deferred so `--help` stays cheap

    os.makedirs(output_dir, exist_ok=True)
    written: list[str] = []
    for i, frame in enumerate(
        extract_frames(
            video_path=input_,
            frame_step=frame_step,
            frame_interval=frame_interval,
            start_instant=start,
            end_instant=end,
            backend=backend,
        )
    ):
        path = os.path.join(output_dir, f"frame_{i:09d}.png")
        cv2.imwrite(path, frame)
        written.append(path)
    click.echo(json.dumps({"frames": written, "count": len(written)}, indent=2))


if __name__ == "__main__":  # pragma: no cover
    cli()
