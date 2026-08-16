"""
video_helper.faces.models
==========================

Model registry + on-demand downloader for the face stack (detection,
recognition, active-speaker detection).

Sourcing policy (sovereign, HuggingFace-free at runtime)
--------------------------------------------------------
Weights are fetched **on first use** and cached on disk. The registry resolves
each model in this order:

1. **The user's own mirror**: ``AI_HELPERS_MODEL_BASE_URL`` (default
   ``https://harchaoui.org/warith/ai-helpers/models/``). This is the preferred
   path once the mirror is seeded (see ``scripts/seed_model_mirror.py``).
2. **A permissive, HuggingFace-free upstream** (OpenCV Zoo / InsightFace GitHub
   releases) as a first-run convenience so the feature works before the mirror
   exists. Never HuggingFace.

If every source fails the caller gets ``None`` and is expected to degrade
gracefully (e.g. the ASD stack falls back to the zero-weight lip-motion proxy).

Everything is logged through ``os_helper`` (``osh.info/warning/error``); files
land under ``~/.cache/ai-helpers/models/`` (override with
``VIDEO_HELPER_MODEL_DIR``).
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field

import os_helper as osh

# Default mirror on the user's own infrastructure. Runtime downloads prefer this
# so there is no third-party (and specifically no HuggingFace) dependency once it
# is seeded. Override for testing or a private mirror.
DEFAULT_BASE_URL = "https://harchaoui.org/warith/ai-helpers/models/"


def _base_url() -> str:
    return os.environ.get("AI_HELPERS_MODEL_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/"


def model_dir() -> str:
    """Return (creating if needed) the local model cache directory."""
    d = os.environ.get("VIDEO_HELPER_MODEL_DIR") or os.path.expanduser("~/.cache/ai-helpers/models")
    osh.make_directory(d)
    return d


@dataclass(frozen=True)
class ModelSpec:
    """One downloadable weight file.

    Parameters
    ----------
    name : str
        Registry key (also the CLI/config-facing identifier).
    filename : str
        On-disk basename under the cache dir and path segment on the mirror.
    sha256 : str
        Expected hex digest, or ``""`` to skip integrity checking (used until
        the mirror is seeded and digests are pinned).
    upstreams : list[str]
        HuggingFace-free fallback URLs tried, in order, only if the mirror miss.
    license : str
        SPDX-ish tag; ``noncommercial`` models are gated by the caller.
    """

    name: str
    filename: str
    sha256: str = ""
    upstreams: list[str] = field(default_factory=list)
    license: str = "unknown"


# OpenCV Zoo raw GitHub (Apache-2.0, HuggingFace-free) — the permissive defaults.
_ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"

REGISTRY: dict[str, ModelSpec] = {
    # Face detection + 5 landmarks — tiny, fast, Apache-2.0.
    "yunet": ModelSpec(
        name="yunet",
        filename="face_detection_yunet_2023mar.onnx",
        upstreams=[f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx"],
        license="Apache-2.0",
    ),
    # Face recognition embedding (128-d), Apache-2.0.
    "sface": ModelSpec(
        name="sface",
        filename="face_recognition_sface_2021dec.onnx",
        upstreams=[f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx"],
        license="Apache-2.0",
    ),
    # Active-speaker detection (Light-ASD), run as a real PyTorch net (see
    # faces/asd.py — no ONNX export, the MFCC front-end doesn't survive one faithfully).
    # Seeded on the project's own mirror; falls back to the zero-weight lip-motion
    # proxy if this and AI_HELPERS_MODEL_BASE_URL both miss.
    "light-asd": ModelSpec(
        name="light-asd",
        filename="light_asd.pth",
        sha256="efc375833887eefa9d209dc92810e18519b04c3c73ea35a549f2a7f40b7d94d5",
        upstreams=["https://deraison.ai/4ai/light_asd.pth"],
        license="research",
    ),
}


def _verify(path: str, sha256: str) -> bool:
    """Return True if ``path`` matches ``sha256`` (or no digest was pinned)."""
    if not sha256:
        return True
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    ok = h.hexdigest() == sha256
    if not ok:
        osh.warning(f"faces.models: checksum mismatch for {os.path.basename(path)}")
    return ok


def ensure_model(name: str) -> str | None:
    """Resolve a model to a local path, downloading + caching on first use.

    Parameters
    ----------
    name : str
        A key in :data:`REGISTRY`.

    Returns
    -------
    str or None
        Local filesystem path to the ready weight, or ``None`` if the model could
        not be fetched from any source (the caller degrades gracefully).
    """
    spec = REGISTRY.get(name)
    if spec is None:
        osh.warning(f"faces.models: unknown model {name!r}")
        return None

    dest = osh.join(model_dir(), spec.filename)
    if osh.file_exists(dest) and _verify(dest, spec.sha256):
        return dest

    # Prefer the user's mirror, then HuggingFace-free upstreams.
    sources = [_base_url() + spec.filename, *spec.upstreams]
    for url in sources:
        try:
            osh.info(f"faces.models: fetching {name} from {url}")
            osh.download_file(url, dest, check_url=False)
            if _verify(dest, spec.sha256):
                return dest
        except Exception as exc:  # noqa: BLE001 — try the next source, never crash the pipeline
            osh.warning(f"faces.models: source failed ({url}): {exc}")
            continue

    osh.warning(
        f"faces.models: could not obtain {name!r} from any source — "
        "the caller must degrade gracefully"
    )
    return None
