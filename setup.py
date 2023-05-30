from distutils.core import setup
import py2exe

setup(console=[{"script": "emulator.py", "icon_resources": [(0, "source-content.ico")]}],
      options={"py2exe": {"bundle_files": 2, "ascii": 1, "compressed": 1, "optimize": 2}})