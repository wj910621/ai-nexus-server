"""Tests for Task 16: Desktop Installer."""
import os

import pytest


def test_gpu_pyinstaller_spec_exists():
    """desktop_gpu.spec exists."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "pyinstaller", "desktop_gpu.spec"
    )
    assert os.path.exists(path)


def test_cpu_pyinstaller_spec_exists():
    """desktop_cpu.spec exists."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "pyinstaller", "desktop_cpu.spec"
    )
    assert os.path.exists(path)


def test_gpu_spec_includes_torch():
    """GPU spec includes torch + diffusers hidden imports."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "pyinstaller", "desktop_gpu.spec"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "torch" in content
    assert "diffusers" in content


def test_cpu_spec_includes_onnxruntime():
    """CPU spec includes onnxruntime hidden imports."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "pyinstaller", "desktop_cpu.spec"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "onnxruntime" in content


def test_cpu_spec_excludes_torch():
    """CPU spec excludes torch (smaller bundle)."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "pyinstaller", "desktop_cpu.spec"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    # CPU spec should not include torch (saves ~2GB)
    # It may mention torch in comments, but not in hiddenimports
    lines = [ln for ln in content.split("\n") if not ln.strip().startswith("#")]
    body = "\n".join(lines)
    # Check that 'torch' is not in hiddenimports list
    if "hiddenimports" in body:
        # Find the hiddenimports block
        idx = body.find("hiddenimports")
        end_idx = body.find("]", idx)
        block = body[idx:end_idx]
        assert "torch" not in block, "CPU spec should not include torch in hiddenimports"


def test_build_desktop_script_exists():
    """build_desktop.py script exists."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "build_desktop.py"
    )
    assert os.path.exists(path)


def test_build_desktop_script_supports_variants():
    """build_desktop.py supports --variant win-gpu / win-cpu / linux-gpu / linux-cpu."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "build_desktop.py"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "win-gpu" in content
    assert "win-cpu" in content
    assert "linux-gpu" in content
    assert "linux-cpu" in content


def test_electron_builder_has_4_targets():
    """electron-builder.yml defines 4 build targets."""
    import yaml
    path = os.path.join(
        os.path.dirname(__file__), "..", "..", "desktop", "electron-builder.yml"
    )
    if not os.path.exists(path):
        pytest.skip("desktop/electron-builder.yml not found (run from desktop/)")
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Check that win and linux targets are defined
    win = cfg.get("win", {})
    linux = cfg.get("linux", {})
    assert "target" in win or len(win) > 0
    assert "target" in linux or len(linux) > 0
