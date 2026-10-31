"""
Subtitles: one timed-text format layer, read and written in one place.

Why this lives here
-------------------
Subtitles are a video concern. This package already burned them into frames
(:func:`video_helper.burn_subtitles`) and already converted SubRip to WebVTT
(:func:`video_helper.srt2vtt`), while the reading and writing of the formats
themselves sat in ``sprezzature-audio``, which had consolidated four writers
and two readers of its own. That consolidation was right and its differences
are preserved below; what was wrong was the address. A caption file is what a
player shows over a picture, so the package that knows players owns the
format, and the speech packages ask it rather than each keeping a writer.

What came with the move, and what did not
-----------------------------------------
The format layer came: cues, timestamps, the reader, the WebVTT and SubRip
writers. The narration bookkeeping did not. Counting samples while an engine
concatenates audio is a fact about synthesis, not about subtitles, so
``Timeline`` and ``SpeechCue`` stay where the voices are.

The differences the earlier consolidation kept are kept here too, because
each one exists for a reason:

* **Voice tags.** A diarized caption track emits ``<v Name>`` once speakers
  are attributed. A *translated* track deliberately does not: W3C reserves
  voice tags for the same-language ``captions`` track, and a translated
  subtitle is dialogue. Hence ``voices=False`` rather than a guess from
  whether a speaker happens to be set.
* **Identifiers.** The narration path writes each cue's segment index as the
  WebVTT identifier, the line before the timings, which is what lets a page
  highlight the right block without matching on text. Nothing else needs
  them, so an unset ``identifier`` emits nothing.
* **Line structure.** :func:`parse` keeps a cue's newlines, and so does
  :func:`write_vtt`. They are what a renderer breaks lines on and what a
  line-width audit counts, and an older reader that glued them with a space
  could do neither: preserving them took 393 audit findings to zero across
  the 22 subtitle tracks of the suite's films. A caller that wants one line
  asks for it with :meth:`Cue.collapsed` -- which is the narration path, where
  a cue is matched to a page element by its identifier and a blank line in the
  payload would become a second cue and shift every index after it.

  The two callers want opposite things and both are right, so the writer
  preserves what it is given and flattening is an explicit request. The
  decision belongs to the caller, never to the writer, and
  ``test_one_writer_serves_both_callers_and_neither_wins`` pins it.

Stdlib plus ``os-helper`` for logging: no ffmpeg, no OpenCV, nothing that
makes importing a caption writer expensive.

Author
------
`Warith HARCHAOUI, Ph.D. <https://www.linkedin.com/in/warith-harchaoui/>`_
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from pathlib import Path

import os_helper as osh

#: ``HH:MM:SS.mmm --> HH:MM:SS.mmm``, with the hour optional and either
#: decimal separator, so one expression reads WebVTT and SubRip alike.
_TIME = r"(?:(?P<{p}h>\d+):)?(?P<{p}m>\d{{2}}):(?P<{p}s>\d{{2}})[.,](?P<{p}ms>\d{{3}})"
TIMESTAMP_RE = re.compile(
    _TIME.format(p="") + r"\s*-->\s*" + _TIME.format(p="e"),
)

#: A voice tag introducing a speaker: ``<v Ada Lovelace>Hello``.
VOICE_RE = re.compile(r"^<v\s+([^>]+)>\s*")

#: How a voice tag is written back out.
VOICE_CUE = "<v {name}>{text}"

#: Which writer an output extension asks for. The extension is the request:
#: a caller naming ``captions.srt`` has already said what it wants, and making
#: it repeat itself in a second argument is how the two come apart.
FORMAT_FOR_SUFFIX: dict[str, str] = {
    ".vtt": "vtt",
    ".webvtt": "vtt",
    ".srt": "srt",
}

#: Every format this module writes. ``burn_subtitles`` accepts two more,
#: ``.ass`` and ``.ssa``, which it reads and never writes.
WRITABLE_FORMATS: frozenset[str] = frozenset({"vtt", "srt"})


@dataclass(frozen=True)
class Cue:
    """One timed piece of text.

    Attributes
    ----------
    start, end : float
        Seconds from the beginning of the media.
    text : str
        The caption. Newlines are significant: a renderer breaks lines where
        they are, and a line-width audit counts them.
    speaker : str or None
        Who is speaking, when that has been worked out. Written as a
        ``<v Name>`` tag only when the caller asks for voices.
    identifier : str or None
        The optional WebVTT cue identifier, written on the line before the
        timings. The narration path uses it to carry a segment index, so a
        page can follow along without matching on text.
    """

    start: float
    end: float
    text: str
    speaker: str | None = None
    identifier: str | None = None

    @property
    def duration(self) -> float:
        """Length of the cue in seconds."""
        return self.end - self.start

    @property
    def lines(self) -> list[str]:
        """The cue's lines, as a renderer will break them."""
        return [line for line in self.text.splitlines() if line.strip()]

    def collapsed(self) -> Cue:
        """The same cue with its text on one line.

        A blank line ends a cue, so a hard-wrapped payload would split one
        cue into two and shift every identifier after it. Callers that
        assemble text from a document rather than from a transcript want this
        before writing.
        """
        return replace(self, text=" ".join(self.text.split()))


