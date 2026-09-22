#!/usr/bin/env python3
"""
Prepare the portable Windows build bundle used by the standalone randomizer.

Run this from native Windows during release development.

End users do NOT run this file. The finished release already contains the
prepared tools.
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RANDOMIZER_DIR = ROOT / "randomizer"

TOOLS_ROOT = RANDOMIZER_DIR / "tools" / "windows"
MSYS_ROOT = TOOLS_ROOT / "msys64"
MSYS_LAUNCHER = MSYS_ROOT / "msys2_shell.cmd"
TOOLCHAIN_ROOT = TOOLS_ROOT / "toolchain"

DOWNLOAD_DIR = RANDOMIZER_DIR / "downloads"

MSYS2_URL = (
    "https://repo.msys2.org/distrib/"
    "msys2-x86_64-latest.sfx.exe"
)

MSYS2_ARCHIVE = (
    DOWNLOAD_DIR
    / "msys2-x86_64-latest.sfx.exe"
)



LIBPNG_VERSION = "1.6.58"

LIBPNG_URL = (
    "https://download.sourceforge.net/libpng/"
    f"libpng-{LIBPNG_VERSION}.tar.xz"
)

LIBPNG_ARCHIVE = (
    DOWNLOAD_DIR
    / f"libpng-{LIBPNG_VERSION}.tar.xz"
)

MSYS_PACKAGES = (
    "bash",
    "make",
    "coreutils",
    "findutils",
    "grep",
    "sed",
    "gawk",
    "diffutils",
    "patch",
    "tar",
    "gzip",
    "which",
    "perl",
    "python",

    # Native host-side build tools used to compile pokeemerald's helper
    # executables such as gbagfx, mapjson, trainerproc, preproc, etc.
    "gcc",
    "pkgconf",
    "git",
    "zlib-devel",
)


def no_console_kwargs():
    if os.name != "nt":
        return {}

    return {
        "creationflags": getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
    }


def clean_windows_env():
    """
    Create a child environment that cannot inherit devkitPro / another MSYS2.

    MSYS2 documentation explicitly warns that mixing installations can break
    path and runtime behaviour.
    """

    env = os.environ.copy()

    for key in list(env):
        upper = key.upper()

        if (
            upper.startswith("DEVKIT")
            or upper.startswith("MSYS")
            or upper.startswith("MINGW")
            or upper == "CYGWIN"
        ):
            env.pop(key, None)

    # Keep only ordinary Windows paths. msys2_shell.cmd will construct the
    # correct POSIX PATH for its selected environment.
    system_root = env.get(
        "SystemRoot",
        r"C:\Windows",
    )

    env["PATH"] = os.pathsep.join(
        [
            str(Path(system_root) / "System32"),
            str(Path(system_root)),
        ]
    )

    env["CHERE_INVOKING"] = "1"

    return env


def run(command, cwd=None, env=None):
    """
    Run a native Windows command and stream all output.

    Streaming is important for release preparation because configure/make
    failures must remain visible.
    """
    print()
    print("$ " + " ".join(str(part) for part in command))

    process = subprocess.Popen(
        [str(part) for part in command],
        cwd=cwd,
        env=env,

        # CREATE_NO_WINDOW can otherwise leave MSYS/libtool with an invalid
        # file descriptor 0. Give every non-interactive child a real stdin
        # handle backed by Windows NUL.
        stdin=subprocess.DEVNULL,

        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        **no_console_kwargs(),
    )

    captured = []

    if process.stdout is not None:
        for line in process.stdout:
            captured.append(line)
            print(line, end="", flush=True)

    code = process.wait()

    if code != 0:
        raise RuntimeError(
            "Command failed with exit code "
            f"{code}\n\n"
            + "".join(captured[-80:])
        )

    return code

def run_msys(command):
    """
    Run a command through the bundled MSYS2 launcher and stream its output.
    """
    if not MSYS_LAUNCHER.exists():
        raise RuntimeError(
            "Bundled MSYS2 launcher is missing:\n"
            f"{MSYS_LAUNCHER}"
        )

    comspec = os.environ.get(
        "ComSpec",
        r"C:\Windows\System32\cmd.exe",
    )

    return run(
        [
            comspec,
            "/d",
            "/c",
            MSYS_LAUNCHER,
            "-defterm",
            "-no-start",
            "-msys",
            "-where",
            MSYS_ROOT,
            "-c",
            command,
        ],
        cwd=MSYS_ROOT,
        env=clean_windows_env(),
    )

def get_msys_output(command):
    if not MSYS_LAUNCHER.exists():
        raise RuntimeError(
            "Bundled MSYS2 launcher is missing:\n"
            f"{MSYS_LAUNCHER}"
        )

    comspec = os.environ.get(
        "ComSpec",
        r"C:\Windows\System32\cmd.exe",
    )

    result = subprocess.run(
        [
            comspec,
            "/d",
            "/c",
            str(MSYS_LAUNCHER),
            "-defterm",
            "-no-start",
            "-msys",
            "-where",
            str(MSYS_ROOT),
            "-c",
            command,
        ],
        cwd=MSYS_ROOT,
        env=clean_windows_env(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        **no_console_kwargs(),
    )

    if result.returncode != 0:
        raise RuntimeError(
            "MSYS2 command failed:\n"
            + (result.stdout or "")
        )

    return (result.stdout or "").strip()


def verify_msys_root():
    """
    Refuse to continue unless / belongs to our packaged MSYS2 tree.
    """

    actual = get_msys_output(
        "cygpath -w /"
    )

    actual_path = Path(
        actual.strip()
    ).resolve()

    expected = MSYS_ROOT.resolve()

    if actual_path != expected:
        raise RuntimeError(
            "Bundled MSYS2 started with the WRONG filesystem root.\n\n"
            f"Expected:\n  {expected}\n\n"
            f"Actual:\n  {actual_path}\n\n"
            "Close any devkitPro/MSYS2 shells and rerun the bootstrap."
        )

    print(
        f"Verified bundled MSYS2 root: {actual_path}"
    )


def download(url, destination):
    """
    Download with Windows curl.exe, falling back to PowerShell.

    SSL certificate checking stays enabled.
    """

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if (
        destination.exists()
        and destination.stat().st_size > 0
    ):
        print(
            f"Already downloaded: {destination.name}"
        )
        return

    print(
        f"Downloading:\n  {url}"
    )

    curl = (
        shutil.which("curl.exe")
        or shutil.which("curl")
    )

    if curl is not None:
        result = subprocess.run(
            [
                curl,
                "--fail",
                "--location",
                "--retry",
                "3",
                "--output",
                str(destination),
                url,
            ],
            **no_console_kwargs(),
        )

        if (
            result.returncode == 0
            and destination.exists()
            and destination.stat().st_size > 0
        ):
            return

        destination.unlink(
            missing_ok=True
        )

    powershell = (
        shutil.which("powershell.exe")
        or shutil.which("powershell")
    )

    if powershell is None:
        raise RuntimeError(
            "Neither curl.exe nor PowerShell was found."
        )

    command = (
        "$ProgressPreference='SilentlyContinue'; "
        "Invoke-WebRequest "
        f"-Uri '{url}' "
        f"-OutFile '{destination}' "
        "-UseBasicParsing"
    )

    result = subprocess.run(
        [
            powershell,
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            command,
        ],
        **no_console_kwargs(),
    )

    if (
        result.returncode != 0
        or not destination.exists()
        or destination.stat().st_size == 0
    ):
        destination.unlink(
            missing_ok=True
        )

        raise RuntimeError(
            f"Download failed:\n{url}"
        )


def remove_path(path):
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def install_msys2():
    if MSYS_LAUNCHER.exists():
        print(
            f"Portable MSYS2 already exists:\n  {MSYS_ROOT}"
        )
        return

    print()
    print(
        "Extracting portable MSYS2..."
    )

    TOOLS_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory() as temp:
        temp_path = Path(temp)

        run(
            [
                MSYS2_ARCHIVE,
                f"-o{temp_path}",
                "-y",
            ]
        )

        candidates = [
            temp_path,
            *[
                p
                for p in temp_path.iterdir()
                if p.is_dir()
            ],
        ]

        extracted = None

        for candidate in candidates:
            if (
                candidate
                / "msys2_shell.cmd"
            ).exists():
                extracted = candidate
                break

        if extracted is None:
            raise RuntimeError(
                "Could not locate the extracted MSYS2 root."
            )

        shutil.copytree(
            extracted,
            MSYS_ROOT,
        )


def install_msys_packages():
    verify_msys_root()

    package_list = " ".join(
        MSYS_PACKAGES
    )

    # First initialise/update the packaged environment itself.
    run_msys(
        "pacman -Sy --noconfirm"
    )

    run_msys(
        "pacman -S --needed --noconfirm "
        + package_list
    )

    verify_msys_root()

    required_commands = (
        "make",
        "cc",
        "gcc",
        "g++",
        "pkg-config",
        "git",
    )

    for command_name in required_commands:
        output = get_msys_output(
            f"command -v {command_name} || true"
        )

        if not output:
            raise RuntimeError(
                f"{command_name} was not installed into the packaged "
                "MSYS2 tree."
            )

        print(
            f"Bundled {command_name}: {output}"
        )

    # zlib comes from pacman and must exist before we build libpng.
    zlib_check = get_msys_output(
        "test -f /usr/include/zlib.h && echo OK || true"
    )

    if zlib_check != "OK":
        raise RuntimeError(
            "zlib development headers were not installed "
            "(/usr/include/zlib.h is missing)."
        )

    # Do NOT check png.h here. libpng is intentionally built from source
    # immediately after this function returns.


def install_libpng():
    """
    Build and install libpng into packaged MSYS2 /usr.

    Validate the archive first, then configure, compile, test, and install it.
    """
    existing = get_msys_output(
        "test -f /usr/include/png.h && echo OK || true"
    )

    if existing == "OK":
        print(
            "libpng is already installed in the packaged MSYS2 environment."
        )
        return

    native_archive = str(
        LIBPNG_ARCHIVE.resolve()
    ).replace("'", "'\\''")

    archive_msys = get_msys_output(
        f"cygpath -u '{native_archive}'"
    )

    print()
    print(
        f"Validating libpng archive:\n  {LIBPNG_ARCHIVE}"
    )

    run_msys(
        f"set -e; tar tf '{archive_msys}' >/dev/null"
    )

    build_command = (
        "set -e; "
        "tmpdir=$(mktemp -d); "
        "printf 'Build directory: %s\\n' \"$tmpdir\"; "
        "cd \"$tmpdir\"; "
        f"tar xf '{archive_msys}'; "
        f"cd 'libpng-{LIBPNG_VERSION}'; "
        "printf 'CC: '; command -v cc; "
        "printf 'MAKE: '; command -v make; "
        "printf 'ZLIB HEADER: '; test -f /usr/include/zlib.h && echo OK; "
        "./configure --prefix=/usr; "
        # `make check` builds the library as required and matches the official
        # pokeemerald MSYS2 installation sequence. Avoid a separate parallel
        # libtool build here.
        "make check; "
        "make install"
    )

    print()
    print(
        f"Building libpng {LIBPNG_VERSION} inside packaged MSYS2..."
    )

    run_msys(build_command)

    png_check = get_msys_output(
        "test -f /usr/include/png.h && echo OK || true"
    )

    if png_check != "OK":
        raise RuntimeError(
            "libpng build completed but /usr/include/png.h is missing."
        )

    print("libpng installed successfully.")

def find_installed_devkitarm():
    """Locate a native Windows devkitARM installation."""
    candidates = []

    configured = os.environ.get("DEVKITARM")
    if configured and ":" in configured:
        candidates.append(Path(configured))

    devkitpro = os.environ.get("DEVKITPRO")
    if devkitpro and ":" in devkitpro:
        candidates.append(Path(devkitpro) / "devkitARM")

    candidates.append(Path(r"C:\devkitPro\devkitARM"))

    for candidate in candidates:
        if (candidate / "bin" / "arm-none-eabi-gcc.exe").exists():
            return candidate

    return None


def install_arm_toolchain():
    """
    Copy the proven devkitARM toolchain into the portable bundle.

    Release developers need devkitARM installed once. End users receive this
    copied toolchain inside the release and do not need devkitPro.
    """
    bundled_gcc = (
        TOOLCHAIN_ROOT
        / "bin"
        / "arm-none-eabi-gcc.exe"
    )

    if bundled_gcc.exists():
        print(
            f"Bundled devkitARM already exists:\n  {TOOLCHAIN_ROOT}"
        )
        return

    source = find_installed_devkitarm()

    if source is None:
        raise RuntimeError(
            "A native Windows devkitARM installation was not found.\n\n"
            "Install devkitPro/devkitARM for release development, then "
            "rerun this bootstrap."
        )

    print()
    print("Copying devkitARM into portable bundle...")
    print(f"  from: {source}")
    print(f"  to:   {TOOLCHAIN_ROOT}")

    remove_path(TOOLCHAIN_ROOT)

    shutil.copytree(
        source,
        TOOLCHAIN_ROOT,
        symlinks=True,
    )

    if not bundled_gcc.exists():
        raise RuntimeError(
            "devkitARM copy completed but arm-none-eabi-gcc.exe is missing."
        )

    result = subprocess.run(
        [str(bundled_gcc), "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        **no_console_kwargs(),
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Copied devkitARM compiler does not run successfully.\n\n"
            + (result.stdout or "")
        )

    lines = (result.stdout or "").splitlines()

    if lines:
        print(f"Copied devkitARM: {lines[0]}")


def main():
    if os.name != "nt":
        raise RuntimeError(
            "Run this bootstrap from native Windows Python, not WSL."
        )

    print("=" * 70)
    print(
        "PREPARING PORTABLE WINDOWS BUILD TOOLS"
    )
    print("=" * 70)
    print()

    DOWNLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    download(
        MSYS2_URL,
        MSYS2_ARCHIVE,
    )

    download(
        LIBPNG_URL,
        LIBPNG_ARCHIVE,
    )

    install_msys2()

    # Validate isolation before touching packages.
    verify_msys_root()

    install_msys_packages()
    install_libpng()

    # Final host-library verification after the source-built libpng install.
    final_png_check = get_msys_output(
        "test -f /usr/include/png.h && echo OK || true"
    )

    if final_png_check != "OK":
        raise RuntimeError(
            "libpng installation did not produce /usr/include/png.h."
        )

    final_zlib_check = get_msys_output(
        "test -f /usr/include/zlib.h && echo OK || true"
    )

    if final_zlib_check != "OK":
        raise RuntimeError(
            "zlib development headers disappeared unexpectedly."
        )

    install_arm_toolchain()

    print()
    print("=" * 70)
    print(
        "WINDOWS TOOL BUNDLE PREPARED"
    )
    print("=" * 70)
    print()
    print(
        r"Next run: py randomizer\windows_toolchain_check.py"
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as exc:
        print()
        print("=" * 70)
        print(
            "WINDOWS TOOL BOOTSTRAP FAILED"
        )
        print("=" * 70)
        print()
        print(exc)
        sys.exit(1)
