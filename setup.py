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
 'pillow>=11.0.0,<12.0.0',
 'vidgear>=0.3.3,<0.4.0']

setup_kwargs = {
    'name': 'video-helper',
    'version': '0.1.0',
    'description': 'Video Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats.',
    'long_description': 'Video Helper is a Python library that provides utility functions for processing video files. It includes features like loading, converting, extracting frames as well as working with subtitle formats.',
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