def format_timestamp(seconds: float, *, srt: bool = False) -> str:
    """
    Format seconds as ``HH:MM:SS.mmm`` (WebVTT) or ``HH:MM:SS,mmm`` (SubRip).

    Parameters
    ----------
    seconds : float
        Offset from the start of the media. Negative input clamps to zero: a
        negative timestamp is never meaningful and a renderer's behaviour on
        one is undefined rather than obvious.
    srt : bool, optional
        Use SubRip's comma instead of WebVTT's full stop. The separator is
        the only difference between the two spellings.

    Returns
    -------
    str
        The timestamp.

    Examples
    --------
    >>> format_timestamp(61.34)
    '00:01:01.340'
    >>> format_timestamp(61.34, srt=True)
    '00:01:01,340'
    """
    # Truncated, not rounded. Rounding up lets a cue claim to start before
    # the sample that actually starts it -- half a millisecond early is still
    # early, and for narration the highlight then lands on a word the voice
    # has not reached. The narration path had worked this out and the caption
    # path had not; consolidating the two meant picking the one with a
    # reason, not the one that was written first.
    total_ms = max(0, int(seconds * 1000))
    hours, rest = divmod(total_ms, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    secs, millis = divmod(rest, 1000)
    separator = "," if srt else "."
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def from_centiseconds(value: int) -> float:
    """Convert a whisper.cpp timestamp (10-ms units) to seconds."""
    return value / 100.0


def _seconds(hours: str | None, minutes: str, secs: str, millis: str) -> float:
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(secs) + int(millis) / 1000


def parse(text: str) -> list[Cue]:
    """
    Read a WebVTT or SubRip document into cues.

    Both formats are accepted because this module writes both, and a reader
    holding one has no reason to convert it before doing anything with it.

    Parameters
    ----------
    text : str
        The document's contents.

    Returns
    -------
    list of Cue
        Cues in time order.

    Notes
    -----
    A ``<v Name>`` tag is lifted into :attr:`Cue.speaker` rather than left in
    the text, so a caller that re-writes the cue does not double-tag it, and
    one that does not want voices simply never asks for them.

    Newlines inside a cue are preserved. Callers that want a single line call
    :meth:`Cue.collapsed`.

    A byte-order mark and CRLF endings are tolerated. Both arrive routinely
    from Windows subtitle tools, and both used to land inside the first cue's
    identifier, where they are invisible in a diff and fatal to a parser.
    """
    cues: list[Cue] = []
    lines = text.lstrip("﻿").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    index = 0
    while index < len(lines):
        match = TIMESTAMP_RE.match(lines[index].strip())
        if not match:
            index += 1
            continue
        groups = match.groupdict()
        start = _seconds(groups["h"], groups["m"], groups["s"], groups["ms"])
        end = _seconds(groups["eh"], groups["em"], groups["es"], groups["ems"])

        # A WebVTT identifier sits on the line before the timings; so does a
        # SubRip sequence number. Both are the cue's name, and neither is its
        # text.
        identifier: str | None = None
        if index > 0:
            previous = lines[index - 1].strip()
            if previous and not TIMESTAMP_RE.match(previous):
                identifier = previous

        cursor = index + 1
        body: list[str] = []
        speaker: str | None = None
        while cursor < len(lines) and lines[cursor].strip() != "":
            line = lines[cursor]
            voice = VOICE_RE.match(line.strip())
            if voice is not None:
                speaker = voice.group(1).strip()
                line = VOICE_RE.sub("", line.strip())
            body.append(line.rstrip())
            cursor += 1

        cues.append(
            Cue(
                start=start,
                end=end,
                text="\n".join(body).strip(),
                speaker=speaker,
                identifier=identifier,
            )
        )
        index = cursor + 1

    cues.sort(key=lambda cue: (cue.start, cue.end))
    return cues


def write_vtt(cues: list[Cue], *, voices: bool = True) -> str:
    """
    Render cues as a WebVTT document.

    Parameters
    ----------
    cues : list of Cue
        Timed text. Cues with no text are dropped: a timed blank box is on
        screen for its full duration and says nothing.
    voices : bool, optional
        Write ``<v Name>`` tags for cues that carry a speaker. Default
        ``True``. Pass ``False`` for a translated subtitle track: W3C
        reserves voice tags for the same-language ``captions`` track.

    Returns
    -------
    str
        A WebVTT document, ready to write to a ``.vtt`` file.
    """
    out: list[str] = ["WEBVTT", ""]
    for cue in cues:
        text = cue.text.strip()
        if not text:
            continue
        if cue.identifier:
            out.append(str(cue.identifier))
        out.append(f"{format_timestamp(cue.start)} --> {format_timestamp(cue.end)}")
        out.append(
            VOICE_CUE.format(name=cue.speaker, text=text) if voices and cue.speaker else text
        )
        out.append("")
    return "\n".join(out)


def write_srt(cues: list[Cue]) -> str:
    """
    Render cues as a SubRip document.

    Parameters
    ----------
    cues : list of Cue
        Timed text. Cues with no text are dropped, as in :func:`write_vtt`.

    Returns
    -------
    str
        A SubRip document, ready to write to a ``.srt`` file.

    Notes
    -----
    SubRip has no voice tags, so a speaker is written as a plain prefix: the
    convention every player renders and no player hides. Cues are numbered
    from one, which is SubRip's identifier, so a WebVTT identifier carrying a
    segment index does not survive the trip. That is the format's limit and
    not a choice made here.
    """
    out: list[str] = []
    number = 1
    for cue in cues:
        text = cue.text.strip()
        if not text:
            continue
        out.append(str(number))
        out.append(
            f"{format_timestamp(cue.start, srt=True)} --> {format_timestamp(cue.end, srt=True)}"
        )
        out.append(f"{cue.speaker}: {text}" if cue.speaker else text)
        out.append("")
        number += 1
    return "\n".join(out)


def write(
    cues: list[Cue],
    output_path: str | Path | None = None,
    *,
    subtitle_format: str = "",
    voices: bool = True,
) -> str:
    """
    Render cues in whichever format was asked for, and write them if asked.

    Parameters
    ----------
    cues : list of Cue
        Timed text.
    output_path : str or pathlib.Path or None, optional
        Where to write. The **extension picks the format** (``.vtt``,
        ``.srt``). None renders without writing, and then
        ``subtitle_format`` has to say which format.
    subtitle_format : str, optional
        ``"vtt"`` or ``"srt"``, overriding what the extension says. Needed
        only when there is no path, or when a caller insists on an extension
        that disagrees with its contents.
    voices : bool, optional
        Forwarded to :func:`write_vtt`. SubRip has no voice tags, so it is
        ignored there rather than silently changing the output.

    Returns
    -------
    str
        The rendered document, whether or not it was written.

    Raises
    ------
    ValueError
        If no format can be determined, or the one named is not written here.

    Examples
    --------
    >>> cues = [Cue(start=0.0, end=1.5, text="Bonjour.")]
    >>> write(cues, subtitle_format="srt").splitlines()[0]
    '1'
    """
    requested = (subtitle_format or "").strip().lower().lstrip(".")
    if not requested and output_path is not None:
        requested = FORMAT_FOR_SUFFIX.get(Path(output_path).suffix.lower(), "")
    if not requested:
        raise ValueError(
            "no subtitle format: name one as subtitle_format, or give an "
            f"output_path whose extension is one of {sorted(FORMAT_FOR_SUFFIX)}"
        )
    if requested not in WRITABLE_FORMATS:
        raise ValueError(
            f"{requested!r} is not written here; this module writes "
            f"{sorted(WRITABLE_FORMATS)}. burn_subtitles() also reads .ass / .ssa."
        )

    document = write_srt(cues) if requested == "srt" else write_vtt(cues, voices=voices)
    if output_path is not None:
        target = Path(output_path)
        if str(target.parent) not in ("", "."):
            target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding="utf-8")
        osh.info(f"Subtitles saved: {target}")
    return document


