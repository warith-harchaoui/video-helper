import os_helper
import ffmpeg
import numpy as np
from vidgear.gears import VideoGear
from PIL import Image 
import re
from typing import Iterator, List, Set

def extract_unique_colors(srt_file_path: str) -> Set[str]:
    """
    Extract all unique hex color codes from an SRT file.
    
    Parameters
    ----------
    srt_file_path : str
        Path to the input .srt file.
    
    Returns
    -------
    Set[str]
        A set of unique hex color codes found in the .srt file.

    Usage
    -----
    >>> srt_file = "subtitles.srt"
    >>> unique_colors = extract_unique_colors(srt_file)
    >>> print(unique_colors)
    {'#FF0000', '#00FF00', '#0000FF'}
    """
    color_tag_pattern = re.compile(r'<font color="(#\w{6})">', re.IGNORECASE)
    unique_colors = set()
    
    with open(srt_file_path, 'r', encoding='utf-8') as srt_file:
        for line in srt_file:
            # Find all occurrences of <font color="#RRGGBB">
            matches = color_tag_pattern.findall(line)
            # Add all found hex colors to the set (uppercase to avoid duplicates)
            unique_colors.update([match.upper() for match in matches])
    
    return unique_colors

def _generate_css_from_colors(color_codes: Set[str], css_file_path: str) -> None:
    """
    Generate a CSS file with styles for each unique color code.
    
    Parameters
    ----------
    color_codes : Set[str]
        A set of unique hex color codes.
    css_file_path : str
        Path to save the generated CSS file.

    Usage
    -----
    >>> unique_colors = {'#FF0000', '#00FF00', '#0000FF'}
    >>> css_file = "styles.css"
    >>> generate_css_from_colors(unique_colors, css_file)
    
    """
    with open(css_file_path, 'w', encoding='utf-8') as css_file:
        for color in color_codes:
            # Strip the '#' from the color code for the class name and use the hex code for styling
            class_name = color.replace('#', '').lower()
            css_file.write(f"::cue(.{class_name}) {{ color: {color}; }}\n")
    
    print(f"CSS file generated: {css_file_path}")

def srt2vtt(srt_file_path: str, vtt_file_path: str=None, css_file_path: str=None) -> None:
    """
    Converts an SRT subtitle file to a WebVTT file, preserving font colors and generating a CSS file.
    
    Parameters
    ----------
    srt_file_path : str
        Path to the input .srt file.
    vtt_file_path : str, optional
        Path to the output .vtt file.
    css_file_path : str,  optional
        Path to the output CSS file that will be generated. This file will contain styles for each unique color code.

    Usage
    -----
    >>> srt_file = "subtitles.srt"
    >>> vtt_file = "subtitles.vtt"
    >>> css_file = "styles.css"
    >>> convert_srt_to_vtt_with_colors_and_css(srt_file, vtt_file, css_file)
    """
    # Extract all unique hex colors from the .srt file
    unique_colors = extract_unique_colors(srt_file_path)

    f,b,e = os_helper.folder_name_ext(srt_file_path)

    if not vtt_file_path:
        vtt_file_path = os_helper.os_path_constructor([f,b+".vtt"])
    
    if not css_file_path:
        css_file_path = os_helper.os_path_constructor([f,b+".css"])
    
    # Generate the CSS file for these colors
    _generate_css_from_colors(unique_colors, css_file_path)
    
    def convert_color_tags(line: str) -> str:
        """
        Convert HTML <font color> tags to WebVTT-compatible <c.classname> tags.
        
        Parameters
        ----------
        line : str
            The line of subtitle text containing potential <font> tags.
        
        Returns
        -------
        str
            The line with converted WebVTT <c> tags.
        """
        # Regular expression to match <font color="#RRGGBB">...</font>
        color_tag_pattern = re.compile(r'<font color="(#\w{6})">(.*?)<\/font>', re.IGNORECASE)
        
        def replace_color(match: re.Match) -> str:
            color_code = match.group(1).upper()  # Extract color code and convert to uppercase
            text = match.group(2)  # Extract the text inside the font tag
            # Create a WebVTT <c.classname> tag where classname is based on the hex code
            class_name = color_code.replace('#', '').lower()
            return f'<c.{class_name}>{text}</c>'
        
        return color_tag_pattern.sub(replace_color, line)

    # Read the .srt file and convert it to .vtt
    with open(srt_file_path, 'r', encoding='utf-8') as srt_file:
        lines = srt_file.readlines()

    with open(vtt_file_path, 'w', encoding='utf-8') as vtt_file:
        # Write the WebVTT header
        vtt_file.write("WEBVTT\n\n")
        
        for line in lines:
            # Convert <font color> tags to WebVTT <c.classname> tags
            line = convert_color_tags(line)
            # Replace commas with periods in the timecodes
            if '-->' in line:
                line = line.replace(',', '.')
            vtt_file.write(line)

    print(f"Conversion complete! WebVTT saved as: {vtt_file_path}")

