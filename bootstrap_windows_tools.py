#!/usr/bin/env python3
"""
Create randomizer/tools/windows from a normal devkitPro Windows installation.

This reconstructs the portable bundle expected by build_backend.py. It stages a
private copy of devkitPro's MSYS2 tree, installs the host build dependencies
inside that staged copy, builds the libpng version used by the legacy
pokeemerald MSYS2 instructions into /usr, and copies devkitARM as the isolated
ARM toolchain.

Nothing is committed to Git; the resulting directory is an input to
build_windows_release.py.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEST = ROOT / "randomizer" / "tools" / "windows"
LIBPNG_VERSION = "1.6.37"
LIBPNG_SHA256 = "505e70834d35383537b6491e7ae8641f1a4bed1876dbfe361201fc80868d88ca"
LIBPNG_URL = (
    "https://downloads.sourceforge.net/project/libpng/"
    f"libpng16/{LIBPNG_VERSION}/libpng-{LIBPNG_VERSION}.tar.xz"
)


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("$ " + " ".join(str(x) for x in command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def download(url: str, destination: Path, sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)

    if not destination.exists():
        print(f"Downloading {url}")
        urllib.request.urlretrieve(url, destination)

    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    if digest.lower() != sha256.lower():
        destination.unlink(missing_ok=True)
        raise SystemExit(
            f"Checksum mismatch for {destination.name}\n"
            f"expected: {sha256}\nactual:   {digest}"
        )


def msys_command(msys_root: Path, command: str) -> list[str]:
    launcher = msys_root / "msys2_shell.cmd"
    comspec = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
    return [
        comspec,
        "/d",
        "/c",
        str(launcher),
        "-defterm",
        "-no-start",
        "-msys",
        "-where",
        str(msys_root),
        "-c",
        command,
    ]


def main() -> int:
    if os.name != "nt":
        raise SystemExit("This bootstrapper must be run on Windows.")

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--devkitpro",
        type=Path,
        default=Path(r"C:\devkitPro"),
        help=r"Installed devkitPro root (default: C:\devkitPro)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing randomizer/tools/windows directory.",
    )
    args = parser.parse_args()

    source = args.devkitpro.resolve()
    source_msys = source / "msys2"
    source_arm = source / "devkitARM"

    required = [
        source_msys / "msys2_shell.cmd",
        source_arm / "bin" / "arm-none-eabi-gcc.exe",
    ]
    missing = [path for path in required if not path.exists()]
    if missing:
        raise SystemExit(
            "devkitPro installation is incomplete:\n"
            + "\n".join(str(path) for path in missing)
        )

    if DEST.exists():
        if not args.force:
            raise SystemExit(
                f"{DEST} already exists. Use --force to rebuild it."
            )
        shutil.rmtree(DEST)

    DEST.mkdir(parents=True)
    staged_msys = DEST / "msys64"
    staged_arm = DEST / "toolchain"

    print("Copying devkitPro MSYS2 into isolated bundle...")
    shutil.copytree(source_msys, staged_msys)

    print("Copying devkitARM into isolated bundle...")
    shutil.copytree(source_arm, staged_arm)

    # Install into the staged MSYS root, not C:\devkitPro.
    print("Installing host build packages into staged MSYS2...")
    run(
        msys_command(
            staged_msys,
            "pacman -Sy --noconfirm msys2-keyring && "
            "pacman -S --needed --noconfirm make gcc zlib-devel git pkgconf",
        ),
        cwd=staged_msys,
    )

    cache = ROOT / "build" / "windows-toolchain-downloads"
    archive = cache / f"libpng-{LIBPNG_VERSION}.tar.xz"
    download(LIBPNG_URL, archive, LIBPNG_SHA256)

    # Put the verified source archive inside the staged filesystem so all build
    # paths are local to the portable MSYS root.
    src_archive = staged_msys / "tmp" / archive.name
    src_archive.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive, src_archive)

    print("Building libpng into staged MSYS2 /usr...")
    shell = (
        "set -e; "
        "cd /tmp; "
        f"rm -rf libpng-{LIBPNG_VERSION}; "
        f"tar xf {archive.name}; "
        f"cd libpng-{LIBPNG_VERSION}; "
        "./configure --prefix=/usr; "
        "make -j2; "
        "make install; "
        f"cd /tmp; rm -rf libpng-{LIBPNG_VERSION} {archive.name}; "
        "pkg-config --exists libpng; "
        "test -f /usr/include/png.h; "
        "test -f /usr/include/zlib.h"
    )
    run(msys_command(staged_msys, shell), cwd=staged_msys)

    print("Validating completed portable bundle...")
    run([sys.executable, str(ROOT / "randomizer" / "windows_toolchain_check.py")])

    print()
    print("Portable Windows tool bundle is ready:")
    print(DEST)
    print()
    print("Next:")
    print(r"  python .\build_windows_release.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
