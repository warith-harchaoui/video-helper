#!/usr/bin/env python3
"""Seed a self-hosted mirror of the face-stack model weights (run once).

The runtime (:mod:`video_helper.faces.models`) downloads weights **only from your
own mirror** (``AI_HELPERS_MODEL_BASE_URL``) — never from HuggingFace. This script
is the one-time bootstrap that *populates* that mirror: it fetches each weight
from its permissive, HuggingFace-free upstream, records a SHA-256, and lays the
files out in a folder you then upload to your server.

Policy
------
- Defaults (YuNet, SFace) come from the **OpenCV Zoo GitHub** (Apache-2.0) — no
  HuggingFace involved at all.
- HuggingFace is permitted **once, here only**, and only for a weight that is
  available nowhere else, via ``--allow-hf`` (off by default). It is never used at
  runtime. This keeps the standing "no HuggingFace" rule intact for the shipped
  product while letting you self-host whatever you need.

Usage
-----
    python scripts/seed_model_mirror.py --out ./model_mirror
    # then upload ./model_mirror/* to  https://<your-host>/warith/ai-helpers/models/
    # and (optionally) paste the printed SHA-256 digests into
    # video_helper/faces/models.py so the runtime verifies integrity.

The Light-ASD weight has no public permissive URL we control; fetch the
authors' PyTorch checkpoint yourself and drop ``light_asd.pth`` into the
output folder before uploading.
"""

from __future__ import annotations

import hashlib
import os

import click
import os_helper as osh

from video_helper.faces.models import REGISTRY

# HuggingFace-free upstreams, per model. Extend as needed; keep GitHub/first-party.
UPSTREAMS: dict[str, str] = {
    "yunet": REGISTRY["yunet"].upstreams[0],
    "sface": REGISTRY["sface"].upstreams[0],
    # "light-asd": "<your PyTorch checkpoint, dropped in manually>",
}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--out",
    default="./model_mirror",
    show_default=True,
    help="Output folder to upload to your host.",
)
@click.option(
    "--allow-hf",
    is_flag=True,
    help="Permit a one-time HuggingFace fetch for a weight available nowhere else.",
)
def main(out: str, allow_hf: bool) -> None:
    """Seed a self-hosted mirror of the face-stack model weights (run once).

    \f

    Everything after the form feed is for readers of the source: click truncates
    ``--help`` there, so the numpydoc block below never reaches the terminal —
    which also keeps the module docstring's RST markup out of it (argparse used
    to print the whole thing, double backticks and section underlines included).

    Parameters
    ----------
    out : str
        Output folder the weights land in, to be uploaded to your host.
    allow_hf : bool
        Permit the one-time HuggingFace fetch for a weight available nowhere
        else; off by default, and never used at runtime.
    """
    osh.make_directory(out)

    digests: dict[str, str] = {}
    for name, spec in REGISTRY.items():
        url = UPSTREAMS.get(name)
        if not url:
            osh.warning(
                f"{name}: no permissive upstream configured — export/drop "
                f"'{spec.filename}' into {out} manually before uploading."
            )
            continue
        if "huggingface.co" in url and not allow_hf:
            osh.warning(
                f"{name}: upstream is HuggingFace; re-run with --allow-hf to fetch it once."
            )
            continue
        dest = osh.join(out, spec.filename)
        osh.info(f"{name}: fetching {url}")
        osh.download_file(url, dest, check_url=False)
        digests[name] = _sha256(dest)

    osh.info("Seeded mirror. SHA-256 digests (paste into faces/models.py to pin integrity):")
    for name, digest in digests.items():
        osh.info(f'  {name}: sha256="{digest}"')
    osh.info(f"Upload the contents of {os.path.abspath(out)} to your model base URL.")


if __name__ == "__main__":
    main()
