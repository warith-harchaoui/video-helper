# -*- coding: utf-8 -*-
from setuptools import setup

packages = \
['video_helper']

package_data = \
{'': ['*']}

install_requires = \
['ffmpeg-python>=0.2.0,<0.3.0',
 'numpy>=2.1.2,<3.0.0',
 'opencv-python>=4.10.0.84,<5.0.0.0',
 'os-helper @ git+https://github.com/warith-harchaoui/os-helper.git@main',
 'scikit-image>=0.24.0,<0.25.0',
 'vidgear>=0.3.3,<0.4.0']

setup_kwargs = {
    'name': 'video-helper',
    'version': '0.1.0',
    'description': 'Video Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats.',
    'long_description': '# Video Helper\n\n`Video Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.\n\n[🕸️ AI Helpers](https://harchaoui.org/warith/ai-helpers)\n\n[![logo](logo.png)](https://harchaoui.org/warith/ai-helpers)\n\nVideo Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats.\n\n# Installation\n\n## Install Package\n\nWe recommend using Python environments. Check this link if you\'re unfamiliar with setting one up:\n\n[🥸 Tech tips](https://harchaoui.org/warith/4ml/#install)\n\n## Install `ffmpeg` \nTo use Video Helper, you must install `ffmpeg`:\n\n- For macOS 🍎\n  \n  Get [brew](https://brew.sh)\n  ```bash\n  brew install ffmpeg\n  ```\n- For Ubuntu 🐧\n  ```bash\n  sudo apt install ffmpeg\n  ```\n- For Windows 🪟\n  Go to the [FFmpeg website](https://ffmpeg.org/download.html) and follow the instructions for downloading FFmpeg. You\'ll need to manually add FFmpeg to your system PATH.\n  \n\nand finally:\n\n```bash\npip install --force-reinstall --no-cache-dir git+https://github.com/warith-harchaoui/video-helper.git@main\n```\n\n# Usage\nHere’s an example of how to use Video Helper to load, convert, and extract frames from a video file:\n\n\n```python\nimport video_helper as vh\n\n# Check if the video file is valid\nvideo_file = "example.mp4"\nvalid = vh.is_valid_video_file(video_file) # True or False\n\n# Get video dimensions and details\ndetails = vh.video_dimensions(video_file)\nprint(details)\n# {\'width\': 1920, \'height\': 1080, \'duration\': 10.0, \'frame_rate\': 30.0, \'has_sound\': True}\n\n# Convert the video file to a different format\noutput_video = "video_tests/example_converted.mp4"\nvh.video_converter(video_file, output_video,\n                   frame_rate=30, width=640, without_sound = True)\n\n# The images will never be distorted:\n# aspect ratios are kept even for arbitrary width and height thanks to black padding if necessary\n\n# Extract frames from the video\n\nstart_instant=5 # seconds\n# it corresponds to start_index = start_instant * frame_rate = 5 * 30 = 150th frame\n\nend_instant=10 # seconds\n# it corresponds to end_index = end_instant * frame_rate = 10 * 30 = 300th frame\n\nframe_step=5 # take one frame every 5\n# which corresponds to 1 frame every 5 / frame_rate = 5 / 30 = 0.17 second\n\n# This means that in the video we take 1 frame every 5 from the 150th to the 300th\n\n# List example\nframes = list(\n    vh.extract_frames(video_file, start_instant=start_instant, end_instant=end_instant, frame_step=frame_step)\n)\n\n# For loop example\nfor frame in vh.extract_frames(\n    video_file,\n    start_instant=start_instant,\n    end_instant=end_instant,\n    frame_step=frame_step):\n    pass # Replace with your frame processing logic\n\n# Each frame is a numpy array with shape (height, width, channels)\n# with pixel values between 0 and 255.\n\n```\n\nAnother example is about subtitles\n\nConvert SRT subtitles to WebVTT with color preservation:\n\n\n```python\nimport video_helper as vh\n\nsrt_file = "subtitles.srt"\nvtt_file = "subtitles.vtt"\ncss_file = "subtitles.css"\n\nvh.srt2vtt(srt_file, vtt_file, css_file)\n```\n\n# Features\n- Video Validation: Check if video files are valid using ffmpeg.\n- Video Conversion: Convert videos to different formats, adjust frame rates, and resize while - maintaining aspect ratios.\n- Frame Extraction: Extract frames from video files with optional frame skipping and time range selection.\n- Subtitle Conversion: Convert SRT subtitles to WebVTT with support for preserving and styling font colors using CSS.\n- Frame Processing: Iterate through video frames for custom processing (e.g., image analysis or machine learning).\n\n# Authors\n - [Warith Harchaoui](https://harchaoui.org/warith)\n - [Mohamed Chelali](https://mchelali.github.io)\n - [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug)\n\n',
    'author': 'Warith Harchaoui',
    'author_email': 'warith.harchaoui@gmail.com>, Mohamed Chelali <mohamed.t.chelali@gmail.com>, Bachir Zerroug <bzerroug@gmail.com',
    'maintainer': 'None',
    'maintainer_email': 'None',
    'url': 'None',
    'packages': packages,
    'package_data': package_data,
    'install_requires': install_requires,
    'python_requires': '>=3.12,<4.0',
}


setup(**setup_kwargs)

