from distutils.core import setup
import py2exe

setup(console=["loginclient.py", "update_blobs.py", "download_app.py"],
      options={"py2exe": {"bundle_files": 2, "ascii": 1, "compressed": 1, "optimize": 2}})