# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for ComicStudio Desktop (CPU variant)

Excludes torch/diffusers/xFormers (saves ~2 GB).
Uses ONNX Runtime for local image inference.
Bundle size: ~600 MB
"""
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# CPU variant: ONNX Runtime + llama.cpp + Piper (no torch/diffusers)
hiddenimports = (
    collect_submodules("onnxruntime")
    + collect_submodules("optimum")
    + collect_submodules("llama_cpp")
    + collect_submodules("piper")
    + collect_submodules("huggingface_hub")
    + [
        "app.engines.image.local_onnx",
        "app.engines.llm.local_llm",
        "app.engines.tts.local_tts",
        "app.engines.model_manager",
        "app.core.local_runtime",
        # NOTE: local_diffusers is excluded — torch not bundled
    ]
)

datas = (
    collect_data_files("onnxruntime")
    + collect_data_files("optimum")
)

a = Analysis(
    ["run_backend.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=["./pyinstaller/hooks"],
    runtime_hooks=[],
    excludes=[
        "torch",  # Exclude torch to save ~2GB
        "diffusers",
        "xformers",
        "matplotlib",
        "IPython",
        "notebook",
    ],
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="comicstudio-backend-cpu",
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
    name="comicstudio-backend-cpu",
)
