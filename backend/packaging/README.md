# Backend Packaging

This directory contains scripts and configs for packaging the Python backend
into a standalone executable using PyInstaller.

## Files

- `__init__.py` — Package marker (avoids stdlib `packaging` conflict)
- `entry.py` — Entry point script (what PyInstaller bundles)
- `runtime.py` — Runtime path resolution (frozen vs development)
- `build.py` — Build script wrapper (calls PyInstaller with spec)
- `verify_spec.py` — Spec file integrity checker (6 checks)
- `comicstudio_backend.spec` — PyInstaller spec file (onedir mode)
- `hooks/` — Custom PyInstaller hooks for native modules

## Quick Start

```bash
# From backend/ directory:

# 1. Install PyInstaller + aiosqlite (Python 3.14+ compatible)
python -m pip install --target .deps pyinstaller==6.21.0 aiosqlite==0.19.0

# 2. Verify spec
python packaging/verify_spec.py

# 3. Build (clean first)
python packaging/build.py --clean

# 4. Test the executable
./dist/comicstudio-backend/comicstudio-backend.exe --port 8765

# 5. In another terminal:
curl http://127.0.0.1:8765/health
```

## Hooks

Each hook in `hooks/` tells PyInstaller how to bundle a specific native module:

| Hook | Purpose |
|------|---------|
| `hook-asyncpg.py` | asyncpg Cython extensions + version metadata |
| `hook-bcrypt.py` | bcrypt `_bcrypt.pyd` native extension |
| `hook-loguru.py` | loguru dynamically-loaded sinks |
| `hook-pydantic_core.py` | pydantic-core Rust-compiled extension |
| `hook-alembic.py` | alembic Mako templates + script.py.mako |
| `hook-ffmpeg_python.py` | ffmpeg-python `_run.py` template |

## Build Output

After a successful build, `dist/comicstudio-backend/` contains:

```
comicstudio-backend/
├── comicstudio-backend.exe   # Main executable (~16 MB)
└── _internal/                # Dependencies (Python runtime + all packages)
    ├── base_library.zip
    ├── *.pyd
    └── ...
```

## Troubleshooting

### ModuleNotFoundError during build

Add the missing module to `hiddenimports` in `comicstudio_backend.spec`:

```python
hiddenimports = (
    ...
    + ["your.missing.module"]  # Add here
)
```

Then rebuild: `python packaging/build.py --clean`

### ImportError at runtime (DLL load failed)

Check the `hooks/` directory — a native module's hook may be missing or incomplete.
Use `collect_dynamic_libs("module_name")` in the relevant hook.

### `packaging` module conflict (stdlib)

Python has a stdlib `packaging` module. The local `packaging/` dir takes precedence
when running from `backend/` root (because `__init__.py` makes it a proper package).
If imports fail, ensure:
1. `packaging/__init__.py` exists
2. PYTHONPATH has `backend/` before `.deps`

### Build is slow

PyInstaller analyzes all imports statically. First build takes 5-15 minutes.
Subsequent builds with `--noconfirm` (no `--clean`) reuse cache and are faster.

## See Also

- `docs/deployment/desktop-packaging.md` — Full desktop packaging guide (Chinese)
- `docs/deployment/local-deployment.md` — Local development deployment
