"""PyInstaller hook for pydantic-core.

Bundles the Rust-compiled _pydantic_core native extension.
"""
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata

binaries = collect_dynamic_libs("pydantic_core")
datas = copy_metadata("pydantic_core")
datas += copy_metadata("pydantic")
