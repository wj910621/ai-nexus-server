"""PyInstaller hook for ffmpeg-python.

ffmpeg-python has a _run.py template that's loaded dynamically.

This hook is defensive: the ComicStudio backend does not actually import
the ``ffmpeg`` Python package (the video engine shells out to the ffmpeg
binary via subprocess), so the package may be absent from the offline
dependency set. ``collect_submodules``/``collect_data_files`` are only
called when the package is importable.
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

try:
    hiddenimports = collect_submodules("ffmpeg")
except Exception:
    hiddenimports = []

try:
    datas = collect_data_files("ffmpeg")
except Exception:
    datas = []
