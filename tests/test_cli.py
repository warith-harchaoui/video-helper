"""
Smoke tests for the argparse and click CLIs.

These tests exercise the CLI *parsing* layer and the trivial subcommand
help path that does not need ffmpeg. The goal here is to prevent
regressions in the CLI entry points — flag names, subcommand names,
dispatch wiring — without pulling in the full ffmpeg stack.

Usage Example
-------------
>>> #   pytest tests/test_cli.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import sys

import pytest

# The click CLI needs the ``click`` runtime dep, which lives in the
# ``[cli]`` optional extra. Skip cleanly if it is not installed.
click = pytest.importorskip("click")

from click.testing import CliRunner  # noqa: E402

# The canonical subcommand list — one source of truth for both CLIs.
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


def test_argparse_parser_builds_without_error() -> None:
    """Building the parser should never fail (imports, subcommand wiring)."""
    from video_helper.cli_argparse import build_parser

    parser = build_parser()
    # A parser with at least one subcommand exposes them via _subparsers.
    subparsers_action = next(
        a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction"
    )
    assert EXPECTED_SUBCOMMANDS.issubset(set(subparsers_action.choices.keys()))


def test_argparse_help_exits_zero(capsys) -> None:
    """``video-helper --help`` should exit with code 0 and print usage."""
    from video_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    captured = capsys.readouterr()
    assert "video-helper" in captured.out.lower()


@pytest.mark.parametrize("sub", sorted(EXPECTED_SUBCOMMANDS))
def test_argparse_subcommand_help_exits_zero(sub, capsys) -> None:
    """Every argparse subcommand's ``--help`` should exit 0 (no wiring bug)."""
    from video_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main([sub, "--help"])
    assert exc.value.code == 0


def test_click_group_has_expected_subcommands() -> None:
    """The click group must expose the same subcommands as the argparse CLI."""
    from video_helper.cli_click import cli

    assert EXPECTED_SUBCOMMANDS.issubset(set(cli.commands.keys()))


def test_click_help_exits_zero() -> None:
    """``video-helper-click --help`` should exit 0."""
    from video_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "video helper" in result.output.lower()


@pytest.mark.parametrize("sub", sorted(EXPECTED_SUBCOMMANDS))
def test_click_subcommand_help_exits_zero(sub) -> None:
    """Every click subcommand's ``--help`` should exit 0."""
    from video_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, [sub, "--help"])
    assert result.exit_code == 0


