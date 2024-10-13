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
valid = vh.is_valid_video_file(video_file) # True or False

# Get video dimensions and details
details = vh.video_dimensions(video_file)
print(details)
# {'width': 1920, 'height': 1080, 'duration': 10.0, 'frame_rate': 30.0, 'has_sound': True}

# Convert the video file to a different format
output_video = "video_tests/example_converted.mp4"
vh.video_converter(video_file, output_video)

start_instant=5 # seconds, it corresponds to start_index = start_instant * frame_rate = 5 * 30 = 150th frame

end_instant=10 # seconds, it corresponds to end_index = end_instant * frame_rate = 10 * 30 = 300th frame

frame_step=5 # take one frame every 5 which corresponds to 1 frame every 5 / frame_rate = 5 / 30 = 0.17 second

# This means that in the video we take 1 frame every 5 from the 150th to the 300th

# Extract frames from the video
for frame in vh.extract_frames(
    video_file,
    start_instant=start_instant,
    end_instant=end_instant,
    frame_step=end_instant):
    process_frame(frame)  # Replace with your frame processing logic

# Each frame is a numpy array with shape (height, width, channels) with pixel values between 0 and 255.

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

