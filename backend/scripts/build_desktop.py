"""Desktop build orchestration script

Builds 4 variants of the ComicStudio desktop app:
- win-gpu:  Windows + NVIDIA GPU local inference (~2.5 GB)
- win-cpu:  Windows + CPU-only local inference (~600 MB)
- linux-gpu: Linux + NVIDIA GPU local inference
- linux-cpu: Linux + CPU-only local inference

Usage:
    python scripts/build_desktop.py --variant win-gpu
    python scripts/build_desktop.py --variant all
"""
import argparse
import subprocess
import sys
from pathlib import Path

VARIANTS = {
    "win-gpu": {
        "backend_spec": "pyinstaller/desktop_gpu.spec",
        "desktop_target": "nsis-gpu",
        "requires_torch": True,
        "platform": "win32",
    },
    "win-cpu": {
        # Production CPU packages are remote-API clients. They must not
        # silently include a local inference runtime under a CPU label.
        "backend_spec": None,
        "desktop_target": "nsis-cpu",
        "requires_torch": False,
        "remote_only": True,
        "platform": "win32",
    },
    "linux-gpu": {
        "backend_spec": "pyinstaller/desktop_gpu.spec",
        "desktop_target": "appimage-gpu",
        "requires_torch": True,
        "platform": "linux",
    },
    "linux-cpu": {
        "backend_spec": "pyinstaller/desktop_cpu.spec",
        "desktop_target": "appimage-cpu",
        "requires_torch": False,
        "platform": "linux",
    },
}


def build_backend(variant: str) -> Path:
    """Build backend executable with PyInstaller."""
    if VARIANTS[variant].get("remote_only"):
        print(f"[1/2] Skipping local backend for {variant}; package is remote-API only")
        return Path()
    spec = VARIANTS[variant]["backend_spec"]
    print(f"[1/2] Building backend ({variant}) via {spec}")
    subprocess.run(
        ["pyinstaller", spec, "--noconfirm", "--clean"],
        check=True,
    )
    # Return path to built backend
    if variant.endswith("-gpu"):
        return Path("dist/comicstudio-backend-gpu")
    return Path("dist/comicstudio-backend-cpu")


def build_desktop(variant: str) -> Path:
    """Build desktop Electron app for the variant."""
    target = VARIANTS[variant]["desktop_target"]
    print(f"[2/2] Building desktop Electron app ({variant}) → {target}")
    desktop_dir = Path(__file__).parent.parent.parent / "desktop"
    subprocess.run(
        ["npm", "run", "build:variant", "--", "--target", target],
        cwd=desktop_dir,
        check=True,
    )
    return desktop_dir / "dist"


def install_dependencies(variant: str) -> None:
    """Install Python dependencies for the variant."""
    if VARIANTS[variant].get("remote_only"):
        print(f"[0/2] Skipping Python inference dependencies for {variant}; remote-API only")
        return
    print(f"[0/2] Installing dependencies for {variant}")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", "desktop-requirements.txt"],
        check=True,
    )


def build_variant(variant: str) -> None:
    """Full build pipeline for a single variant."""
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant: {variant}. Choices: {list(VARIANTS)}")
    print(f"\n=== Building {variant} ===")
    install_dependencies(variant)
    build_backend(variant)
    build_desktop(variant)
    print(f"✓ {variant} build complete")


def main():
    parser = argparse.ArgumentParser(description="ComicStudio desktop builder")
    parser.add_argument(
        "--variant",
        choices=list(VARIANTS.keys()) + ["all"],
        default="all",
        help="Which variant to build (default: all)",
    )
    args = parser.parse_args()

    if args.variant == "all":
        for v in VARIANTS:
            build_variant(v)
    else:
        build_variant(args.variant)


if __name__ == "__main__":
    main()
