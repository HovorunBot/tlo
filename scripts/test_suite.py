"""Python script to run pytest across all supported Python versions."""  # noqa: INP001

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

SUPPORTED_PYTHONS: Sequence[str] = ("3.10", "3.11", "3.12", "3.13", "3.14")


def _run_for_version(version: str, extra_args: Sequence[str]) -> int:
    cmd = [
        "uv",
        "run",
        "--python",
        version,
        "--group",
        "test",
        "pytest",
        *extra_args,
    ]
    result = subprocess.run(cmd, check=False)  # noqa: S603 - code is trusted
    return result.returncode


def main(argv: Sequence[str] | None = None) -> int:
    """Run pytest across all supported Python versions via `uv run`."""
    args = list(argv or sys.argv[1:])
    failures: list[tuple[str, int]] = []

    for version in SUPPORTED_PYTHONS:
        exit_code = _run_for_version(version, args)
        if exit_code != 0:
            failures.append((version, exit_code))

    if failures:
        ", ".join(f"{version} (exit {code})" for version, code in failures)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
