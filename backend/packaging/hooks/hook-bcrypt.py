"""PyInstaller hook for bcrypt.

Bundles the _bcrypt native extension (.pyd on Windows, .so on Linux).
"""
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

binaries = collect_dynamic_libs("bcrypt")
datas = copy_metadata("bcrypt")
hiddenimports = ["bcrypt._bcrypt"]
