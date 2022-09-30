#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages


def readme():
    with open("README.md") as f:
        return f.read()


setup(
    name="bqs_live",
    version="0.0.1",
    description="A Module to plot bluesky queue server data streamed through Kafka",
    long_description=readme(),
    classifiers=[
        "Development Status :: 1 - Planning",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
    ],
    author="Hugo Campos",
    author_email="hugo.campos@lnls.br",
    url="https://gitlab.cnpem.br/SOL/bluesky/bqs_live",
    install_requires=[
        "wheel",
        "PyQt5",
        "silx",
        "numpy",
        "python-dateutil",
        "python-kafka"
    ],
    package_data={"bqs_live": ["*.ui", "icons/*.png"]},
    packages=find_packages(exclude=["test", "test.*"]),
    entry_points={"console_scripts": ["bqs_live=bqs_live.scripts.live_view_caller:main"]},
)