def is_valid_video_file(video_file: str) -> bool:
    """
    Check if the input video file is valid.

    Parameters
    ----------
    video_file : str
        Path to the input video file.

    Returns
    -------
    bool
        True if the video file is valid, False otherwise.
    """
    valid = False
    # Check if the file exists
    if not os_helper.file_exists(video_file):
        valid = False
        os_helper.info(f"Video file not found: {video_file}")
        return valid

    try:
        probe = ffmpeg.probe(video_file)
        video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
        valid = True
    except Exception as e:
        valid = False

    os_helper.info(f"Video file {video_file} is {'valid' if valid else 'invalid'}")

    return valid



def video_dimensions(video_file: str) -> dict:
    """
    Get the dimensions of a video file using ffmpeg-python:
    - width
    - height
    - duration
    - frame rate

    Parameters
    ----------
    video_file : str
        Path to the input video file.

    Returns
    -------
    dict
        A dictionary containing the video dimensions:
        - width: int, width of the video in pixels
        - height: int, height of the video in pixels
        - duration: float, duration of the video in seconds
        - frame_rate: float, frame rate of the video in frames per second
        - has_sound: bool, whether the video has sound or not

    Usage
    -----
    >>> video_file = "video.mp4"
    >>> d = video_dimensions(video_file)
    >>> print(d)
    {'width': 1920, 'height': 1080, 'duration': 10.0, 'frame_rate': 30.0, 'has_sound': True}

    Notes
    -----
    The function uses ffmpeg to probe the video file and extract the video stream information to get the dimensions, duration, and frame rate.
    """
    os_helper.checkfile(video_file, msg=f"Video file not found: {video_file}")

    probe = ffmpeg.probe(video_file)
    video_info = next(s for s in probe["streams"] if s["codec_type"] == "video")
    width = int(video_info["width"])
    height = int(video_info["height"])
    duration = float(video_info["duration"])
    frame_rate = video_info["r_frame_rate"]
    frame_rate = frame_rate.split("/")
    frame_rate = float(frame_rate[0]) / float(frame_rate[1])
    has_sound = any(s["codec_type"] == "audio" for s in probe["streams"])
    d = {
        "width": width,
        "height": height,
        "duration": duration,
        "frame_rate": frame_rate,
        "has_sound": has_sound,
    }
    return d



