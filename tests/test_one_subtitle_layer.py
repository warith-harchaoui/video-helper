"""
One timed-text layer, read and written in one place.

The suite had four writers of this format and two readers, consolidated once
in ``sprezzature-audio`` and moved here, where the package that burns
subtitles into frames and converts between the formats already lived. The
differences between those writers were not cosmetic — voice tags on one
track and deliberately not on another, cue identifiers on a third, line
structure kept by one reader and glued together by the other — so the move
had to keep every one of them rather than pick a winner.

These tests are that list of differences, each pinned, plus what the move
added: a format chosen by extension, the SubRip direction, and the sentence
splitter that two packages disagreed about.

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_helper.subtitles import (
    Cue,
    format_timestamp,
    from_centiseconds,
    parse,
    split_sentences,
    vtt2srt,
    write,
    write_srt,
    write_vtt,
)

# ── Timestamps ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("seconds", "srt", "expected"),
    [
        (0, False, "00:00:00.000"),
        (61.34, False, "00:01:01.340"),
        (61.34, True, "00:01:01,340"),
        (3661.5, False, "01:01:01.500"),
    ],
)
def test_a_timestamp_reads_the_same_in_both_formats(
    seconds: float, srt: bool, expected: str
) -> None:
    """The decimal separator is the only difference between VTT and SRT."""
    assert format_timestamp(seconds, srt=srt) == expected


def test_a_negative_time_clamps_to_zero() -> None:
    """A negative timestamp is never meaningful and a renderer's reply to one
    is undefined rather than obvious."""
    assert format_timestamp(-5.0) == "00:00:00.000"


def test_a_timestamp_is_truncated_never_rounded() -> None:
    """Rounding up lets a cue claim to start before the sample that starts it.

    Half a millisecond early is still early, and a read-along highlight then
    lands on a word the voice has not reached.
    """
    assert format_timestamp(1.9999) == "00:00:01.999"


def test_whisper_units_convert() -> None:
    """whisper.cpp counts in 10-ms units; nothing else here does."""
    assert from_centiseconds(150) == 1.5


# ── Voice tags ─────────────────────────────────────────────────────────────


def test_a_speaker_becomes_a_voice_tag() -> None:
    """A diarized same-language track names its speakers."""
    out = write_vtt([Cue(start=0.0, end=1.0, text="Hello.", speaker="Ada")])
    assert "<v Ada>Hello." in out


def test_voices_can_be_refused() -> None:
    """W3C reserves voice tags for the same-language captions track, so a
    translated subtitle track must be able to carry a speaker and not write
    it."""
    cues = [Cue(start=0.0, end=1.0, text="Bonjour.", speaker="Ada")]
    assert "<v" not in write_vtt(cues, voices=False)


def test_subrip_prefixes_the_speaker_instead() -> None:
    """SubRip has no voice tags, so the speaker is the prefix players show."""
    out = write_srt([Cue(start=0.0, end=1.0, text="Hello.", speaker="Ada")])
    assert "Ada: Hello." in out


# ── Identifiers ────────────────────────────────────────────────────────────


def test_an_identifier_is_written_before_the_timings() -> None:
    """The narration path carries a segment index there, which is what lets a
    page highlight the right block without matching on text."""
    out = write_vtt([Cue(start=0.0, end=1.0, text="Hello.", identifier="7")])
    lines = [line for line in out.splitlines() if line]
    assert lines[1] == "7"
    assert "-->" in lines[2]


def test_no_identifier_writes_no_line() -> None:
    """Nothing but narration needs them."""
    out = write_vtt([Cue(start=0.0, end=1.0, text="Hello.")])
    lines = [line for line in out.splitlines() if line]
    assert "-->" in lines[1]


def test_srt_numbers_its_own_cues() -> None:
    """SubRip's identifier is a sequence number, so a segment index cannot
    survive the trip. The format's limit, not a choice made here."""
    out = write_srt(
        [
            Cue(start=0.0, end=1.0, text="One.", identifier="40"),
            Cue(start=1.0, end=2.0, text="Two.", identifier="41"),
        ]
    )
    numbers = [line for line in out.splitlines() if line.isdigit()]
    assert numbers == ["1", "2"]


# ── Line structure ─────────────────────────────────────────────────────────


