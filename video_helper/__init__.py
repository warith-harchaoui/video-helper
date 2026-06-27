# Import necessary modules from the library
from .main import (
    extract_unique_colors,
    srt2vtt,
    is_valid_video_file,
    video_dimensions,
    video_converter,
    extract_frames,
    dump_frames,
    extract_video_chunk,
    video_duration,
    black_video,
    image_loop_to_video,
    concat_videos,
    overlay_image,
    extract_audio_track,
    mux_audio_video,
    burn_subtitles,
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
    'extract_video_chunk',
    'video_duration',
    'black_video',
    'image_loop_to_video',
    'concat_videos',
    'overlay_image',
    'extract_audio_track',
    'mux_audio_video',
    'burn_subtitles',
]