def vtt2srt(vtt_file_path: str, srt_file_path: str | None = None) -> str:
    """
    Convert a WebVTT file to SubRip.

    Parameters
    ----------
    vtt_file_path : str
        Path to the input ``.vtt`` file.
    srt_file_path : str, optional
        Path to the output ``.srt`` file. Defaults to ``<vtt_stem>.srt``
        next to the input.

    Returns
    -------
    str
        Path to the file written.

    Notes
    -----
    The other direction, :func:`video_helper.srt2vtt`, is **not** this
    function's mirror and the asymmetry is deliberate: it also lifts
    ``<font color>`` tags into cue classes and writes the stylesheet that
    binds them, which has no counterpart going the other way because SubRip
    carries its colours inline. Going this way, a voice tag becomes the
    ``Name:`` prefix SubRip players render, and a WebVTT identifier is
    replaced by SubRip's own numbering, which is what the format allows.

    Why it exists at all: every platform that takes a caption upload takes
    SubRip, and plenty still do not take WebVTT. A package that could only
    convert towards WebVTT could not deliver a caption file to the places
    films actually go.

    Examples
    --------
    >>> vtt2srt("captions.vtt")  # doctest: +SKIP
    'captions.srt'
    """
    osh.checkfile(vtt_file_path, msg=f"WebVTT file not found: {vtt_file_path}")

    folder, stem, _ = osh.folder_name_ext(vtt_file_path)
    # A local name rather than the reassigned parameter. `osh.emptystring` is a
    # function call, so a type checker cannot see that the branch leaves the
    # parameter a `str`, and mypy 2.4 reports what mypy 1 passed in silence:
    # `Argument 1 to "Path" has incompatible type "str | None"`. The sibling
    # `srt2vtt` reassigns its parameter the same way and would report the same;
    # this module is new, so it starts clean.
    destination = (
        osh.join([folder, stem + ".srt"]) if osh.emptystring(srt_file_path) else str(srt_file_path)
    )

    cues = parse(Path(vtt_file_path).read_text(encoding="utf-8"))
    Path(destination).write_text(write_srt(cues), encoding="utf-8")
    osh.info(f"SubRip saved: {destination} ({len(cues)} cues)")
    return destination


