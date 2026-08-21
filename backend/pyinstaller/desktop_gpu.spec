# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ComicStudio Desktop (GPU variant)

Includes torch + diffusers + xFormers for NVIDIA GPU local inference.
Bundle size: ~2.5 GB
"""
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all submodules for AI libraries
hiddenimports = (
    collect_submodules("torch")
    + collect_submodules("diffusers")
    + collect_submodules("transformers")
    + collect_submodules("accelerate")
    + collect_submodules("xformers")
    + collect_submodules("llama_cpp")
    + collect_submodules("piper")
    + collect_submodules("onnxruntime")
    + collect_submodules("huggingface_hub")
    + [
        "app.engines.image.local_diffusers",
        "app.engines.image.local_onnx",
        "app.engines.llm.local_llm",
        "app.engines.tts.local_tts",
        "app.engines.model_manager",
        "app.core.local_runtime",
    ]
)

datas = (
    collect_data_files("torch")
    + collect_data_files("diffusers")
    + collect_data_files("transformers")
    + collect_data_files("xformers")
)

a = Analysis(
    ["run_backend.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["./pyinstaller/hooks"],
    runtime_hooks=[],
    excludes=["matplotlib", "IPython", "notebook"],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="comicstudio-backend-gpu",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="comicstudio-backend-gpu",
)
