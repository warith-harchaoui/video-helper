from setuptools import setup, find_packages

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="video-helper",  
    version="1.0.0",  
    author="Warith Harchaoui, Mohamed Chelali, and Bachir Zerroug",
    author_email="warith.harchaoui@gmail.com", 
    description="A Python library for processing video files using ffmpeg, numpy, vidgear, and os-helper.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/warith-harchaoui/video-helper",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.9',
    install_requires=[
        "ffmpeg-python",
        "opencv-python",
        "numpy",
        "vidgear",
        'os-helper @ git+https://github.com/warith-harchaoui/os-helper.git@main',
        "pillow",
    ],
)