# ── Sentences ──────────────────────────────────────────────────────────────
#
# A caption is broken at a line width, and a line is broken out of a
# sentence. The splitter lives beside the writers because that is the one
# thing the subtitle layer needs from prose, and because the two copies it
# replaces disagreed: one broke "v2.5" into three pieces and "Dr. Martin"
# into two.

#: Tokens that end in a full stop without ending a sentence. Splitting on
#: ``.`` alone turns "Dr. Rosling said so." into two sentences and a
#: highlight jumps mid-phrase, which is worse than not highlighting at all.
#:
#: Bilingual on purpose, and the French list is not a translation of the
#: English one: ``M.`` is an abbreviation in French and a sentence end in
#: English ("...the M."). Compared case-insensitively, matched on the token
#: before the stop.
ABBREVIATIONS: frozenset[str] = frozenset(
    {
        # English
        "mr",
        "mrs",
        "ms",
        "dr",
        "prof",
        "st",
        "jr",
        "sr",
        "vs",
        "etc",
        "inc",
        "ltd",
        "co",
        "fig",
        "al",
        "e.g",
        "i.e",
        "cf",
        "no",
        "vol",
        "ph.d",
        "approx",
        "dept",
        "est",
        "min",
        "max",
        # French
        "m",
        "mme",
        "mlle",
        "mm",
        "pr",
        "ste",
        "av",
        "bd",
        "env",
        "ex",
        "éd",
        "chap",
        "p",
        "pp",
        "art",
        "réf",
        "tél",
        "pers",
        "sg",
    }
)

#: A sentence ends at one of these, possibly followed by a closing quote or
#: bracket, and then whitespace.
#:
#: ``space`` accepts the end of the block as well as whitespace, and that
#: alternative is load-bearing rather than tidy. ``closers`` is greedy, so on
#: "« Une question ? »" it first takes " »" -- and then ``\\s+`` had nothing
#: left to match, the engine backtracked to ZERO closers, " " satisfied
#: ``\\s+``, and the quote was stranded as a sentence of its own. The same
#: sentence with text after it split correctly, which is why the bug
#: survived: it only fires when the quote closes the block. It put four cues
#: of a lone "»" into the French narrations, 120 ms each.
_SENTENCE_END = re.compile(
    r"""
    (?P<terminator>[.!?…]+)              # one or more terminators (… and ...)
    (?P<closers>
        (?:[   ]*["'”’»\)\]])*   # closing marks that belong to it
    )
    (?P<space>\s+|\Z)                    # the gap before whatever follows
    """,
    re.VERBOSE,
)