def test_argparse_extract_frames_exposes_pad_color_flags(capsys) -> None:
    """``extract-frames --help`` (argparse) lists --width/--height/--pad-color."""
    from video_helper.cli_argparse import main

    with pytest.raises(SystemExit) as exc:
        main(["extract-frames", "--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "--width" in out
    assert "--height" in out
    assert "--pad-color" in out


def test_click_extract_frames_exposes_pad_color_flags() -> None:
    """``extract-frames --help`` (click) lists --width/--height/--pad-color."""
    from video_helper.cli_click import cli

    runner = CliRunner()
    result = runner.invoke(cli, ["extract-frames", "--help"])
    assert result.exit_code == 0
    assert "--width" in result.output
    assert "--height" in result.output
    assert "--pad-color" in result.output


def test_argparse_extract_frames_parses_pad_color_flags() -> None:
    """The argparse ``extract-frames`` subparser parses width/height/pad-color."""
    from video_helper.cli_argparse import build_parser

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
    assert ns.width == 320
    assert ns.height == 240
    assert ns.pad_color == "#FF0000"


def test_argparse_extract_frames_pad_color_defaults_to_black() -> None:
    """Omitting --pad-color defaults to 'black', matching the library default."""
    from video_helper.cli_argparse import build_parser

    ns = build_parser().parse_args(["extract-frames", "--input", "in.mp4", "--output-dir", "out"])
    assert ns.width is None
    assert ns.height is None
    assert ns.pad_color == "black"


def test_click_extract_frames_pad_color_defaults_to_black() -> None:
    """The click ``extract-frames`` command defaults --pad-color to 'black'."""
    from video_helper.cli_click import extract_frames_cmd

    defaults = {p.name: p.default for p in extract_frames_cmd.params}
    assert defaults["width"] is None
    assert defaults["height"] is None
    assert defaults["pad_color"] == "black"


def test_argparse_compress_parses_all_flags() -> None:
    """The argparse ``compress`` subparser parses every documented flag."""
    from video_helper.cli_argparse import build_parser

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


def test_argparse_compress_defaults_match_library() -> None:
    """Omitted ``compress`` flags default to the same values as compress_video()."""
    from video_helper.cli_argparse import build_parser

    ns = build_parser().parse_args(["compress", "--input", "in.mp4"])
    assert ns.output is None
    assert ns.target_size_mb == 97.0
    assert ns.audio_bitrate == "128k"
    assert ns.vcodec == "libx265"
    assert ns.min_video_bitrate_kbps == 200
    assert ns.no_overwrite is False


def test_click_compress_defaults_match_library() -> None:
    """The click ``compress`` command defaults match compress_video()'s signature."""
    from video_helper.cli_click import compress

    defaults = {p.name: p.default for p in compress.params}
    assert defaults["output"] is None
    assert defaults["target_size_mb"] == 97.0
    assert defaults["audio_bitrate"] == "128k"
    assert defaults["vcodec"] == "libx265"
    assert defaults["min_video_bitrate_kbps"] == 200
    assert defaults["no_overwrite"] is False


def test_argparse_compress_vcodec_accepts_copy() -> None:
    """The argparse ``compress`` --vcodec choices include the 'copy' remux escape hatch."""
    from video_helper.cli_argparse import build_parser

    ns = build_parser().parse_args(["compress", "--input", "in.mp4", "--vcodec", "copy"])
    assert ns.vcodec == "copy"


def test_click_compress_vcodec_choices_include_copy() -> None:
    """The click ``compress`` --vcodec choices include the 'copy' remux escape hatch."""
    from video_helper.cli_click import compress

    vcodec_param = next(p for p in compress.params if p.name == "vcodec")
    assert vcodec_param.type.choices == ("libx265", "libx264", "copy")


def test_argparse_extract_flow_parses_all_flags() -> None:
    """The argparse ``extract-flow`` subparser parses every documented flag."""
    from video_helper.cli_argparse import build_parser

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
    assert ns.no_overwrite is True


def test_argparse_extract_flow_defaults_match_library() -> None:
    """Omitted ``extract-flow`` flags default to the same values as extract_optical_flow()."""
    from video_helper.cli_argparse import build_parser

    ns = build_parser().parse_args(["extract-flow", "--input", "in.mp4"])
    assert ns.output is None
    assert ns.method == "dis"
    assert ns.dis_preset == "fast"
    assert ns.raft_variant == "small"
    assert ns.device == "cpu"
    assert ns.clip_flow is None
    assert ns.frame_step == 1
    assert ns.frame_interval is None
    assert ns.fps is None
    assert ns.output_width is None
    assert ns.output_height is None
    assert ns.wavelet == "db2"
    assert ns.no_overwrite is False


def test_argparse_extract_flow_parses_resize_flags() -> None:
    """The argparse ``extract-flow`` subparser parses --output-width/--output-height/--wavelet."""
    from video_helper.cli_argparse import build_parser

    ns = build_parser().parse_args(
        [
            "extract-flow",
            "--input",
            "in.mp4",
            "--output-width",
            "320",
            "--output-height",
            "240",
            "--wavelet",
            "haar",
        ]
    )
    assert ns.output_width == 320
    assert ns.output_height == 240
    assert ns.wavelet == "haar"


def test_click_extract_flow_defaults_match_library() -> None:
    """The click ``extract-flow`` command defaults match extract_optical_flow()'s signature."""
    from video_helper.cli_click import extract_flow_cmd

    defaults = {p.name: p.default for p in extract_flow_cmd.params}
    assert defaults["output"] is None
    assert defaults["method"] == "dis"
    assert defaults["dis_preset"] == "fast"
    assert defaults["raft_variant"] == "small"
    assert defaults["device"] == "cpu"
    assert defaults["clip_flow"] is None
    assert defaults["frame_step"] == 1
    assert defaults["frame_interval"] is None
    assert defaults["fps"] is None
    assert defaults["output_width"] is None
    assert defaults["output_height"] is None
    assert defaults["wavelet"] == "db2"
    assert defaults["no_overwrite"] is False


def test_argparse_main_prints_clean_error_on_library_exception(capsys) -> None:
    """A library ``AssertionError`` (missing input file) must not surface as
    a raw Python traceback — ``main()`` should print one clean ``Error: ...``
    line to stderr and return a nonzero exit code."""
    from video_helper.cli_argparse import main

    exit_code = main(["duration", "--input", "/nonexistent/no-such-video.mp4"])
    assert exit_code != 0
    captured = capsys.readouterr()
    assert captured.err.startswith("Error: ")
    assert "Traceback (most recent call last)" not in captured.err


def test_click_main_prints_clean_error_on_library_exception(tmp_path, monkeypatch, capsys) -> None:
    """Same guarantee as the argparse twin, via the ``main()`` console-script
    wrapper (not the bare ``cli`` group, which does not catch this). ``main``
    is a plain function (not a click ``Command``), so it is driven the same
    way a real console-script invocation would: via ``sys.argv`` + the
    ``SystemExit`` it raises, not ``CliRunner.invoke`` (which requires a
    click ``Command``/``Group``).

    ``duration --input`` uses ``click.Path(exists=True)``, which rejects a
    missing path at the option-parsing level (exit code 2, click's own
    usage error) before the library ever runs — so this needs a file that
    *exists* but is not a valid video, to actually exercise the library's
    own exception path.
    """
    from video_helper.cli_click import main

    garbage = tmp_path / "not-a-video.mp4"
    garbage.write_bytes(b"not a real video")
    monkeypatch.setattr(sys, "argv", ["video-helper-click", "duration", "--input", str(garbage)])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert captured.err.startswith("Error: ")
    assert "Traceback (most recent call last)" not in captured.err
