"""
Functional tests for the ``video-helper`` command line.

These tests exercise the CLI *parsing* layer and the subcommand help paths
that need no ffmpeg. The goal is to prevent regressions in the entry point
-- flag names, subcommand names, defaults, dispatch wiring -- so a broken
command line fails here rather than in somebody's shell. Each test drives a
full scenario end to end rather than asserting one flag in isolation, so the
suite stays proportional to the number of *behaviors* protected, not the
number of flags.

Parsing is checked through ``Command.make_context``, which runs click's
parser and stops before the callback: the parsed values are asserted without
ffmpeg ever being invoked. That is the click equivalent of the
``parser.parse_args()`` assertions this file carried while the package also
shipped an argparse CLI.

Usage Example
-------------
>>> #   pytest tests/test_cli.py

Author
------
Warith Harchaoui, Ph.D. -- https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import sys

import click
import pytest
from click.testing import CliRunner

from video_helper.cli import (
    _ordered_inputs,
    cli,
    compress,
    concat,
    extract_flow_cmd,
    extract_frames_cmd,
    main,
)

# The canonical subcommand list -- the command line's whole public surface.
EXPECTED_SUBCOMMANDS = {
    "validate",
    "dimensions",
    "duration",
    "convert",
    "chunk",
    "black",
    "compress",
    "image-loop",
    "concat",
    "overlay",
    "extract-audio",
    "mux-audio",
    "burn-subs",
    "srt2vtt",
    "extract-frames",
    "extract-flow",
}


def _params(command: click.Command, args: list[str]) -> dict:
    """Parse ``args`` for ``command`` and return the resolved parameters.

    ``make_context`` stops at the end of parsing, so this reads exactly what
    the callback would have received without running it (no ffmpeg).
    """
    ctx = command.make_context(command.name or "cmd", args)
    return ctx.params


def test_cli_exposes_the_expected_subcommands() -> None:
    """Every canonical operation is reachable as a subcommand."""
    assert EXPECTED_SUBCOMMANDS.issubset(set(cli.commands.keys()))


def test_top_level_help_and_version_flags_all_work() -> None:
    """``--help``, its ``-h`` alias and ``-V`` each exit 0 and say something.

    None of the three is visible by reading the command definitions: click
    only answers to ``-h`` when ``help_option_names`` says so, and a
    malformed ``version_option`` raises at *import* rather than here.
    """
    runner = CliRunner()
    for flag in ("--help", "-h"):
        result = runner.invoke(cli, [flag])
        assert result.exit_code == 0, flag
        assert "video helper" in result.output.lower(), flag
        # The help must describe the tool, not its own implementation history.
        assert "argparse" not in result.output.lower()
        assert "twin" not in result.output.lower()

    for flag in ("--version", "-V"):
        result = runner.invoke(cli, [flag])
        assert result.exit_code == 0, flag
        assert "version" in result.output.lower(), flag


def test_every_subcommand_help_exits_zero() -> None:
    """Every subcommand's ``--help`` exits 0 -- catches a subcommand wired
    into the group but broken (a bad default, a missing callback argument)."""
    runner = CliRunner()
    for sub in sorted(EXPECTED_SUBCOMMANDS):
        result = runner.invoke(cli, [sub, "--help"])
        assert result.exit_code == 0, f"{sub} --help"


def test_extract_frames_pad_color_flags_parse_and_default() -> None:
    """``extract-frames``'s --width/--height/--pad-color are listed in --help,
    parsed to the right type, and default to 'black' when omitted."""
    result = CliRunner().invoke(cli, ["extract-frames", "--help"])
    assert result.exit_code == 0
    for flag in ("--width", "--height", "--pad-color"):
        assert flag in result.output

    parsed = _params(
        extract_frames_cmd,
        [
            "--input",
            "in.mp4",
            "--output-dir",
            "out",
            "--width",
            "320",
            "--height",
            "240",
            "--pad-color",
            "#FF0000",
        ],
    )
    assert (parsed["width"], parsed["height"], parsed["pad_color"]) == (320, 240, "#FF0000")

    defaults = _params(extract_frames_cmd, ["--input", "in.mp4", "--output-dir", "out"])
    assert defaults["width"] is None
    assert defaults["height"] is None
    assert defaults["pad_color"] == "black"


def test_compress_flags_and_defaults_match_the_library(tmp_path) -> None:
    """``compress``'s flags, defaults, and the ``vcodec='copy'`` remux escape
    hatch all parse, and the defaults match ``compress_video()``'s own
    signature (the single source of truth)."""
    # --input is a click.Path(exists=True), so the parser needs a real file.
    source = tmp_path / "in.mp4"
    source.write_bytes(b"")

    parsed = _params(
        compress,
        [
            "--input",
            str(source),
            "--output",
            "out.mp4",
            "--target-size-mb",
            "50",
            "--audio-bitrate",
            "96k",
            "--vcodec",
            "libx264",
            "--min-video-bitrate-kbps",
            "300",
            "--no-overwrite",
        ],
    )
    assert parsed["output"] == "out.mp4"
    assert parsed["target_size_mb"] == 50.0
    assert parsed["audio_bitrate"] == "96k"
    assert parsed["vcodec"] == "libx264"
    assert parsed["min_video_bitrate_kbps"] == 300
    assert parsed["no_overwrite"] is True

    defaults = _params(compress, ["--input", str(source)])
    for name, expected in (
        ("output", None),
        ("target_size_mb", 97.0),
        ("audio_bitrate", "128k"),
        ("vcodec", "libx265"),
        ("min_video_bitrate_kbps", 200),
        ("no_overwrite", False),
    ):
        assert defaults[name] == expected, f"default {name}"

    # 'copy' (remux, no re-encode) must stay reachable from the command line.
    assert _params(compress, ["--input", str(source), "--vcodec", "copy"])["vcodec"] == "copy"
    vcodec_param = next(p for p in compress.params if p.name == "vcodec")
    assert "copy" in vcodec_param.type.choices


def test_extract_flow_flags_and_defaults_match_the_library() -> None:
    """``extract-flow``'s flags and defaults (including the wavelet-resize
    pair) all parse and match ``extract_optical_flow()``'s own signature."""
    parsed = _params(
        extract_flow_cmd,
        [
            "--input",
            "in.mp4",
            "--output",
            "flow.npy",
            "--method",
            "raft",
            "--dis-preset",
            "medium",
            "--raft-variant",
            "large",
            "--device",
            "mps",
            "--clip-flow",
            "20",
            "--start",
            "1.5",
            "--end",
            "3.5",
            "--frame-step",
            "2",
            "--frame-interval",
            "0.5",
            "--fps",
            "24",
            "--output-width",
            "320",
            "--output-height",
            "240",
            "--wavelet",
            "haar",
            "--no-overwrite",
        ],
    )
    assert parsed["output"] == "flow.npy"
    assert parsed["method"] == "raft"
    assert parsed["dis_preset"] == "medium"
    assert parsed["raft_variant"] == "large"
    assert parsed["device"] == "mps"
    assert parsed["clip_flow"] == 20.0
    assert parsed["start"] == 1.5
    assert parsed["end"] == 3.5
    assert parsed["frame_step"] == 2
    assert parsed["frame_interval"] == 0.5
    assert parsed["fps"] == 24.0
    assert parsed["output_width"] == 320
    assert parsed["output_height"] == 240
    assert parsed["wavelet"] == "haar"
    assert parsed["no_overwrite"] is True

    defaults = _params(extract_flow_cmd, ["--input", "in.mp4"])
    for name, expected in (
        ("output", None),
        ("method", "dis"),
        ("dis_preset", "fast"),
        ("raft_variant", "small"),
        ("device", "cpu"),
        ("clip_flow", None),
        ("frame_step", 1),
        ("frame_interval", None),
        ("fps", None),
        ("output_width", None),
        ("output_height", None),
        ("wavelet", "db2"),
        ("no_overwrite", False),
    ):
        assert defaults[name] == expected, f"default {name}"