#: A fragment with no letter and no digit anywhere in it. Punctuation, a lone
#: closing quote, a dash, a bracket: nothing a voice can read and nothing a
#: viewer can follow.
_HAS_SPEECH = re.compile(r"[^\W_]", re.UNICODE)


def _ends_an_abbreviation(text: str, stop: int) -> bool:
    """Is the full stop at `stop` part of a token that is not a sentence end?"""
    head = text[:stop]
    # No check for decimals here, deliberately. A real decimal separator has
    # a digit straight after it, and `_SENTENCE_END` requires whitespace, so
    # "3.14" can never reach this function. An earlier version guarded
    # against them anyway and paid for it: "Voir p. 12. Puis la suite." was
    # left as one sentence, because the stop after "12" looked decimal.
    #
    # The token before the stop: letters, digits and interior dots, so
    # "e.g" and "Ph.D" are recognised whole rather than by their last letter.
    token = re.split(r"[\s(\[\"'“«]", head)[-1].lower().rstrip(".")
    if not token:
        return False
    if token in ABBREVIATIONS:
        return True
    # A single letter followed by a stop is an initial -- "J. R. R. Tolkien",
    # "W. Harchaoui" -- and never the end of a sentence.
    return len(token) == 1 and token.isalpha()


def _merge_orphans(sentences: list[str]) -> list[str]:
    """Fold fragments that carry no speakable character into their neighbour.

    A belt to the regex's braces. The stranded closing quote has one cause
    and it is fixed in the pattern, but the failure mode is worth refusing
    outright rather than refusing one route to it: a "sentence" of pure
    punctuation is a cue nobody can follow and a segment no voice can say.

    Backwards by preference, because a closing mark belongs to what it
    closes; forwards only for a fragment that opens the block and has nothing
    behind it.

    Examples
    --------
    >>> _merge_orphans(['« Une question ?', '»'])
    ['« Une question ? »']
    >>> _merge_orphans(['»', 'Et la suite.'])
    ['» Et la suite.']
    >>> _merge_orphans(['»'])
    ['»']
    """
    if len(sentences) < 2:
        return sentences
    out: list[str] = []
    for piece in sentences:
        if out and not _HAS_SPEECH.search(piece):
            out[-1] = f"{out[-1]} {piece}"
        else:
            out.append(piece)
    # A leading orphan has nothing behind it to join, so it joins forwards.
    if len(out) > 1 and not _HAS_SPEECH.search(out[0]):
        out[1] = f"{out[0]} {out[1]}"
        out.pop(0)
    return out


def split_sentences(text: str) -> list[str]:
    """
    Split a block of prose into sentences.

    Parameters
    ----------
    text : str
        One block's text, already cleaned of markup.

    Returns
    -------
    list of str
        One entry per sentence, whitespace-collapsed, never empty strings.
        Text with no terminator at all comes back as a single sentence.

    Notes
    -----
    Deliberately a small rule set rather than a model: it has to give the
    same answer for a page and for its audio, run with no dependency, and be
    inspectable when it gets one wrong. It handles terminators with their
    trailing quotes, ellipses, decimals, initials, and the abbreviations in
    :data:`ABBREVIATIONS` for English and French.

    Sentence granularity is the unit a read-along is built on: a paragraph is
    too coarse to follow with the eye, and a word would need forced
    alignment against audio the pipeline generated itself, a statistical
    guess at something already known exactly.

    Examples
    --------
    >>> split_sentences("One. Two! Three?")
    ['One.', 'Two!', 'Three?']
    >>> split_sentences("Dr. Rosling said so. Then he left.")
    ['Dr. Rosling said so.', 'Then he left.']
    >>> split_sentences("It cost 3.14 euros. Exactly.")
    ['It cost 3.14 euros.', 'Exactly.']
    >>> split_sentences("Released as v2.5 today.")
    ['Released as v2.5 today.']
    >>> split_sentences("No terminator here")
    ['No terminator here']
    """
    collapsed = " ".join(text.split())
    if not collapsed:
        return []

    sentences: list[str] = []
    start = 0
    for match in _SENTENCE_END.finditer(collapsed):
        stop = match.start("terminator")
        # Only a lone full stop can be an abbreviation; "!" and "?" and any
        # run of terminators always end the sentence.
        if match.group("terminator") == "." and _ends_an_abbreviation(collapsed, stop):
            continue
        end = match.end("closers")
        piece = collapsed[start:end].strip()
        if piece:
            sentences.append(piece)
        start = match.end("space")

    tail = collapsed[start:].strip()
    if tail:
        sentences.append(tail)
    return _merge_orphans(sentences)
