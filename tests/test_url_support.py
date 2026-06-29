"""
v1.5.2 — URL-aware ``is_valid_video_file`` and ``video_dimensions``.

Unit tests for the cheap URL-handling additions: ``is_valid_video_file``
short-circuits to ``True`` for ``http://`` / ``https://`` inputs (since
the only way to really validate is to download), and
``video_dimensions`` accepts an optional ``http_headers`` kwarg that it
forwards to ``ffprobe`` for URL inputs.

These tests are network-free: they only exercise the short-circuit and
the keyword acceptance (we don't actually ffprobe a URL — that would
require network).
"""

from __future__ import annotations

import inspect

import pytest

from video_helper import is_valid_video_file, video_dimensions


# ---------------------------------------------------------------------------
# is_valid_video_file — URL short-circuit
# ---------------------------------------------------------------------------


def test_is_valid_video_file_trusts_https_url() -> None:
    """An https URL is trusted (would need bandwidth to verify otherwise)."""
    assert is_valid_video_file("https://example.com/sample.mp4") is True


def test_is_valid_video_file_trusts_http_url() -> None:
    """An http URL is trusted too — same rationale."""
    assert is_valid_video_file("http://example.com/sample.mp4") is True


def test_is_valid_video_file_trusts_url_with_unusual_extension() -> None:
    """yt-dlp-resolved URLs often end in ``.m3u8`` / ``.mpd`` or no ext at all."""
    assert is_valid_video_file("https://manifest.example.com/live.m3u8") is True
    assert is_valid_video_file("https://stream.example.com/path?token=xyz") is True


def test_is_valid_video_file_rejects_missing_local_file() -> None:
    """Local-file negative path still works exactly as before."""
    assert is_valid_video_file("/tmp/definitely_not_a_real_file_xyz.mp4") is False


# ---------------------------------------------------------------------------
# video_dimensions — new http_headers kwarg
# ---------------------------------------------------------------------------


def test_video_dimensions_accepts_http_headers_kwarg() -> None:
    """
    Signature should now accept ``http_headers``. We don't invoke it
    against a real URL (would require network); we just confirm the
    keyword is reachable so callers can pass yt-dlp headers through.
    """
    sig = inspect.signature(video_dimensions)
    assert "http_headers" in sig.parameters
    # Default is None — callers shouldn't need to wire anything for
    # local-file probes.
    assert sig.parameters["http_headers"].default is None


def test_video_dimensions_local_file_no_headers_required() -> None:
    """Local-file probes never need ``http_headers`` and never read them."""
    # No file at this path → ``osh.checkfile`` raises. We only need to
    # confirm the call path; the actual exception type is asserted
    # elsewhere.
    with pytest.raises(Exception):
        video_dimensions("/tmp/nonexistent_video_xyz.mp4")
