#!/usr/bin/env python3
"""
Validate the portable Windows MSYS2 + Arm toolchain bundle.
"""

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RANDOMIZER_DIR = ROOT / "randomizer"

TOOLS_ROOT = RANDOMIZER_DIR / "tools" / "windows"
MSYS_ROOT = TOOLS_ROOT / "msys64"
MSYS_LAUNCHER = MSYS_ROOT / "msys2_shell.cmd"
TOOLCHAIN_ROOT = TOOLS_ROOT / "toolchain"
TOOLCHAIN_BIN = TOOLCHAIN_ROOT / "bin"

REQUIRED_MSYS_TOOLS = (
    "bash",
    "make",
    "sh",
    "sed",
    "awk",
    "grep",
    "cp",
    "rm",
    "mkdir",
    "find",
    "cat",
    "printf",

    # Host-side tool compiler/dependency stack.
    "cc",
    "gcc",
    "g++",
    "pkg-config",
    "git",
)

REQUIRED_ARM_TOOLS = (
    "arm-none-eabi-gcc.exe",
    "arm-none-eabi-cpp.exe",
    "arm-none-eabi-as.exe",
    "arm-none-eabi-ld.exe",
    "arm-none-eabi-objcopy.exe",
    "arm-none-eabi-objdump.exe",
    "arm-none-eabi-ar.exe",
)

REQUIRED_TOOLCHAIN_DIRS = (
    "bin",
    "include",
    "lib",
    "arm-none-eabi",
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
    env = os.environ.copy()

    for key in list(env):
        upper = key.upper()

        if (
            upper.startswith("DEVKIT")
            or upper.startswith("MSYS")
            or upper.startswith("MINGW")
            or upper == "CYGWIN"
        ):
            env.pop(
                key,
                None,
            )

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


def run_msys_capture(command):
    if not MSYS_LAUNCHER.exists():
        return (
            1,
            "msys2_shell.cmd missing",
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
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        **no_console_kwargs(),
    )

    return (
        result.returncode,
        (result.stdout or "").strip(),
    )


def version(path):
    try:
        result = subprocess.run(
            [
                str(path),
                "--version",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            **no_console_kwargs(),
        )

        lines = (
            result.stdout
            or ""
        ).strip().splitlines()

        return (
            lines[0]
            if lines
            else f"exit {result.returncode}"
        )

    except Exception as exc:
        return f"ERROR: {exc}"


def main():
    print("=" * 70)
    print(
        "WINDOWS PORTABLE BUILD ENVIRONMENT CHECK"
    )
    print("=" * 70)
    print()

    failures = 0

    print("MSYS2 isolation")
    print("---------------")

    if not MSYS_LAUNCHER.exists():
        print(
            f"[MISSING] {MSYS_LAUNCHER}"
        )
        failures += 1
    else:
        code, root_output = run_msys_capture(
            "cygpath -w /"
        )

        if code != 0:
            print(
                "[FAILED] Could not query bundled MSYS2 root"
            )
            print(root_output)
            failures += 1
        else:
            try:
                actual_root = Path(
                    root_output
                ).resolve()
                expected_root = (
                    MSYS_ROOT.resolve()
                )

                if actual_root != expected_root:
                    print(
                        "[FAILED] Bundled shell is using the wrong root"
                    )
                    print(
                        f"         expected: {expected_root}"
                    )
                    print(
                        f"         actual:   {actual_root}"
                    )
                    failures += 1
                else:
                    print(
                        f"[OK]      root -> {actual_root}"
                    )
            except Exception:
                print(
                    f"[FAILED] Unexpected root output: {root_output}"
                )
                failures += 1

    print()
    print("MSYS2 shell/tools")
    print("-----------------")

    for tool in REQUIRED_MSYS_TOOLS:
        code, output = run_msys_capture(
            f"command -v {tool} || true"
        )

        if (
            code != 0
            or not output
        ):
            print(
                f"[MISSING] {tool}"
            )
            failures += 1
        else:
            print(
                f"[OK]      {tool} -> {output}"
            )

    print()
    print("Host build headers")
    print("------------------")

    for header in (
        "/usr/include/png.h",
        "/usr/include/zlib.h",
    ):
        code, output = run_msys_capture(
            f"test -f '{header}' && echo OK || true"
        )

        if (
            code != 0
            or output.strip() != "OK"
        ):
            print(
                f"[MISSING] {header}"
            )
            failures += 1
        else:
            print(
                f"[OK]      {header}"
            )

    print()
    print("ARM toolchain")
    print("-------------")

    for directory in REQUIRED_TOOLCHAIN_DIRS:
        path = (
            TOOLCHAIN_ROOT
            / directory
        )

        if not path.exists():
            print(
                f"[MISSING] directory: {directory}"
            )
            failures += 1
        else:
            print(
                f"[OK]      directory: {directory}"
            )

    for tool in REQUIRED_ARM_TOOLS:
        path = (
            TOOLCHAIN_BIN
            / tool
        )

        if not path.exists():
            print(
                f"[MISSING] {tool}"
            )
            failures += 1
        else:
            print(
                f"[OK]      {tool} -> {path}"
            )

    print()
    print("Version probes")
    print("--------------")

    _, bash_version = run_msys_capture(
        "bash --version | head -1"
    )

    if bash_version:
        print(
            f"bash: {bash_version}"
        )

    _, make_version = run_msys_capture(
        "make --version | head -1"
    )

    if make_version:
        print(
            f"make: {make_version}"
        )

    gcc = (
        TOOLCHAIN_BIN
        / "arm-none-eabi-gcc.exe"
    )

    if gcc.exists():
        print(
            "arm-none-eabi-gcc: "
            + version(gcc)
        )

    print()
    print("=" * 70)

    if failures:
        print(
            f"FAILED: {failures} required check(s) failed."
        )
        return 1

    print(
        "PASS: portable Windows build environment is isolated and complete."
    )
    return 0


if __name__ == "__main__":
    sys.exit(
        main()
    )
