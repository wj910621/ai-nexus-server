"""PyInstaller hook for asyncpg.

Bundles the pgproto Cython extension and version metadata.
"""
from PyInstaller.utils.hooks import collect_submodules, copy_metadata

hiddenimports = collect_submodules("asyncpg")
hiddenimports += collect_submodules("asyncpg.pgproto")
datas = copy_metadata("asyncpg")
