# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ComicStudio AI Backend.

Builds a onedir bundle containing the FastAPI + uvicorn + all deps.
The resulting executable is spawned by the Electron desktop app.
"""
import importlib
import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files, copy_metadata, collect_dynamic_libs

block_cipher = None

# Project root (backend/)
PROJECT_ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
APP_ROOT = os.path.join(PROJECT_ROOT, "app")


def _is_installed(package_name: str) -> bool:
    """Return True if ``package_name`` is importable in this environment."""
    try:
        importlib.import_module(package_name)
        return True
    except ImportError:
        return False


def _safe_collect_submodules(package_name: str):
    """collect_submodules that tolerates missing optional packages."""
    if not _is_installed(package_name):
        print(f"WARNING: optional package '{package_name}' not installed; "
              f"skipping submodule collection for it.")
        return []
    return collect_submodules(package_name)


def _safe_copy_metadata(package_name: str):
    """copy_metadata that tolerates missing packages."""
    try:
        return copy_metadata(package_name)
    except Exception as e:
        print(f"WARNING: no metadata for '{package_name}': {e}")
        return []


# Hidden imports that PyInstaller can't detect statically.
# Optional packages (edge_tts) are collected defensively so the build does
# not break when they are absent from the offline dependency set.
hiddenimports = (
    collect_submodules("app")
    + collect_submodules("uvicorn")
    + collect_submodules("uvicorn.logging")
    + collect_submodules("uvicorn.loops")
    + collect_submodules("uvicorn.loops.auto")
    + collect_submodules("uvicorn.protocols")
    + collect_submodules("uvicorn.protocols.http")
    + collect_submodules("uvicorn.protocols.http.auto")
    + collect_submodules("uvicorn.protocols.websockets")
    + collect_submodules("uvicorn.protocols.websockets.auto")
    + collect_submodules("uvicorn.lifespan")
    + collect_submodules("uvicorn.lifespan.on")
    + collect_submodules("sqlalchemy")
    + collect_submodules("sqlalchemy.dialects")
    + collect_submodules("sqlalchemy.dialects.sqlite")
    + collect_submodules("sqlalchemy.dialects.postgresql")
    + collect_submodules("sqlalchemy.ext.asyncio")
    + collect_submodules("aiosqlite")
    + collect_submodules("asyncpg")
    # edge_tts is an optional dependency (lazy-imported with try/except in
    # app.engines.tts.edge_tts). Only collect when actually installed.
    + _safe_collect_submodules("edge_tts")
    # NOTE: the ffmpeg-python package is NOT used by the app (the video
    # engine shells out to the ffmpeg binary via subprocess), so it is
    # intentionally not collected here.
    + collect_submodules("pydantic")
    + collect_submodules("pydantic_core")
    + collect_submodules("pydantic_settings")
    + collect_submodules("loguru")
    + collect_submodules("jose")
    + collect_submodules("passlib")
    + collect_submodules("passlib.handlers")
    + collect_submodules("passlib.handlers.bcrypt")
    # uvicorn runtime deps that are pure-python and bundled alongside it
    + _safe_collect_submodules("websockets")
    + _safe_collect_submodules("click")
    # Asyncpg protocol modules
    + ["asyncpg.pgproto.pgproto", "asyncpg.protocol", "asyncpg.protocol.protocol"]
    # App-specific
    + ["app.main", "app.core.config", "app.core.database", "app.core.bootstrap",
       "app.core.paths", "app.core.desktop_config"]
    + collect_submodules("app.api")
    + collect_submodules("app.models")
    + collect_submodules("app.schemas")
    + collect_submodules("app.services")
    + collect_submodules("app.engines")
)

# Data files to bundle
datas = (
    _safe_copy_metadata("fastapi")
    + _safe_copy_metadata("pydantic")
    + _safe_copy_metadata("pydantic_core")
    + _safe_copy_metadata("pydantic_settings")
    + _safe_copy_metadata("uvicorn")
    + _safe_copy_metadata("starlette")
    + _safe_copy_metadata("asyncpg")
    + _safe_copy_metadata("aiosqlite")
    + _safe_copy_metadata("loguru")
    + _safe_copy_metadata("websockets")
    + _safe_copy_metadata("click")
    + collect_data_files("app", include_py_files=True)
)

# Native binaries
binaries = (
    collect_dynamic_libs("bcrypt")
    + collect_dynamic_libs("pydantic_core")
)

# Add hooks dir
hookspath = [os.path.join(SPECPATH, "hooks")]

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[PROJECT_ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=hookspath,
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "tkinter",
        "matplotlib",
        "PIL.ImageTk",
        "torch",
        "diffusers",
        "transformers",
        "tensorflow",
        "CUDA",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="comicstudio-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="comicstudio-backend",
)
