# -*- coding: utf-8 -*-
from pathlib import Path

from setuptools import setup

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

packages = ["video_helper"]

package_data = {"": ["*"]}

install_requires = [
    "ffmpeg-python>=0.2.0,<0.3.0",
    "opencv-python>=4.10.0.84,<5.0.0.0",
    "os-helper @ git+https://github.com/warith-harchaoui/os-helper.git@v1.3.0",
    "vidgear>=0.3.3,<0.4.0",
]

# Optional extras:
#   pyav   — best windowed-sequential + sparse backend, hwaccel support.
#   torch  — destination="torch" (NCHW / CTHW RGB) on cpu / mps / cuda.
#   pil    — destination="pil" (PIL.Image RGB, size=(W, H)).
extras_require = {
    "pyav": ["av>=12,<18"],
    "torch": ["torch>=2.0,<3"],
    "pil": ["pillow>=10,<12"],
    "all": ["av>=12,<18", "torch>=2.0,<3", "pillow>=10,<12"],
}

setup_kwargs = {
    "name": "video-helper",
    "version": "1.5.0",
    "description": (
        "Video Helper is a Python library that provides utility functions for "
        "processing video files: validation, format conversion, frame extraction, "
        "subtitle conversion (SRT/VTT/CSS), temporal cropping, pipeline primitives "
        "(black video, image loop, concat, overlay, audio mux, subtitle burn)."
    ),
    "long_description": long_description,
    "long_description_content_type": "text/markdown",
    "author": "Warith HARCHAOUI",
    "author_email": "Warith HARCHAOUI <warithmetics@deraison.ai>",
    "maintainer": "None",
    "maintainer_email": "None",
    "url": "https://github.com/warith-harchaoui/video-helper",
    "packages": packages,
    "package_data": package_data,
    "install_requires": install_requires,
    "extras_require": extras_require,
    "python_requires": ">=3.10,<3.14",
}


setup(**setup_kwargs)
