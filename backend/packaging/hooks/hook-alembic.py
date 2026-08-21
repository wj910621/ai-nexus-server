"""PyInstaller hook for alembic.

Bundles the Mako template files and script.py.mako used for migrations.
"""
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

datas = collect_data_files("alembic", include_py_files=False)
hiddenimports = collect_submodules("alembic")
hiddenimports += ["alembic.script.py_template", "mako.ext"]
