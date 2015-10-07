#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

try:
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r').read()

setup(name='applescript_terminal_command',
      version='0.1.0',
      description='AppleScript Terminal Command',
      long_description=read_md('README.md'),
      author='Abtin Gramian',
      author_email='abtin.gramian@gmail.com',
      url='https://github.com/agramian/applescript-terminal-command',
      packages=['applescript_terminal_command'],
      install_requires=[
        'subprocess_manager',
        'shell'
      ],
      download_url = 'https://github.com/agramian/applescript-terminal-command/tarball/v0.1.0',
      keywords = ['applescript', 'terminal', 'app', 'mac', 'osx', 'shell', 'commands'],
      classifiers = [],
     )