def test_line_structure_survives_a_read() -> None:
    """A width audit counts lines and cannot do it on a cue whose lines were
    glued together by the reader."""
    cues = parse("WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nfirst line\nsecond line\n")
    assert cues[0].lines == ["first line", "second line"]


def test_one_writer_serves_both_callers_and_neither_wins(tmp_path: Path) -> None:
    """The two callers of this writer need opposite things, and both are right.

    A film's subtitle is read by a human: two display lines of about 42
    characters each, and the newline between them is how WebVTT says so. The
    suite's films carry 22 such tracks, and an audit that counts line width
    cannot do its work on a cue whose lines were glued together.

    A narration cue is matched to a page element by its *identifier*, and a
    blank line ends a cue: a hard-wrapped payload there would become two cues
    and shift every index after it, so the read-along would highlight the
    wrong sentence from that point on.

    So the writer preserves what it is given, and flattening is the caller's
    explicit request through ``Cue.collapsed()``. Pinned here because a
    consolidation that picked one of the two would silently break the other,
    and the breakage shows up as misaligned highlighting in one case and a
    failed width audit in the other -- neither of them near this code.
    """
    two_lines = Cue(
        start=0.0,
        end=3.0,
        text="first display line\nsecond display line",
        identifier="7",
    )

    for_a_human = write_vtt([two_lines])
    assert "first display line\nsecond display line" in for_a_human

    # `collapsed()` keeps the identifier, which is the whole point: the cue
    # that gets flattened is the one that is matched by index.
    for_an_index = write_vtt([two_lines.collapsed()])
    assert "first display line second display line" in for_an_index
    # One cue, not two: the count is what the identifiers ride on.
    assert for_an_index.count("-->") == 1
    assert len(parse(for_an_index)) == 1
    assert parse(for_an_index)[0].identifier == "7"


def test_collapsing_puts_a_cue_on_one_line() -> None:
    """A blank line ends a cue, so a caller assembling text from a document
    collapses before writing or it gets two cues and a shifted index."""
    cue = Cue(start=0.0, end=1.0, text="first\nsecond")
    assert cue.collapsed().text == "first second"


def test_an_empty_cue_is_dropped() -> None:
    """A timed blank box is on screen for its full duration and says nothing."""
    out = write_vtt([Cue(start=0.0, end=1.0, text="   ")])
    assert "-->" not in out


# ── Reading ────────────────────────────────────────────────────────────────


def test_subrip_reads_too() -> None:
    """A reader holding an SRT has no reason to convert it first."""
    cues = parse("1\n00:00:01,000 --> 00:00:02,000\nHello.\n")
    assert cues[0].start == 1.0
    assert cues[0].text == "Hello."


def test_a_voice_tag_is_lifted_out_of_the_text() -> None:
    """So a caller that re-writes the cue does not double-tag it."""
    cues = parse("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\n<v Ada>Hello.\n")
    assert cues[0].speaker == "Ada"
    assert cues[0].text == "Hello."


def test_cues_come_back_in_time_order() -> None:
    """Out-of-order cues are legal in the file and useless to a consumer."""
    cues = parse(
        "WEBVTT\n\n00:00:05.000 --> 00:00:06.000\nsecond\n\n00:00:01.000 --> 00:00:02.000\nfirst\n"
    )
    assert [cue.text for cue in cues] == ["first", "second"]


def test_a_byte_order_mark_and_crlf_do_not_reach_the_first_cue() -> None:
    """Both arrive routinely from Windows subtitle tools, both used to land
    inside the first identifier, where they are invisible in a diff."""
    cues = parse("﻿1\r\n00:00:01,000 --> 00:00:02,000\r\nHello.\r\n")
    assert len(cues) == 1
    assert cues[0].identifier == "1"
    assert cues[0].text == "Hello."


def test_a_round_trip_keeps_everything() -> None:
    """The pair has to agree, or one of them is wrong."""
    original = [
        Cue(start=0.0, end=1.5, text="first\nsecond", speaker="Ada", identifier="0"),
        Cue(start=2.0, end=3.0, text="next", identifier="1"),
    ]
    back = parse(write_vtt(original))
    assert [(cue.start, cue.end) for cue in back] == [(0.0, 1.5), (2.0, 3.0)]
    assert back[0].speaker == "Ada"
    assert back[0].lines == ["first", "second"]
    assert back[0].identifier == "0"


# ── The format is the extension ────────────────────────────────────────────


