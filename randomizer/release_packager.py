#!/usr/bin/env python3
"""
Create the final Windows release directory.

Output:

dist/
└── PokemonEmeraldRandomizer/
    ├── Randomizer.exe
    ├── game/
    ├── internal/
    │   ├── baseline/
    │   └── tools/
    │       └── windows/
    ├── output/
    └── README.txt
"""

import os
import shutil
import stat
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RANDOMIZER_DIR = ROOT / "randomizer"

DIST_ROOT = ROOT / "dist"
RELEASE_ROOT = DIST_ROOT / "PokemonEmeraldRandomizer"

BASELINE = RANDOMIZER_DIR / "baseline"
WINDOWS_TOOLS = RANDOMIZER_DIR / "tools" / "windows"

EXE_CANDIDATES = (
    DIST_ROOT / "Randomizer.exe",
    DIST_ROOT / "Randomizer" / "Randomizer.exe",
)


# ============================================================
# ROBUST DELETE
# ============================================================

def _force_remove_error(func, path, exc_info):
    """
    shutil.rmtree callback for read-only MSYS2 files on Windows.
    """

    try:
        os.chmod(
            path,
            stat.S_IWRITE | stat.S_IREAD,
        )
        func(path)

    except Exception:
        # Last resort: try unlink/rmdir directly.
        try:
            p = Path(path)

            if p.is_dir() and not p.is_symlink():
                os.rmdir(path)
            else:
                os.unlink(path)

        except Exception:
            # Re-raise the original deletion failure with context.
            raise exc_info[1]


def remove_tree(path):
    path = Path(path)

    if not path.exists():
        return

    shutil.rmtree(
        path,
        onerror=_force_remove_error,
    )


# ============================================================
# COPY FILTER
# ============================================================

ROOT_IGNORE_DIRS = {
    ".git",
    ".github",
    "build",
    "dist",
    "output",
    "__pycache__",
}

ROOT_IGNORE_FILES = {
    "baserom.gba",
    "pokeemerald.gba",
    "pokeemerald.elf",
    "pokeemerald.map",
    "build_last.log",
}

IGNORE_SUFFIXES = {
    ".sav",
    ".pyc",
    ".pyo",
    ".bak",
}


def relative_directory(directory):
    try:
        return (
            Path(directory)
            .resolve()
            .relative_to(ROOT.resolve())
        )
    except ValueError:
        return Path()



DEVELOPMENT_ONLY_RANDOMIZER_FILES = {
    "bootstrap_windows_tools.py",
    "build_randomizer_exe.py",
    "cleanup_randomizer_files.py",
    "patch_tm_shop.py",
    "prepare_baseline.py",
    "release_packager.py",
    "windows_toolchain_check.py",
}


def ignore_game_files(directory, names):
    """
    Keep runtime randomizer Python files, but never copy heavyweight release
    preparation data into game/.

    In particular:
        randomizer/tools/
    is excluded wholesale. The Windows tool bundle is copied separately into
    internal/tools/windows/.
    """

    rel = relative_directory(
        directory
    )

    ignored = set()

    for name in names:
        candidate = Path(directory) / name

        if name in ROOT_IGNORE_DIRS:
            ignored.add(name)
            continue

        if name in ROOT_IGNORE_FILES:
            ignored.add(name)
            continue

        if (
            candidate.is_file()
            and candidate.suffix.lower()
            in IGNORE_SUFFIXES
        ):
            ignored.add(name)
            continue

        if rel == Path("randomizer"):
            if name in {
                "tools",
                "downloads",
                "logs",
                "baseline",
                "__pycache__",
            }:
                ignored.add(name)
                continue

            if name in DEVELOPMENT_ONLY_RANDOMIZER_FILES:
                ignored.add(name)
                continue

            if name.endswith(".pre_cleanup.bak"):
                ignored.add(name)
                continue

    return ignored


# ============================================================
# HELPERS
# ============================================================

def find_exe():
    for candidate in EXE_CANDIDATES:
        if candidate.exists():
            return candidate

    return None


def require(path, description):
    if not Path(path).exists():
        raise RuntimeError(
            f"Missing {description}:\n{path}"
        )


# ============================================================
# RELEASE
# ============================================================

def main():
    require(
        BASELINE,
        "packaged baseline",
    )

    require(
        WINDOWS_TOOLS,
        "portable Windows tool bundle",
    )

    exe = find_exe()

    if exe is None:
        raise RuntimeError(
            "Randomizer.exe was not found.\n\n"
            "Run:\n"
            "  py randomizer\\build_randomizer_exe.py\n"
            "first."
        )

    if RELEASE_ROOT.exists():
        print(
            "Removing previous release directory..."
        )

        remove_tree(
            RELEASE_ROOT
        )

    RELEASE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print()
    print("=" * 70)
    print(
        "CREATING WINDOWS RELEASE DIRECTORY"
    )
    print("=" * 70)
    print()

    # --------------------------------------------------------
    # EXE
    # --------------------------------------------------------

    print(
        "Copying Randomizer.exe..."
    )

    shutil.copy2(
        exe,
        RELEASE_ROOT / "Randomizer.exe",
    )

    # --------------------------------------------------------
    # GAME SOURCE
    # --------------------------------------------------------

    print(
        "Copying game source..."
    )

    shutil.copytree(
        ROOT,
        RELEASE_ROOT / "game",
        ignore=ignore_game_files,
        dirs_exist_ok=True,
    )

    # Standalone releases deliberately omit the development repository's
    # .git directory.  pokeemerald-expansion's build rules require this
    # marker when compiling from a source tree without Git history.
    (
        RELEASE_ROOT
        / "game"
        / ".histignore"
    ).touch(
        exist_ok=True,
    )

    # --------------------------------------------------------
    # INTERNAL DATA
    # --------------------------------------------------------

    internal = (
        RELEASE_ROOT / "internal"
    )

    print(
        "Copying packaged baseline..."
    )

    shutil.copytree(
        BASELINE,
        internal / "baseline",
        dirs_exist_ok=True,
    )

    print(
        "Copying portable Windows build tools..."
    )

    # Copy links as links where Windows permissions permit it. If the source
    # contains ordinary files, they are copied normally.
    shutil.copytree(
        WINDOWS_TOOLS,
        internal / "tools" / "windows",
        dirs_exist_ok=True,
        symlinks=True,
        ignore_dangling_symlinks=True,
    )

    # --------------------------------------------------------
    # USER OUTPUT
    # --------------------------------------------------------

    (
        RELEASE_ROOT
        / "output"
    ).mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        RELEASE_ROOT
        / "README.txt"
    ).write_text(
        "Pokemon Emerald Randomizer\n"
        "==========================\n\n"
        "1. Double-click Randomizer.exe.\n"
        "2. Choose your options and seed.\n"
        "3. Click Randomize.\n"
        "4. The finished ROM will be placed in output\\.\n\n"
        "No terminal is required.\n"
        "Python, WSL, Git, MSYS2 and devkitARM do not need to be installed.\n"
        "No base ROM is included with this package.\n",
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print(
        "RELEASE DIRECTORY READY"
    )
    print("=" * 70)
    print()
    print(
        RELEASE_ROOT
    )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(
            main()
        )

    except Exception as exc:
        print()
        print(
            "RELEASE PACKAGING FAILED"
        )
        print(
            exc
        )
        sys.exit(1)
