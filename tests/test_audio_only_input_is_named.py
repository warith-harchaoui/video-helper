"""
``video_dimensions`` on a file with no video stream.

Audio is audio-helper's half of a deliberate split -- ``video_duration``'s own
docstring calls itself "the mirror of ``audio_helper.get_audio_duration`` for
the video side". Handed a WAV, this function used to raise a bare
``StopIteration`` from inside a ``next()`` generator: no file name, no cause,
and it reads as a bug in video-helper rather than as "you want the other
function". The error now says which one.
"""

from __future__ import annotations

import subprocess
import wave
from pathlib import Path

import pytest

import video_helper as vh


@pytest.fixture()
def wav(tmp_path: Path) -> str:
    """A tiny real WAV, written with the stdlib so the test needs no fixture file."""
    path = tmp_path / "tone.wav"
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(8000)
        handle.writeframes(b"\x00\x00" * 8000)
    return str(path)


def test_an_audio_file_raises_a_named_error(wav: str) -> None:
    with pytest.raises(ValueError) as caught:
        vh.video_dimensions(wav)
    message = str(caught.value)
    # The three things the old StopIteration could not say.
    assert "audio-only" in message
    assert "audio_helper" in message
    assert wav in message


def test_video_duration_surfaces_the_same_error(wav: str) -> None:
    """``video_duration`` goes through ``video_dimensions``, so it inherits it."""
    with pytest.raises(ValueError, match="audio_helper"):
        vh.video_duration(wav)


def test_a_real_video_still_probes(tmp_path: Path) -> None:
    """
    The guard must not cost the normal path.

    Built here rather than taken from a fixture so the test is self-contained.
    """
    clip = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
         "-i", "testsrc=size=160x120:rate=10:duration=1", str(clip)],
        check=True, capture_output=True,
    )
    dims = vh.video_dimensions(str(clip))
    assert (dims["width"], dims["height"]) == (160, 120)
    assert dims["has_sound"] is False
