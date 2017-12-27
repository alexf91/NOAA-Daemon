#!/usr/bin/env python

from setuptools import setup

setup(name='noaa-daemon',
    version='0.1',
    description='Automatically record NOAA satellite transmissions',
    author='Alexander Fasching',
    author_email='fasching.a91@gmail.com',
    maintainer='Alexander Fasching',
    maintainer_email='fasching.a91@gmail.com',
    url='https://github.com/alexf91/NOAA-Daemon',
    license='GPL',
    packages=['noaad'],
    entry_points={
        'console_scripts': ['noaad = noaad.__main__:main']
    },
    install_requires=[
        'configparser',
        'ephem',
        'setproctitle',
        'trollius'
    ],
)
