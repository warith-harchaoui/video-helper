"""
Test suite package marker for ``video_helper``.

Module summary
--------------
This package groups the pytest modules that exercise the public library,
both CLI surfaces (argparse + click), the FastAPI HTTP surface, and the
frame-extraction backends. It holds no test logic itself — it only makes
``tests`` importable so shared helpers and fixtures resolve cleanly.

Author
------
Project maintainers.
"""

from __future__ import annotations
