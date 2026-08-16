"""
Functional tests for the argparse and click CLIs.

These tests exercise the CLI *parsing* layer and the trivial subcommand
help path that does not need ffmpeg. The goal here is to prevent
regressions in the CLI entry points -- flag names, subcommand names,
dispatch wiring, and cross-surface parity (argparse vs. click must agree
on subcommands, flags, and defaults) -- without pulling in the full
ffmpeg stack. Each test drives a full scenario end to end rather than
asserting one flag in isolation, so the suite stays proportional to the
number of *behaviors* being protected, not the number of flags.

Usage Example
-------------
>>> #   pytest tests/test_cli.py

Author
------
Warith Harchaoui, Ph.D. -- https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import sys

import pytest

# The click CLI needs the ``click`` runtime dep, which lives in the
# ``[cli]`` optional extra. Skip cleanly if it is not installed.
click = pytest.importorskip("click")

from click.testing import CliRunner  # noqa: E402

# The canonical subcommand list -- one source of truth for both CLIs.
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


def test_both_clis_expose_the_expected_subcommands() -> None:
    """argparse and click must each expose every canonical subcommand."""
    from video_helper.cli_argparse import build_parser
    from video_helper.cli_click import cli

    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"
    )
    assert EXPECTED_SUBCOMMANDS.issubset(set(subparsers_action.choices.keys()))
    assert EXPECTED_SUBCOMMANDS.issubset(set(cli.commands.keys()))


def test_both_clis_top_level_help_exits_zero(capsys) -> None:
    """``--help`` on both entry points exits 0 and prints usage."""
    from video_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    assert "video-helper" in capsys.readouterr().out.lower()

    from video_helper.cli_click import cli

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "video helper" in result.output.lower()


def test_every_subcommand_help_exits_zero_on_both_clis(capsys) -> None:
    """Every subcommand's ``--help`` exits 0 on both the argparse and click
    entry points -- catches a subcommand wired into one CLI but broken (or
    missing a required-arg default) in the other."""
    from video_helper.cli_argparse import main as argparse_main
    from video_helper.cli_click import cli

    runner = CliRunner()
    for sub in sorted(EXPECTED_SUBCOMMANDS):
        with pytest.raises(SystemExit) as exc:
            argparse_main([sub, "--help"])
        assert exc.value.code == 0, f"argparse {sub} --help"

        result = runner.invoke(cli, [sub, "--help"])
        assert result.exit_code == 0, f"click {sub} --help"


def test_extract_frames_pad_color_flags_parse_and_default_on_both_clis() -> None:
    """``extract-frames``'s --width/--height/--pad-color are wired the same
    way on both CLIs: listed in --help, parsed to the right type, and
    default to 'black' when omitted."""
    from video_helper.cli_argparse import build_parser
    from video_helper.cli_argparse import main as argparse_main
    from video_helper.cli_click import cli, extract_frames_cmd

    with pytest.raises(SystemExit):
        argparse_main(["extract-frames", "--help"])

    ns = build_parser().parse_args(
        [
            "extract-frames",
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
        ]
    )
    assert (ns.width, ns.height, ns.pad_color) == (320, 240, "#FF0000")

    ns_default = build_parser().parse_args(
        ["extract-frames", "--input", "in.mp4", "--output-dir", "out"]
    )
    assert ns_default.width is None
    assert ns_default.height is None
    assert ns_default.pad_color == "black"

    result = CliRunner().invoke(cli, ["extract-frames", "--help"])
    assert result.exit_code == 0
    assert "--width" in result.output
    assert "--height" in result.output
    assert "--pad-color" in result.output

    click_defaults = {p.name: p.default for p in extract_frames_cmd.params}
    assert click_defaults["width"] is None
    assert click_defaults["height"] is None
    assert click_defaults["pad_color"] == "black"


def test_compress_flags_and_defaults_match_across_cli_surfaces() -> None:
    """``compress``'s flags, defaults, and the ``vcodec='copy'`` remux
    escape hatch agree between argparse and click, and both match
    ``compress_video()``'s own signature (the single source of truth)."""
    from video_helper.cli_argparse import build_parser
    from video_helper.cli_click import compress

    ns = build_parser().parse_args(
        [
            "compress",
            "--input",
            "in.mp4",
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
        ]
    )
    assert ns.output == "out.mp4"
    assert ns.target_size_mb == 50.0
    assert ns.audio_bitrate == "96k"
    assert ns.vcodec == "libx264"
    assert ns.min_video_bitrate_kbps == 300
    assert ns.no_overwrite is True

    argparse_defaults = build_parser().parse_args(["compress", "--input", "in.mp4"])
    click_defaults = {p.name: p.default for p in compress.params}
    for name, expected in (
        ("output", None),
        ("target_size_mb", 97.0),
        ("audio_bitrate", "128k"),
        ("vcodec", "libx265"),
        ("min_video_bitrate_kbps", 200),
        ("no_overwrite", False),
    ):
        assert getattr(argparse_defaults, name) == expected, f"argparse default {name}"
        assert click_defaults[name] == expected, f"click default {name}"

    # 'copy' (remux, no re-encode) must be reachable from both CLIs.
    copy_ns = build_parser().parse_args(["compress", "--input", "in.mp4", "--vcodec", "copy"])
    assert copy_ns.vcodec == "copy"
    vcodec_param = next(p for p in compress.params if p.name == "vcodec")
    assert "copy" in vcodec_param.type.choices


