#!/usr/bin/env python

from setuptools import setup
from setuptools import find_packages


def readme():
    with open("README.rst") as f:
        return f.read()


setup(
    name="kafka-bluesky-live",
    version="0.0.1",
    description="This is a live view for data produced by Bluesky in the so called Documents and streamed via Kafka.",
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
    url="https://gitlab.cnpem.br/SOL/bluesky/kafka-bluesky-live",
    install_requires=[
        "wheel",
        "pyqt5",
        "silx",
        "numpy",
        "python-dateutil",
        "kafka-python",
    ],
    package_data={"kafka_bluesky_live": ["*.ui", "ui/icons/*.png", "ui/icons/*.jpg", "resource/images/*.png"]},
    packages=find_packages(exclude=["test", "test.*"]),
    entry_points={
        "console_scripts": ["kbl=kafka_bluesky_live.scripts.live_view_caller:main"]
    },
)