def video_converter(
    input_video: str,
    output_video: str = None,
    frame_rate: int = None,
    width: int = None,
    height: int = None,
    without_sound: bool = False,
):
    """
    Convert a video file to a new format with specified options.

    Parameters
    ----------
    input_video : str
        Path to the input video file.
    output_video : str
        Path to the output video file.
    frame_rate : int, optional
        Frame rate of the output video file.
    width : int, optional
        Width of the output video file. If only width is specified, aspect ratio is maintained. If width is odd, it is reduced by 1 (ffmpeg reasons).
    height : int, optional
        Height of the output video file. If only height is specified, aspect ratio is maintained. If height is odd, it is reduced by 1 (ffmpeg reasons).
    without_sound : bool, optional
        Remove audio from the output video file.

    Notes
    -----
    - The output video file will be in the same format as the input, unless an output file with a different format is specified.
        
    Examples
    --------
    >>> video_converter("input.mp4", "output.mp4", frame_rate=30, width=640, height=480)
    >>> video_converter("input.mp4", "output.mp4", without_sound=True)
    """
    os_helper.info(f"Converting video file:\n\t{input_video}\ninto\n\t{output_video}")

    # Check if the input video file exists and is valid
    os_helper.check(
        is_valid_video_file(input_video),
        msg=f"Input video file not okay:\n\t{input_video}"
    )

    quiet = os_helper.verbosity() <= 0  # Determine verbosity level

    # Extract folder and file extension details
    fi, bi, input_ext = os_helper.folder_name_ext(input_video)
    if os_helper.emptystring(output_video):
        output_video = os_helper.join(fi, bi + "-converted" + "." + input_ext)

    fo, bo, output_ext = os_helper.folder_name_ext(output_video)

    # If no conversion is required, just copy the streams
    if not frame_rate and not width and not height and not without_sound:
        ffmpeg.input(input_video).output(output_video, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
        os_helper.check(
            is_valid_video_file(output_video),
            msg=f"Failed to convert video file:\n\t{output_video}"
        )
        os_helper.info(f"Video file converted successfully:\n{output_video}")
        return

    # Ensure width and height are even
    if width and width % 2 != 0:
        width -= 1
    if height and height % 2 != 0:
        height -= 1

    # Use temporary files for conversion if needed
    with os_helper.temporary_filename(suffix=".mp4", mode="wb") as temp_input, \
         os_helper.temporary_filename(suffix=".mp4", mode="wb") as temp_output:

        # Convert to MP4 if the input video is not already in MP4 format
        if input_ext.lower() != "mp4":
            ffmpeg.input(input_video).output(temp_input, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
        else:
            os_helper.copyfile(input_video, temp_input)  # Direct copy if already MP4

        stream = ffmpeg.input(temp_input)

        # Dictionary to store ffmpeg options
        ffmpeg_options = {}

        # Set the frame rate if specified
        if frame_rate:
            ffmpeg_options["r"] = frame_rate

        # Apply video scaling and padding if needed
        if width and height:
            ffmpeg_options["vf"] = f"scale='min({width},iw*{height}/ih):min({height},ih*{width}/iw)',pad='{width}:{height}:(ow-iw)/2:(oh-ih)/2:black'"
        elif width:
            ffmpeg_options["vf"] = f"scale={width}:-1"  # Maintain aspect ratio
        elif height:
            ffmpeg_options["vf"] = f"scale=-1:{height}"  # Maintain aspect ratio

        # Remove audio if specified
        if without_sound:
            ffmpeg_options["an"] = None  # Disable audio stream

        # Perform the conversion with the specified options
        stream = stream.output(temp_output, **ffmpeg_options)
        stream.run(overwrite_output=True, quiet=quiet)

        # If the output format is not MP4, perform final conversion
        if output_ext.lower() != "mp4":
            ffmpeg.input(temp_output).output(output_video, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
        else:
            os_helper.copyfile(temp_output, output_video)  # Copy to final output if MP4

    # Validate the final output video
    os_helper.check(
        is_valid_video_file(output_video),
        msg=f"Failed to convert video file:\n\t{input_video}\ninto\n\t{output_video}"
    )

    # Retrieve video properties for validation
    d = video_dimensions(output_video)

    # Validate frame rate
    if frame_rate:
        error = round(100 * np.abs(d["frame_rate"] - frame_rate) / frame_rate)
        os_helper.check(
            error < 2,  # Allow slight floating-point variations
            msg=f"Failed to set frame rate for video file ({d['frame_rate']} vs {frame_rate}, error = {error}%):\n\t{output_video}"
        )

    # Validate width and height
    if width:
        os_helper.check(
            d["width"] == width,
            msg=f"Failed to set width for video file:\n\t{output_video}"
        )
    if height:
        os_helper.check(
            d["height"] == height,
            msg=f"Failed to set height for video file:\n\t{output_video}"
        )

    # Validate sound removal
    if without_sound:
        os_helper.check(
            not d["has_sound"],
            msg=f"Failed to remove audio from video file:\n\t{output_video}"
        )

    os_helper.info(f"Video file converted successfully:\n\t{output_video}")







def extract_frames(
    video_path: str,
    start_index: int = None,
    end_index: int = None,
    start_instant: float = None,
    end_instant: float = None,
    stabilize: bool = False,
    frame_step: int = 1,
    frame_interval: float = None,
) -> Iterator[np.ndarray]:
    """
    Extract frames from a video file between the specified start and end indices or time range, with optional frame sampling.
    
    Parameters
    ----------
    video_path : str
        Path to the input video file.
    start_index : int, optional
        Start index of the frame range. If None, starts from the beginning of the video.
    end_index : int, optional
        End index of the frame range. If None, extracts frames until the end of the video.
    start_instant : float, optional
        Start time in seconds. If specified, overrides start_index.
    end_instant : float, optional
        End time in seconds. If specified, overrides end_index.
    stabilize: bool, optional
        If True, stabilizes the video before extracting frames (using VidGear). Defaults to False.
    frame_step : int, optional
        Extract every nth frame. Defaults to 1 (extract every frame).
    frame_interval : float, optional
        Time interval between frames in seconds. Overrides frame_step if specified

    Yields
    ------
    frame : numpy.ndarray
        Extracted frames with shape (height, width, channels) and pixel values between 0 and 255.

    Notes
    -----
    This function uses VidGear's VideoGear for efficient frame extraction. Frame sampling allows skipping frames (e.g., extract every nth frame).
    
    Usage
    -----
    >>> for frame in extract_frames("video.mp4", start_instant=10, end_instant=20, frame_step=5):
    >>>     process_frame(frame)
    """
    # Check if the video file is valid
    os_helper.check(
        is_valid_video_file(video_path),
        msg=f"Video file not okay:\n\t{video_path}",
    )

    # Get video details (dimensions, duration, frame_rate)
    d = video_dimensions(video_path)
    duration = d["duration"]
    frame_rate = d["frame_rate"]

    # Calculate start_index from start_instant, if provided
    if start_instant is not None:
        start_index = int(start_instant * frame_rate)

    # Default start_index to 0 if not provided
    if start_index is None:
        start_index = 0

    # Calculate end_index from end_instant, if provided
    if end_instant is not None:
        end_index = int(end_instant * frame_rate)

    # Default end_index to the last frame if not provided
    if end_index is None:
        end_index = int(duration * frame_rate)

    # Calculate frame_step from frame_interval, if provided
    if frame_interval is not None:
        frame_step = int(frame_interval * frame_rate)

    # Check if start_index and end_index are within the valid frame range
    os_helper.check(
        0 <= start_index <= end_index <= int(duration * frame_rate),
        msg=f"Invalid frame range:\n\t{start_index} ({os_helper.time2str(1.0 * start_index / frame_rate)}) to {end_index} ({os_helper.time2str(1.0 * end_index / frame_rate)}).\n"
        f"It should be within 0 to {int(duration * frame_rate)} (for {os_helper.time2str(duration)} at {frame_rate} fps)",
    )

    # Initialize video stream
    stream = VideoGear(source=video_path, stabilize=stabilize).start()
    current_index = 0  # Start from the first frame

    try:
        # Iterate through video frames
        while True:
            frame = stream.read()

            # If no more frames, exit the loop
            if frame is None:
                break

            # Skip frames until reaching the start_index
            if current_index < start_index:
                current_index += 1
                continue

            # Yield frames only if current_index is within the range and is a multiple of frame_step
            if current_index <= end_index and (current_index - start_index) % frame_step == 0:
                yield frame

            # Stop if end_index is reached
            if current_index > end_index:
                break

            current_index += 1

    finally:
        stream.stop()  # Ensure the video stream is properly closed



def dump_frames(frames_list: List[np.ndarray], output_movie: str, fps: int = 30) -> None:
    """
    Save frames to a video file.

    Parameters
    ----------
    frames_list : List[np.ndarray]
        A list of frames as numpy arrays.
    output_movie : str
        Path to the output video file.
    fps : int, optional
        Frame rate of the output video file. Defaults to 30.

    Notes
    -----
    The function uses VidGear to write the frames to a video file.

    Usage
    -----
    >>> frames = [frame1, frame2, frame3]
    >>> dump_frames(frames, "output.mp4")
    """
    # Check if the frames list is not empty
    os_helper.check(len(frames_list) > 0, msg="No frames to dump!")

    # Get the dimensions of the first frame
    height, width, channels = frames_list[0].shape

    # Check if the dimensions of all frames are consistent
    os_helper.check(
        all(frame.shape == (height, width, channels) for frame in frames_list),
        msg="Frames do not have consistent dimensions!",
    )

    # Extract output file extension
    _, _, output_ext = os_helper.folder_name_ext(output_movie)

    # Determine verbosity level
    quiet = os_helper.verbosity() <= 0

    # Create temp folder with os_helper
    with os_helper.temporary_folder() as temp_folder:
        try:
            # Save each frame as an image in the temp folder
            frame_pattern = os_helper.os_path_constructor([temp_folder, "frame_%09d.png"])
            for i, frame in enumerate(frames_list):
                frame_path = frame_pattern % i
                Image.fromarray(frame).save(frame_path)

            # Generate the video from saved images using ffmpeg
            temp_movie = os_helper.os_path_constructor([temp_folder, "temp_movie.mp4"])
            ffmpeg.input(frame_pattern, framerate=fps).output(temp_movie).run(overwrite_output=True, quiet=quiet)

            # Convert the video format if necessary
            if output_ext.lower() != "mp4":
                ffmpeg.input(temp_movie).output(output_movie, vcodec='copy', acodec='copy').run(overwrite_output=True, quiet=quiet)
            else:
                os_helper.copyfile(temp_movie, output_movie)

        except Exception as e:
            raise RuntimeError(f"Error occurred while dumping frames to video: {e}")

    os_helper.info(f"Video saved successfully: {output_movie}")
