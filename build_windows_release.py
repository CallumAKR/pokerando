#!/usr/bin/env python3
"""
Assemble a self-contained PokéRando Windows release.

This script intentionally does not download or invent a toolchain. Before
running it, prepare the portable build environment at:

    randomizer/tools/windows/
        msys64/
        toolchain/

Run randomizer/windows_toolchain_check.py first. Once that check passes this
script freezes the GUI with PyInstaller and assembles the release layout
expected by randomizer/runtime_paths.py.

The Windows tool bundle is copied into the release, but should remain outside
normal Git history.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RANDOMIZER = ROOT / "randomizer"
TOOLS = RANDOMIZER / "tools" / "windows"
BASELINE = RANDOMIZER / "baseline"
DIST_ROOT = ROOT / "dist"
WORK_ROOT = ROOT / "build" / "windows-release"
RELEASE_NAME = "PokemonEmeraldRandomizer"

# Build/output/cache material must not be copied into the packaged game tree.
SKIP_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "__pycache__",
    "build",
    "dist",
    "output",
}
SKIP_SUFFIXES = {".gba", ".elf", ".map", ".o", ".d", ".pyc"}
SKIP_NAMES = {
    "Randomizer.exe",
    "build_debug.txt",
}


def run(command: list[str], *, cwd: Path = ROOT) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def require_windows() -> None:
    if os.name != "nt":
        raise SystemExit(
            "Windows releases must be built on Windows so PyInstaller produces "
            "a native Windows executable."
        )


def check_tool_bundle() -> None:
    checker = RANDOMIZER / "windows_toolchain_check.py"
    run([sys.executable, str(checker)])


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "PyInstaller is required to build Randomizer.exe. Install it into "
            "the packaging Python environment with:\n\n"
            "    python -m pip install pyinstaller\n"
        ) from exc


def ignore_game_copy(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    path = Path(directory)

    for name in names:
        candidate = path / name

        if candidate.is_dir() and name in SKIP_DIRS:
            ignored.add(name)
            continue

        if name in SKIP_NAMES or candidate.suffix.lower() in SKIP_SUFFIXES:
            ignored.add(name)
            continue

        # The release keeps its build tools under internal/tools/windows.
        if candidate == TOOLS:
            ignored.add(name)

        # Baseline data is likewise copied to internal/baseline.
        if candidate == BASELINE:
            ignored.add(name)

    return ignored


def copy_game_tree(destination: Path) -> None:
    shutil.copytree(
        ROOT,
        destination,
        ignore=ignore_game_copy,
        dirs_exist_ok=False,
    )

    # A release intentionally has no Git history.
    (destination / ".histignore").touch()


def build_executable(exe_destination: Path) -> None:
    entry = RANDOMIZER / "gui.py"
    pyinstaller_dist = WORK_ROOT / "pyinstaller-dist"
    pyinstaller_work = WORK_ROOT / "pyinstaller-work"
    spec_dir = WORK_ROOT / "spec"

    run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onefile",
            "--windowed",
            "--name",
            "Randomizer",
            "--distpath",
            str(pyinstaller_dist),
            "--workpath",
            str(pyinstaller_work),
            "--specpath",
            str(spec_dir),
            str(entry),
        ]
    )

    built = pyinstaller_dist / "Randomizer.exe"
    if not built.exists():
        raise SystemExit(f"PyInstaller did not produce {built}")

    shutil.copy2(built, exe_destination)


def assemble(*, keep_existing: bool = False) -> Path:
    require_windows()
    ensure_pyinstaller()
    check_tool_bundle()

    release = DIST_ROOT / RELEASE_NAME

    if release.exists():
        if keep_existing:
            raise SystemExit(f"Release directory already exists: {release}")
        shutil.rmtree(release)

    if WORK_ROOT.exists():
        shutil.rmtree(WORK_ROOT)

    release.mkdir(parents=True)
    WORK_ROOT.mkdir(parents=True)

    print("Copying game source...")
    copy_game_tree(release / "game")

    print("Copying baseline...")
    if not BASELINE.exists():
        raise SystemExit(f"Missing baseline directory: {BASELINE}")
    shutil.copytree(BASELINE, release / "internal" / "baseline")

    print("Copying portable Windows build environment...")
    shutil.copytree(TOOLS, release / "internal" / "tools" / "windows")

    (release / "output").mkdir()

    print("Building Randomizer.exe...")
    build_executable(release / "Randomizer.exe")

    print()
    print("=" * 70)
    print("WINDOWS RELEASE READY")
    print("=" * 70)
    print(release)
    print()
    print(
        "Before publishing, test this folder on a clean Windows machine with "
        "no Python/devkitPro/MSYS2 on PATH."
    )

    return release


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the self-contained PokéRando Windows release."
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Refuse to replace an existing dist/PokemonEmeraldRandomizer.",
    )
    args = parser.parse_args()

    assemble(keep_existing=args.keep_existing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
