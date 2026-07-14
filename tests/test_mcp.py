"""
Smoke test for the MCP surface (``video_helper.mcp``).

Verifies that the MCP wrapper around the FastAPI app imports without
error, exposes the underlying FastAPI ``app`` object, and that the
``mcp`` handler is attached. Full protocol round-trips belong to a
separate integration suite once the MCP client tooling is stable in
CI.

Usage Example
-------------
>>> #   pytest tests/test_mcp.py

Author
------
Warith Harchaoui, Ph.D. — https://linkedin.com/in/warith-harchaoui/
"""

from __future__ import annotations

import pytest

# fastapi_mcp lives in the ``[mcp]`` optional extra — skip cleanly if absent.
pytest.importorskip("fastapi_mcp")


def test_mcp_module_imports_and_exposes_app() -> None:
    """The MCP module must import and re-expose the FastAPI app + mcp handler."""
    from video_helper import mcp as mcp_module

    assert hasattr(mcp_module, "app"), "video_helper.mcp must re-expose `app`."
    assert hasattr(mcp_module, "mcp"), "video_helper.mcp must expose the `mcp` handler."


def test_main_entrypoint_is_callable() -> None:
    """The ``video-helper-mcp`` console entry point should be a callable."""
    from video_helper.mcp import main

    assert callable(main)
