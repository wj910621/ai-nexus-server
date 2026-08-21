"""PyInstaller hook for loguru.

Loguru loads default sinks dynamically; ensure they're bundled.
"""
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = collect_submodules("loguru")
hiddenimports += ["loguru._colorizer", "loguru._file_sink", "loguru._defaults"]
