import pytest
import os_helper as osh
import numpy as np
from typing import List
import urllib.request
from video_helper import (
    extract_unique_colors,
    srt2vtt,
    is_valid_video_file,
    video_dimensions,
    video_converter,
    extract_frames,
    dump_frames
)  


# Define a test video URL
video_url = "https://harchaoui.org/warith/shaky.mp4"
video_filename = "shaky.mp4"

osh.verbosity(0)

overwrite = True

def get_video():
    folder = "video_tests"
    video_file = osh.os_path_constructor([folder, video_filename])
    if not (osh.file_exists(video_file)):
        osh.make_directory(folder)
        urllib.request.urlretrieve(video_url, video_file)
    return video_file


def test_video_dimensions():
    """
    Test that the video dimensions and frame rate can be retrieved correctly.
    """
    video_file = get_video()
    dimensions = video_dimensions(video_file)
    assert "width" in dimensions, "Width not found in video dimensions!"
    assert "height" in dimensions, "Height not found in video dimensions!"
    assert "frame_rate" in dimensions, "Frame rate not found in video dimensions!"
    assert dimensions["duration"] > 0, "Invalid video duration!"


def test_video_conversion():
    """
    Test converting the video with specific parameters.
    """
    video_file = get_video()
    folder, basename, extension = osh.folder_name_ext(video_file)
    output_video_file = basename + "_converted." + extension
    output_video_file = osh.os_path_constructor([folder, output_video_file])

    frame_rate = 15
    width = 1080
    height = 200
    without_sound = True  # Test removing sound for this case

    # Convert the video
    video_converter(
        video_file,
        output_video_file,
        frame_rate=frame_rate,
        width=width,
        height=height,
        without_sound=without_sound,
    )

    # Validate the output video dimensions
    d = video_dimensions(output_video_file)

    assert d["width"] == width, f"Width mismatch: {d['width']} != {width}"
    assert d["height"] == height, f"Height mismatch: {d['height']} != {height}"
    assert (
        round(d["frame_rate"]) == frame_rate
    ), f"Frame rate mismatch: {d['frame_rate']} != {frame_rate}"
    assert d["has_sound"] == (not without_sound), f"Audio mismatch: {d['has_sound']} != {without_sound}"
    assert d["duration"] > 0, "Invalid video duration!"

    # Clean up the output video after testing (optional)


def test_frame_extraction():
    """
    Test frame extraction between specific time intervals.
    """
    video_file = get_video()
    start_instant = 1  # seconds
    end_instant = 2  # 10 seconds
    frame_step = 5  # Extract every 5th frame
    frame_interval = 2  # Extract one frame every 2 seconds

    # Collect extracted frames
    frames = list(
        extract_frames(
            video_file,
            start_instant=start_instant,
            end_instant=end_instant,
            frame_step=frame_step,
        )
    )

    assert len(frames) > 0, "No frames extracted!"
    for frame in frames:
        assert isinstance(frame, np.ndarray), "Extracted frame is not a numpy array!"
        assert frame.shape[-1] == 3, "Frame does not have 3 channels (RGB)!"

    # Validate the frame count
    d = video_dimensions(video_file)
    frame_rate = d["frame_rate"]
    expected_frame_count = int((end_instant - start_instant) * frame_rate / frame_step)
    # Allow a small margin for floating-point inaccuracies
    error = abs(len(frames) - expected_frame_count) 
    assert error <= 2, f"Frame count mismatch: {len(frames)} != {expected_frame_count} ({error})"

    # Validate the frame dimensions
    expected_width = d["width"]
    expected_height = d["height"]
    for frame in frames:
        assert frame.shape[0] == expected_height, f"Height mismatch: {frame.shape[0]} != {expected_height}"
        assert frame.shape[1] == expected_width, f"Width mismatch: {frame.shape[1]} != {expected_width}"

    # Test frame extraction with frame interval instead of frame step
    frames_interval = list(
        extract_frames(
            video_file,
            start_instant=start_instant,
            end_instant=end_instant,
            frame_interval=frame_interval,
        )
    )

    # Validate number of frames extracted using frame_interval
    expected_frame_count_interval = int((end_instant - start_instant) / frame_interval)
    error = abs(len(frames) - expected_frame_count)
    assert error <= 2, f"Frame count mismatch with interval: {len(frames_interval)} != {expected_frame_count_interval} ({error})"


def test_frames_dump():
    """
    Test frame extraction between specific time intervals.
    """
    video_file = get_video()
    frames = list( extract_frames(video_file, stabilize=True) )

    d = video_dimensions(video_file)

    f,b,e = osh.folder_name_ext(video_file)
    o = osh.os_path_constructor([f, "frames.mp4"])
    dump_frames(frames, o, d["frame_rate"])

    assert is_valid_video_file(o), "Invalid video file after dumping frames!"