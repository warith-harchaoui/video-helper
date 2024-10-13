# Import necessary modules from the library
from .main import (
    extract_unique_colors,
    srt2vtt,
    is_valid_video_file,
    video_dimensions,
    video_converter,
    extract_frames,
    dump_frames
)

# Define the public API for the library
__all__ = [
    'extract_unique_colors',
    'srt2vtt',
    'is_valid_video_file',
    'video_dimensions',
    'video_converter',
    'extract_frames',
    'dump_frames',
]
