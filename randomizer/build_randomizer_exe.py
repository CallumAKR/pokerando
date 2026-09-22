#!/usr/bin/env python3
"""Build the native Windows Randomizer.exe with an installed PyInstaller."""

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "Randomizer.spec"


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "PyInstaller is not installed. Install the release-development "
            "version before building Randomizer.exe."
        ) from exc

    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            str(SPEC),
        ],
        cwd=ROOT,
    )

    exe = ROOT / "dist" / "Randomizer.exe"

    if not exe.exists():
        raise RuntimeError(
            "PyInstaller completed but Randomizer.exe was not found:\n"
            f"{exe}"
        )

    print()
    print(f"Randomizer.exe ready:\n{exe}")


if __name__ == "__main__":
    main()