def test_concat_accepts_both_input_spellings_and_refuses_an_ambiguous_one(tmp_path) -> None:
    """``concat --inputs a b c`` and ``--inputs a --inputs b --inputs c`` both
    resolve to the same ordered list, and mixing the two is a usage error.

    click has no ``nargs=-1`` for options, so files listed after a single
    ``--inputs`` arrive as a separate trailing tuple. Getting that wrong does
    not raise -- it concatenates fewer clips than asked, writing a plausible
    but wrong file -- which is why the order is asserted here rather than
    merely the count.
    """
    clips = []
    for name in ("a.mp4", "b.mp4", "c.mp4"):
        path = tmp_path / name
        path.write_bytes(b"")
        clips.append(str(path))

    listed = _params(concat, ["--inputs", *clips, "--output", "out.mp4"])
    assert _ordered_inputs(listed["inputs"], listed["trailing_inputs"]) == clips

    repeated_args: list[str] = []
    for clip in clips:
        repeated_args += ["--inputs", clip]
    repeated = _params(concat, [*repeated_args, "--output", "out.mp4"])
    assert _ordered_inputs(repeated["inputs"], repeated["trailing_inputs"]) == clips

    # Mixed spelling: click reports ('a', 'c') and ('b',) with no record of
    # how they interleaved, so the command refuses instead of guessing.
    result = CliRunner().invoke(
        cli,
        [
            "concat",
            "--inputs",
            clips[0],
            clips[1],
            "--inputs",
            clips[2],
            "--output",
            str(tmp_path / "out.mp4"),
        ],
    )
    assert result.exit_code != 0
    assert "Ambiguous --inputs order" in result.output


def test_cli_prints_clean_error_on_library_exception(tmp_path, monkeypatch, capsys) -> None:
    """A library exception must not surface as a raw Python traceback: the
    console-script ``main()`` prints one clean ``Error: ...`` line to stderr
    and exits non-zero."""
    # ``duration`` declares click.Path(exists=True), which rejects a missing
    # path before the library ever runs -- so this needs a file that *exists*
    # but is not a valid video, to reach the library's own exception path
    # through ``main()`` (the bare ``cli`` group does not catch it).
    garbage = tmp_path / "not-a-video.mp4"
    garbage.write_bytes(b"not a real video")
    monkeypatch.setattr(sys, "argv", ["video-helper", "duration", "--input", str(garbage)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("Error: ")
    assert "Traceback (most recent call last)" not in captured.err
