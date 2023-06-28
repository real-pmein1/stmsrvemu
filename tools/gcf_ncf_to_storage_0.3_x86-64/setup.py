from distutils.core import setup
import py2exe

setup(console=["gcf_to_storage.py"],
      options={"py2exe": {"ascii": 1, "compressed": 1, "optimize": 2}})
setup(console=["ncf_to_storage.py"],
      options={"py2exe": {"ascii": 1, "compressed": 1, "optimize": 2}})