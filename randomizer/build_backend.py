#!/usr/bin/env python3
"""
ROM build backend.

Development:
    - Linux/WSL can use host make.
    - Native Windows uses the packaged Windows tools when present.

Frozen Randomizer.exe:
    - MUST use the bundled tools under:
          <release>\\internal\\tools\\windows
    - Never silently falls back to system/devkitPro tools.
"""

import os
import json
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from runtime_paths import (
    FROZEN,
    ROOT,
    WINDOWS_TOOLS_ROOT,
)
from source_integrity import (
    ensure_heal_locations_json_valid,
)
from heal_location_make_rules import ensure_heal_locations_snapshot_rules


MSYS_ROOT = (
    WINDOWS_TOOLS_ROOT
    / "msys64"
)

MSYS_LAUNCHER = (
    MSYS_ROOT
    / "msys2_shell.cmd"
)

TOOLCHAIN_ROOT = (
    WINDOWS_TOOLS_ROOT
    / "toolchain"
)


class BuildEnvironmentError(RuntimeError):
    pass


def ensure_history_check_marker():
    """
    Allow a packaged source tree to build without a bundled .git directory.

    Development checkouts retain their normal history validation.  A copied
    or frozen release has no Git metadata by design, so pokeemerald-expansion
    expects an empty .histignore marker in the game root.
    """

    git_metadata = (
        ROOT
        / ".git"
    )

    marker = (
        ROOT
        / ".histignore"
    )

    if (
        git_metadata.exists()
        or marker.exists()
    ):
        return

    try:
        marker.touch(
            exist_ok=True,
        )
    except OSError as exc:
        raise BuildEnvironmentError(
            "The packaged game source has no Git history, and the required "
            "build marker could not be created:\n\n"
            f"{marker}\n\n"
            f"{exc}"
        ) from exc

    print(
        "Created standalone source-history marker: "
        f"{marker}"
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
    Prevent an installed devkitPro/MSYS2/Cygwin environment from leaking into
    our portable build environment.
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


def stream_process(
    command,
    cwd,
    env=None,
):
    print(
        "$ "
        + " ".join(
            str(part)
            for part in command
        ),
        flush=True,
    )

    process = subprocess.Popen(
        [
            str(part)
            for part in command
        ],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        **no_console_kwargs(),
    )

    if process.stdout is not None:
        for line in process.stdout:
            print(
                line,
                end="",
                flush=True,
            )

    return process.wait()


def capture_process(
    command,
    cwd,
    env=None,
):
    result = subprocess.run(
        [
            str(part)
            for part in command
        ],
        cwd=cwd,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        **no_console_kwargs(),
    )

    return (
        result.returncode,
        (result.stdout or "").strip(),
    )


def to_msys_path(path):
    path = Path(path).resolve()

    drive = path.drive

    if not drive:
        return path.as_posix()

    return (
        f"/{drive[0].lower()}"
        + path.as_posix()[2:]
    )


def msys_command(
    command,
    where,
):
    comspec = os.environ.get(
        "ComSpec",
        r"C:\Windows\System32\cmd.exe",
    )

    return [
        comspec,
        "/d",
        "/c",
        str(MSYS_LAUNCHER),
        "-defterm",
        "-no-start",
        "-msys",
        "-where",
        str(where),
        "-c",
        command,
    ]


def bundled_windows_environment_available():
    return (
        os.name == "nt"
        and MSYS_LAUNCHER.exists()
        and (
            TOOLCHAIN_ROOT
            / "bin"
            / "arm-none-eabi-gcc.exe"
        ).exists()
    )


def describe_build_backend():
    if bundled_windows_environment_available():
        return "bundled-windows"

    return "host"


def verify_bundled_environment():
    """
    Verify the exact release paths before building.

    This catches packaging/path mistakes before Make starts.
    """

    print(
        f"Game root: {ROOT}"
    )

    print(
        f"Windows tools root: {WINDOWS_TOOLS_ROOT}"
    )

    print(
        f"MSYS2 launcher: {MSYS_LAUNCHER}"
    )

    print(
        f"devkitARM root: {TOOLCHAIN_ROOT}"
    )

    if not MSYS_LAUNCHER.exists():
        raise BuildEnvironmentError(
            "Bundled MSYS2 launcher is missing:\n\n"
            f"{MSYS_LAUNCHER}"
        )

    gcc = (
        TOOLCHAIN_ROOT
        / "bin"
        / "arm-none-eabi-gcc.exe"
    )

    if not gcc.exists():
        raise BuildEnvironmentError(
            "Bundled devkitARM compiler is missing:\n\n"
            f"{gcc}"
        )

    code, output = capture_process(
        msys_command(
            "cygpath -w /",
            MSYS_ROOT,
        ),
        cwd=MSYS_ROOT,
        env=clean_windows_env(),
    )

    if code != 0:
        raise BuildEnvironmentError(
            "Could not start bundled MSYS2.\n\n"
            + output
        )

    lines = [
        line.strip()
        for line in output.splitlines()
        if line.strip()
    ]

    if not lines:
        raise BuildEnvironmentError(
            "Bundled MSYS2 returned no filesystem root."
        )

    actual_root = os.path.normcase(
        os.path.normpath(
            str(
                Path(
                    lines[-1]
                ).resolve()
            )
        )
    )

    expected_root = os.path.normcase(
        os.path.normpath(
            str(
                MSYS_ROOT.resolve()
            )
        )
    )

    if actual_root != expected_root:
        raise BuildEnvironmentError(
            "Bundled MSYS2 is using the wrong filesystem root.\n\n"
            f"Expected:\n{MSYS_ROOT.resolve()}\n\n"
            f"Actual:\n{lines[-1]}"
        )

    checks = (
        ("make", "command -v make"),
        ("cc", "command -v cc"),
        ("g++", "command -v g++"),
        ("pkg-config", "command -v pkg-config"),
        ("git", "command -v git"),
        (
            "libpng",
            "pkg-config --exists libpng && pkg-config --cflags libpng",
        ),
    )

    for name, command in checks:
        code, output = capture_process(
            msys_command(
                command,
                MSYS_ROOT,
            ),
            cwd=MSYS_ROOT,
            env=clean_windows_env(),
        )

        if (
            code != 0
            or not output.strip()
        ):
            raise BuildEnvironmentError(
                f"Bundled dependency check failed: {name}\n\n"
                f"Command:\n{command}\n\n"
                f"Output:\n{output}"
            )

        print(
            f"Bundled {name}: "
            f"{output.splitlines()[-1]}"
        )


def build_with_host(clean=False):
    """
    Development-only fallback.

    A frozen EXE is forbidden from reaching this function.
    """

    if FROZEN:
        raise BuildEnvironmentError(
            "Frozen Randomizer.exe attempted to use the host build backend.\n\n"
            "This is a packaging error. The release must contain "
            "internal\\tools\\windows."
        )

    make = (
        shutil.which("make")
        or shutil.which(
            "mingw32-make"
        )
    )

    if make is None:
        raise BuildEnvironmentError(
            "GNU Make was not found in the host environment."
        )

    print()
    print(
        "Build backend: host"
    )

    print(
        f"Host make: {make}"
    )

    if clean:
        print("Forcing clean rebuild...")
        code = stream_process([make, "clean"], cwd=ROOT)
        if code != 0:
            raise BuildEnvironmentError("make clean failed.")
    else:
        print("Incremental build: preserving generated tools/assets.")

    jobs = (
        os.cpu_count()
        or 1
    )

    code = stream_process(
        [
            make,
            f"-j{jobs}",
        ],
        cwd=ROOT,
    )

    if code != 0:
        raise BuildEnvironmentError(
            "ROM build failed."
        )


def build_with_bundled_windows(clean=False):
    print()
    print(
        "Build backend: bundled Windows"
    )

    verify_bundled_environment()

    # Make regenerates both headers in a recursive 'generated' step. Its
    # prerequisites must refer to this run's stable JSON snapshot too.
    ensure_heal_locations_snapshot_rules(ROOT / "json_data_rules.mk")

    project = to_msys_path(
        ROOT
    )

    toolchain = to_msys_path(
        TOOLCHAIN_ROOT
    )

    jobs = (
        os.cpu_count()
        or 1
    )

    build_step = (
        "make clean; "
        if clean
        else "printf 'Incremental build: preserving generated tools/assets.\\n'; "
    )

    # A release may be run from a cloud-synchronised directory such as
    # OneDrive.  jsonproc has previously observed heal_locations.json halfway
    # through a sync update even though Python validated it immediately before
    # Make started.  Give jsonproc an immutable snapshot in the system temp
    # directory, then create both generated headers before parallel Make can
    # race the synchronisation client.
    heal_locations_file = ROOT / "src/data/heal_locations.json"
    heal_locations_text = heal_locations_file.read_text(
        encoding="utf-8",
        errors="strict",
    )
    json.loads(heal_locations_text)

    snapshot_fd, snapshot_name = tempfile.mkstemp(
        prefix="pokemon-emerald-heal-locations-",
        suffix=".json",
    )

    try:
        with os.fdopen(snapshot_fd, "w", encoding="utf-8", newline="\n") as snapshot:
            snapshot.write(heal_locations_text)
            snapshot.flush()
            os.fsync(snapshot.fileno())

        snapshot_path = Path(snapshot_name)
        snapshot_msys = shlex.quote(to_msys_path(snapshot_path))

        generate_heal_headers = (
            "printf 'Generating heal-location headers from stable snapshot.\\n'; "
            "tools/jsonproc/jsonproc.exe "
            f"{snapshot_msys} "
            "src/data/heal_locations.json.txt "
            "src/data/heal_locations.h; "
            "tools/jsonproc/jsonproc.exe "
            f"{snapshot_msys} "
            "src/data/heal_locations.constants.json.txt "
            "include/constants/heal_locations.h; "
        )

        shell_command = (
            "set -e; "
            f"export PATH='{toolchain}/bin':\"$PATH\"; "
            f"cd '{project}'; "
            "printf 'ARM compiler: '; command -v arm-none-eabi-gcc; "
            "printf 'Host C compiler: '; command -v cc; "
            "printf 'Host C++ compiler: '; command -v g++; "
            "printf 'Make: '; command -v make; "
            "printf 'libpng flags: '; pkg-config --cflags libpng; "
            + build_step
            + generate_heal_headers
            + f"make -j{jobs} TOOLCHAIN='{toolchain}' "
            + f"HEAL_LOCATIONS_JSON={snapshot_msys}"
        )

        code = stream_process(
            msys_command(
                shell_command,
                ROOT,
            ),
            cwd=ROOT,
            env=clean_windows_env(),
        )
    finally:
        try:
            Path(snapshot_name).unlink()
        except FileNotFoundError:
            pass

    if code != 0:
        raise BuildEnvironmentError(
            "Bundled Windows ROM build failed."
        )


def build_rom(clean=False):
    # The release package intentionally excludes .git.  Repair older or
    # manually copied packages that do not yet contain .histignore.
    ensure_history_check_marker()

    # Catch/repair the narrowly observed heal_locations.json corruption before
    # starting a long parallel ROM build.
    ensure_heal_locations_json_valid()

    print()
    print("=" * 70)
    print(
        "BUILDING ROM"
    )
    print("=" * 70)
    print()

    print(
        f"Frozen application: {FROZEN}"
    )

    if FROZEN:
        # A released EXE is never allowed to fall back to installed host tools.
        if not bundled_windows_environment_available():
            raise BuildEnvironmentError(
                "The packaged Windows build environment is missing.\n\n"
                f"Expected MSYS2 launcher:\n{MSYS_LAUNCHER}\n\n"
                f"Expected toolchain:\n{TOOLCHAIN_ROOT}"
            )

        build_with_bundled_windows(clean=clean)

    elif bundled_windows_environment_available():
        # Native Windows development can test the exact release backend.
        build_with_bundled_windows(clean=clean)

    else:
        # Linux/WSL development fallback.
        build_with_host(clean=clean)

    rom_path = (
        ROOT
        / "pokeemerald.gba"
    )

    if not rom_path.exists():
        raise BuildEnvironmentError(
            "Build completed but pokeemerald.gba was not produced."
        )

    print()
    print(
        f"ROM ready: {rom_path}"
    )

    return rom_path


if __name__ == "__main__":
    print(
        "Selected backend:",
        describe_build_backend(),
    )

    build_rom()
