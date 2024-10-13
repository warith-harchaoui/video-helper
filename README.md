# Video Helper

`Video Helper` belongs to a collection of libraries called `AI Helpers` developed for building Artificial Intelligence.

[🕸️ AI Helpers](https://harchaoui.org/warith/ai-helpers)

[![logo](logo.png)](https://harchaoui.org/warith/ai-helpers)

Video Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats.

# Installation

## Install Package

We recommend using Python environments. Check this link if you're unfamiliar with setting one up:

[🥸 Tech tips](https://harchaoui.org/warith/4ml/#install)

## Install `ffmpeg` 
To use Video Helper, you must install `ffmpeg`:

- For macOS 🍎
  
  Get [brew](https://brew.sh)
  ```bash
  brew install ffmpeg
  ```
- For Ubuntu 🐧
  ```bash
  sudo apt install ffmpeg
  ```
- For Windows 🪟
  Go to the [FFmpeg website](https://ffmpeg.org/download.html) and follow the instructions for downloading FFmpeg. You'll need to manually add FFmpeg to your system PATH.
  

and finally:

```bash
pip install --force-reinstall --no-cache-dir git+https://github.com/warith-harchaoui/video-helper.git@main
```

# Usage
Here’s an example of how to use Video Helper to load, convert, and extract frames from a video file:


```python
import video_helper as vh

# Check if the video file is valid
video_file = "example.mp4"
valid = vh.is_valid_video_file(video_file)

# Get video dimensions and details
details = vh.video_dimensions(video_file)
print(details)

# Convert the video file to a different format
output_video = "video_tests/example_converted.mp4"
vh.video_converter(video_file, output_video)

# Extract frames from the video
for frame in vh.extract_frames(video_file, start_instant=5, end_instant=10, frame_step=5):
    process_frame(frame)  # Replace with your frame processing logic

```

Another example is about subtitles

Convert SRT subtitles to WebVTT with color preservation:


```python
import video_helper as vh

srt_file = "subtitles.srt"
vtt_file = "subtitles.vtt"
css_file = "styles.css"

vh.srt2vtt(srt_file, vtt_file, css_file)
```

# Features
- Video Validation: Check if video files are valid using ffmpeg.
- Video Conversion: Convert videos to different formats, adjust frame rates, and resize while - maintaining aspect ratios.
- Frame Extraction: Extract frames from video files with optional frame skipping and time range selection.
- Subtitle Conversion: Convert SRT subtitles to WebVTT with support for preserving and styling font colors using CSS.
- Frame Processing: Iterate through video frames for custom processing (e.g., image analysis or machine learning).

# Authors
 - [Warith Harchaoui](https://harchaoui.org/warith)
 - [Mohamed Chelali](https://mchelali.github.io)
 - [Bachir Zerroug](https://www.linkedin.com/in/bachirzerroug)

