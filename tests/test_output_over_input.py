"""A destination that is also one of the sources.

Every writer in :mod:`video_helper.main` hands ffmpeg ``overwrite_output=True``,
so pointing the destination at a source truncates that source while ffmpeg is
still reading it. Two of them did it **without raising at all**: measured on
disk, ``extract_video_chunk(v, 0.2, 0.8, v)`` replaced a 41 781-byte video with
a 10 604-byte fragment of itself and ``concat_videos([v, w], v)`` overwrote `v`,
both returning normally. The caller is told nothing and the original is gone.

The remaining writers happened to fail with an opaque ffmpeg error instead,
leaving the input intact by luck rather than by design. They are covered here
too, so a later refactor cannot turn that luck into the silent case.

Author
------
[Warith HARCHAOUI](https://linkedin.com/in/warith-harchaoui/)
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import os_helper as osh
import pytest

import video_helper as vh
from video_helper.main import _refuse_output_over_input


def _tiny_video(path: Path, seconds: float, hz: int) -> Path:
    """A real encoded file, because the fault is about bytes on disk."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={seconds}:size=160x120:rate=10",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={hz}:duration={seconds}",
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-c:a",
            "aac",
            "-shortest",
            str(path),
        ],
        capture_output=True,
        check=True,
    )
    return path


def test_the_guard_compares_paths_not_strings() -> None:
    """Pure path arithmetic, so it needs neither ffmpeg nor a file."""
    assert _refuse_output_over_input("out.mp4", ["a.mp4", "b.mp4"]) is None
    for spelling in ("a.mp4", "./a.mp4", "sub/../a.mp4"):
        with pytest.raises(ValueError, match="both an input and the output"):
            _refuse_output_over_input(spelling, ["a.mp4"])
    # Second in the list, not only first.
    with pytest.raises(ValueError, match="both an input and the output"):
        _refuse_output_over_input("b.mp4", ["a.mp4", "b.mp4"])


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_no_writer_destroys_a_file_it_was_reading(tmp_path: Path) -> None:
    """The failure itself, asserted on the bytes rather than the exception.

    A guard that raised *after* ffmpeg had already truncated the file would
    satisfy an exception-only test, which is exactly the shape of the original
    bug: `extract_video_chunk` and `concat_videos` raised nothing and still
    destroyed the input.
    """
    first = _tiny_video(tmp_path / "first.mp4", 2.0, 440)
    second = _tiny_video(tmp_path / "second.mp4", 3.0, 550)
    untouched = osh.hashfile(str(first))

    cases = {
        "extract_video_chunk": lambda: vh.extract_video_chunk(str(first), 0.2, 0.8, str(first)),
        "dotted spelling": lambda: vh.extract_video_chunk(
            str(first), 0.2, 0.8, str(tmp_path / "." / "first.mp4")
        ),
        "concat, destination first": lambda: vh.concat_videos(
            [str(first), str(second)], str(first)
        ),
        "concat, destination second": lambda: vh.concat_videos(
            [str(second), str(first)], str(first)
        ),
        "compress_video": lambda: vh.compress_video(str(first), str(first), target_size_mb=0.02),
        "extract_audio_track": lambda: vh.extract_audio_track(str(first), str(first)),
        "mux_audio_video": lambda: vh.mux_audio_video(str(first), str(second), str(first)),
        "overlay_image": lambda: vh.overlay_image(str(first), str(second), str(first)),
    }
    for label, call in cases.items():
        with pytest.raises(ValueError, match="both an input and the output"):
            call()
        assert first.exists(), f"{label} deleted the file it was reading"
        assert osh.hashfile(str(first)) == untouched, f"{label} modified the file it was reading"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs ffmpeg")
def test_the_ordinary_case_still_works(tmp_path: Path) -> None:
    """The guard must not cost the legitimate call, which is the common one."""
    first = _tiny_video(tmp_path / "a.mp4", 2.0, 440)
    second = _tiny_video(tmp_path / "b.mp4", 3.0, 550)
    joined = tmp_path / "joined.mp4"
    vh.concat_videos([str(first), str(second)], str(joined))
    assert joined.exists() and joined.stat().st_size > 0

    chunk = tmp_path / "chunk.mp4"
    vh.extract_video_chunk(str(first), 0.2, 0.8, str(chunk))
    assert chunk.exists() and chunk.stat().st_size > 0
