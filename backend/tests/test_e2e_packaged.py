"""End-to-end tests for the packaged backend.

These tests spawn the built executable and verify it serves requests.
They are skipped if the executable doesn't exist (e.g., in CI without build).
"""
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXECUTABLE_PATH = (
    PROJECT_ROOT
    / "dist"
    / "comicstudio-backend"
    / ("comicstudio-backend.exe" if os.name == "nt" else "comicstudio-backend")
)


def find_free_port() -> int:
    """Find a free TCP port for the test server."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def wait_for_health(url: str, timeout: float = 60.0) -> bool:
    """Poll /health until it responds or timeout."""
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(f"{url}/health", timeout=2.0)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


@pytest.mark.skipif(not EXECUTABLE_PATH.exists(), reason="Packaged executable not built")
class TestPackagedBackend:
    """Tests that spawn the packaged backend executable."""

    @pytest.fixture
    def backend_process(self, tmp_path):
        """Start the packaged backend on a free port.

        stdout/stderr are redirected to temp files instead of PIPE because
        the backend emits a large volume of SQLAlchemy engine logs at startup
        (CREATE TABLE statements, PRAGMA queries, etc.). If the pipes are not
        actively drained the OS pipe buffer fills up (~64KB on Windows) and
        the backend's writes block, preventing it from ever reaching the
        uvicorn accept loop. Temp files avoid this deadlock entirely.
        """
        port = find_free_port()
        env = os.environ.copy()
        env["CS_DESKTOP_MODE"] = "1"
        env["CS_DATA_DIR"] = str(tmp_path)
        env["APP_PORT"] = str(port)
        env["APP_HOST"] = "127.0.0.1"
        # Remove PYTHONPATH to ensure frozen exe is self-contained
        env.pop("PYTHONPATH", None)
        env.pop("PYTHONHOME", None)

        # Use temp files so backend output never blocks on a full pipe.
        stdout_path = tmp_path / "backend_stdout.log"
        stderr_path = tmp_path / "backend_stderr.log"
        stdout_fh = open(stdout_path, "w", encoding="utf-8", errors="replace")
        stderr_fh = open(stderr_path, "w", encoding="utf-8", errors="replace")

        proc = subprocess.Popen(
            [str(EXECUTABLE_PATH), "--port", str(port), "--host", "127.0.0.1"],
            stdout=stdout_fh,
            stderr=stderr_fh,
            env=env,
        )

        url = f"http://127.0.0.1:{port}"
        try:
            if not wait_for_health(url, timeout=60):
                # Kill first so we can safely read the captured logs.
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                stdout_fh.close()
                stderr_fh.close()
                stdout_content = stdout_path.read_text(encoding="utf-8", errors="replace")
                stderr_content = stderr_path.read_text(encoding="utf-8", errors="replace")
                tail = lambda s: s[-4000:] if len(s) > 4000 else s
                pytest.fail(
                    f"Backend didn't start in time.\n"
                    f"--- stdout (tail) ---\n{tail(stdout_content)}\n"
                    f"--- stderr (tail) ---\n{tail(stderr_content)}\n"
                )
        except Exception:
            # Make sure file handles are closed and process is cleaned up
            # if something unexpected happens during wait_for_health.
            proc.kill()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
            stdout_fh.close()
            stderr_fh.close()
            raise

        yield url

        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        stdout_fh.close()
        stderr_fh.close()

    def test_health_endpoint(self, backend_process):
        """The /health endpoint returns 200 with version info."""
        url = backend_process
        r = httpx.get(f"{url}/health", timeout=5.0)
        assert r.status_code == 200
        data = r.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "ok"
        assert data["data"]["version"] == "0.1.0"

    def test_root_endpoint(self, backend_process):
        """The / endpoint returns app name."""
        url = backend_process
        r = httpx.get(f"{url}/", timeout=5.0)
        assert r.status_code == 200
        data = r.json()
        assert "ComicStudio" in data["data"]["name"]

    def test_openapi_endpoint(self, backend_process):
        """The /openapi.json endpoint returns the OpenAPI schema."""
        url = backend_process
        r = httpx.get(f"{url}/openapi.json", timeout=5.0)
        assert r.status_code == 200
        schema = r.json()
        assert "paths" in schema
        assert "/health" in schema["paths"]

    def test_sqlite_db_created(self, backend_process, tmp_path):
        """The SQLite database file is created in the data dir."""
        db_file = tmp_path / "comicstudio.db"
        assert db_file.exists()
        assert db_file.stat().st_size > 0

    def test_uploads_dir_created(self, backend_process, tmp_path):
        """The uploads directory is created in the data dir."""
        uploads_dir = tmp_path / "uploads"
        assert uploads_dir.exists()
        assert uploads_dir.is_dir()

    def test_jwt_secret_created(self, backend_process, tmp_path):
        """The JWT secret file is created."""
        secret_file = tmp_path / ".jwt_secret"
        assert secret_file.exists()
        secret = secret_file.read_text(encoding="utf-8")
        assert len(secret) >= 32

    def test_version_file_created(self, backend_process, tmp_path):
        """The version.txt file is created with version info."""
        version_file = tmp_path / "version.txt"
        assert version_file.exists()
        content = version_file.read_text(encoding="utf-8")
        assert "0.1.0" in content

    def test_logs_dir_created(self, backend_process, tmp_path):
        """The logs directory is created."""
        logs_dir = tmp_path / "logs"
        assert logs_dir.exists()

    def test_executable_size_reasonable(self):
        """The executable should be at least 10MB (sanity check)."""
        size = EXECUTABLE_PATH.stat().st_size
        assert size > 10 * 1024 * 1024, f"Executable is only {size} bytes"

    def test_executable_no_python_dependency(self):
        """The executable should not crash immediately if PYTHONHOME is unset.

        This is a sanity check that the bundle is self-contained.
        """
        port = find_free_port()
        env = os.environ.copy()
        env.pop("PYTHONHOME", None)
        env.pop("PYTHONPATH", None)
        env["CS_DESKTOP_MODE"] = "1"
        env["CS_DATA_DIR"] = str(Path(__file__).parent / "tmp_test_data")
        env["APP_PORT"] = str(port)

        # Use DEVNULL instead of PIPE so the backend cannot block on a full
        # pipe buffer while we are sleeping (the backend emits a lot of
        # SQLAlchemy log output at startup).
        try:
            proc = subprocess.Popen(
                [str(EXECUTABLE_PATH), "--port", str(port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
            )
            # Wait briefly to see if it crashes
            time.sleep(3)
            assert proc.poll() is None, "Process exited immediately"
            proc.terminate()
            proc.wait(timeout=10)
        finally:
            # Cleanup test data
            import shutil
            test_data = Path(__file__).parent / "tmp_test_data"
            if test_data.exists():
                shutil.rmtree(test_data, ignore_errors=True)
