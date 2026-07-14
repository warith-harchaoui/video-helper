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
    "image-loop",
    "concat",
    "overlay",
    "extract-audio",
    "mux-audio",
    "burn-subs",
    "srt2vtt",
    "extract-frames",
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
