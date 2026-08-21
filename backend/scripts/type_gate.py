"""Commercial type-safety gate.

Critical identity, billing, rate-limit and Jarvis integration modules must be
fully clean. The legacy application-wide SQLAlchemy typing debt is measured
against an explicit baseline so it cannot silently grow while models are
migrated to SQLAlchemy 2 ``Mapped`` declarations.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CRITICAL_MODULES = (
    "app/core/config.py",
    "app/core/security.py",
    "app/core/rate_limit.py",
    "app/services/ynex_billing_service.py",
    "app/engines/llm/jarvis_gateway.py",
)
FULL_BASELINE_ERRORS = 194


def run_mypy(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "mypy", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def main() -> int:
    critical = run_mypy(
        [
            *CRITICAL_MODULES,
            "--ignore-missing-imports",
            "--follow-imports=skip",
        ]
    )
    if critical.returncode:
        sys.stderr.write(critical.stdout + critical.stderr)
        print("TYPE_GATE: critical commercial path failed", file=sys.stderr)
        return 1

    full = run_mypy(
        ["app", "--ignore-missing-imports", "--no-pretty", "--show-error-codes"]
    )
    output = full.stdout + full.stderr
    error_count = len(re.findall(r"(?m)^.+:\d+: error:", output))
    if full.returncode not in (0, 1):
        sys.stderr.write(output)
        print("TYPE_GATE: mypy execution failed", file=sys.stderr)
        return 2
    if error_count > FULL_BASELINE_ERRORS:
        sys.stderr.write(output)
        print(
            f"TYPE_GATE: debt increased from {FULL_BASELINE_ERRORS} to {error_count}",
            file=sys.stderr,
        )
        return 1

    print(
        "TYPE_GATE: critical path clean; "
        f"full-app debt={error_count}/{FULL_BASELINE_ERRORS} (must not increase)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
