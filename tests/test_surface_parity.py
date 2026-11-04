"""The CLI and the HTTP surface expose the same operations, and the README says how many.

README / LISEZMOI promise that every CLI subcommand has its HTTP route (and so
its MCP tool) and the other way round, and they print the count. A subcommand
added to one surface only, or a count left behind, turns this red.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

_ROOT = Path(__file__).resolve().parent.parent
# /mcp appears once any test has imported video_helper.mcp, which mounts it on
# this same app: a transport, not an operation.
_META_ROUTES = {"/health", "/", "/gui"}
_WORDS = {"eighteen": 18, "nineteen": 19, "twenty": 20, "seventeen": 17, "sixteen": 16}
_MOTS = {"dix-huit": 18, "dix-neuf": 19, "vingt": 20, "dix-sept": 17, "seize": 16}


def _operations() -> tuple[set[str], set[str]]:
    from video_helper.api import app
    from video_helper.cli import cli

    routes = {
        r.path.lstrip("/")
        for r in app.routes
        if getattr(r, "methods", None)
        and r.path not in _META_ROUTES
        and not r.path.startswith(("/docs", "/openapi", "/redoc", "/mcp"))
    }
    return set(cli.commands), routes


def test_every_subcommand_has_a_route_and_back() -> None:
    commands, routes = _operations()
    assert commands == routes, {
        "cli only": sorted(commands - routes),
        "http only": sorted(routes - commands),
    }


def test_readme_counts_match_the_surfaces() -> None:
    commands, _ = _operations()
    en = (_ROOT / "README.md").read_text(encoding="utf-8")
    fr = (_ROOT / "LISEZMOI.md").read_text(encoding="utf-8")
    m_en = re.search(r"the (\w+) CLI\s+subcommands and the (\w+) HTTP routes", en)
    m_fr = re.search(
        r"les ([\w-]+)\s+sous-commandes de la CLI répondent une à une aux ([\w-]+)", fr
    )
    assert m_en and m_fr, "the surface sentence moved: update this test with it"
    assert {_WORDS[m_en.group(1)], _WORDS[m_en.group(2)]} == {len(commands)}
    assert {_MOTS[m_fr.group(1)], _MOTS[m_fr.group(2)]} == {len(commands)}