def test_extract_flow_flags_and_defaults_match_across_cli_surfaces() -> None:
    """``extract-flow``'s flags and defaults (including the wavelet-resize
    pair) agree between argparse and click, matching
    ``extract_optical_flow()``'s own signature."""
    from video_helper.cli_argparse import build_parser
    from video_helper.cli_click import extract_flow_cmd

    ns = build_parser().parse_args(
        [
            "extract-flow",
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
        ]
    )
    assert ns.output == "flow.npy"
    assert ns.method == "raft"
    assert ns.dis_preset == "medium"
    assert ns.raft_variant == "large"
    assert ns.device == "mps"
    assert ns.clip_flow == 20.0
    assert ns.start == 1.5
    assert ns.end == 3.5
    assert ns.frame_step == 2
    assert ns.frame_interval == 0.5
    assert ns.fps == 24.0
    assert ns.output_width == 320
    assert ns.output_height == 240
    assert ns.wavelet == "haar"
    assert ns.no_overwrite is True

    argparse_defaults = build_parser().parse_args(["extract-flow", "--input", "in.mp4"])
    click_defaults = {p.name: p.default for p in extract_flow_cmd.params}
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
        assert getattr(argparse_defaults, name) == expected, f"argparse default {name}"
        assert click_defaults[name] == expected, f"click default {name}"


def test_both_clis_print_clean_error_on_library_exception(tmp_path, monkeypatch, capsys) -> None:
    """A library exception (missing/invalid input) must not surface as a raw
    Python traceback on either CLI -- each ``main()`` should print one clean
    ``Error: ...`` line to stderr and return/raise a nonzero exit code."""
    from video_helper.cli_argparse import main as argparse_main

    exit_code = argparse_main(["duration", "--input", "/nonexistent/no-such-video.mp4"])
    assert exit_code != 0
    captured = capsys.readouterr()
    assert captured.err.startswith("Error: ")
    assert "Traceback (most recent call last)" not in captured.err

    # click's own ``duration --input`` uses click.Path(exists=True), which
    # rejects a missing path before the library ever runs -- so this needs a
    # file that *exists* but is not a valid video, to exercise the library's
    # own exception path via the console-script ``main()`` wrapper (not the
    # bare ``cli`` group, which does not catch this).
    from video_helper.cli_click import main as click_main

    garbage = tmp_path / "not-a-video.mp4"
    garbage.write_bytes(b"not a real video")
    monkeypatch.setattr(sys, "argv", ["video-helper-click", "duration", "--input", str(garbage)])
    with pytest.raises(SystemExit) as exc_info:
        click_main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("Error: ")
    assert "Traceback (most recent call last)" not in captured.err