def test_the_extension_picks_the_format(tmp_path: Path) -> None:
    """A caller naming captions.srt has already said what it wants; making it
    repeat itself in a second argument is how the two come apart."""
    cues = [Cue(start=0.0, end=1.0, text="Hello.")]
    vtt = write(cues, tmp_path / "out.vtt")
    srt = write(cues, tmp_path / "out.srt")
    assert vtt.startswith("WEBVTT")
    assert srt.splitlines()[0] == "1"
    assert (tmp_path / "out.vtt").read_text(encoding="utf-8") == vtt
    assert (tmp_path / "out.srt").read_text(encoding="utf-8") == srt


def test_a_format_can_be_named_without_a_path() -> None:
    """Rendering without writing is what an API endpoint does."""
    assert write([Cue(start=0.0, end=1.0, text="Hi.")], subtitle_format="srt").startswith("1")


def test_no_format_anywhere_is_refused() -> None:
    """Guessing a caption format is how a .txt full of WEBVTT gets written."""
    with pytest.raises(ValueError, match="no subtitle format"):
        write([Cue(start=0.0, end=1.0, text="Hi.")])


def test_an_unwritable_format_says_which_ones_are(tmp_path: Path) -> None:
    """burn_subtitles reads .ass and .ssa; nothing here writes them."""
    with pytest.raises(ValueError, match="not written here"):
        write([Cue(start=0.0, end=1.0, text="Hi.")], tmp_path / "out.ass", subtitle_format="ass")


def test_a_missing_parent_directory_is_created(tmp_path: Path) -> None:
    """Callers pass an out-dir that may not exist yet; that is not an error."""
    out = write([Cue(start=0.0, end=1.0, text="Hi.")], tmp_path / "deep" / "out.vtt")
    assert (tmp_path / "deep" / "out.vtt").read_text(encoding="utf-8") == out


# ── vtt2srt ────────────────────────────────────────────────────────────────


def test_vtt2srt_writes_beside_its_input(tmp_path: Path) -> None:
    """Every platform that takes a caption upload takes SubRip; plenty still
    do not take WebVTT."""
    source = tmp_path / "captions.vtt"
    source.write_text(
        "WEBVTT\n\n0\n00:00:01.000 --> 00:00:02.500\n<v Ada>Hello.\n", encoding="utf-8"
    )
    written = Path(vtt2srt(str(source)))
    assert written.name == "captions.srt"
    body = written.read_text(encoding="utf-8")
    assert "00:00:01,000 --> 00:00:02,500" in body
    assert "Ada: Hello." in body


def test_vtt2srt_keeps_every_cue(tmp_path: Path) -> None:
    """A conversion that drops a cue shifts every subtitle after it."""
    cues = [Cue(start=float(i), end=i + 0.5, text=f"line {i}") for i in range(40)]
    source = tmp_path / "many.vtt"
    source.write_text(write_vtt(cues), encoding="utf-8")
    body = Path(vtt2srt(str(source))).read_text(encoding="utf-8")
    assert body.count("-->") == 40


# ── Sentences ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("One. Two! Three?", ["One.", "Two!", "Three?"]),
        ("Dr. Rosling said so. Then he left.", ["Dr. Rosling said so.", "Then he left."]),
        ("It cost 3.14 euros. Exactly.", ["It cost 3.14 euros.", "Exactly."]),
        ("Released as v2.5 today.", ["Released as v2.5 today."]),
        ("No terminator here", ["No terminator here"]),
        ("Voir p. 12. Puis la suite.", ["Voir p. 12.", "Puis la suite."]),
        ("J. R. R. Tolkien a écrit cela.", ["J. R. R. Tolkien a écrit cela."]),
        ("Comme en fig. 3, cela tient.", ["Comme en fig. 3, cela tient."]),
        ("", []),
    ],
)
def test_the_splitter_holds_the_cases_two_copies_disagreed_on(
    text: str, expected: list[str]
) -> None:
    """The two implementations this replaces did not agree.

    One broke "v2.5" into three pieces and "Dr. Martin" into two, which puts
    a caption break mid-phrase and a read-along highlight on half a word.
    """
    assert split_sentences(text) == expected


def test_a_closing_quote_is_not_a_sentence() -> None:
    """It was, for four cues of the French narrations: a lone "»" of 120 ms,
    which no voice can say and no viewer can follow."""
    assert split_sentences("« Une question ? »") == ["« Une question ? »"]
