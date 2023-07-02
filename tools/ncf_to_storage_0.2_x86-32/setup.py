from distutils.core import setup
import py2exe

setup(console=["ncf_to_storage.py"],
      options={"py2exe": {"bundle_files": 2, "ascii": 1, "compressed": 1, "optimize": 2}})