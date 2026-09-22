#!/usr/bin/env python3
"""
Shared runtime paths for development and frozen Randomizer.exe builds.

Development layout:
    pokeemerald-expansion/
        randomizer/
            runtime_paths.py
            baseline/
            tools/windows/
        output/

Release layout:
    PokemonEmeraldRandomizer/
        Randomizer.exe
        game/
            randomizer/
                runtime_paths.py
                ...
        internal/
            baseline/
            tools/windows/
        output/
"""

import sys
from pathlib import Path


FROZEN = bool(
    getattr(
        sys,
        "frozen",
        False,
    )
)

if FROZEN:
    APP_ROOT = (
        Path(sys.executable)
        .resolve()
        .parent
    )

    ROOT = (
        APP_ROOT
        / "game"
    )

    INTERNAL_ROOT = (
        APP_ROOT
        / "internal"
    )

    BASELINE_ROOT = (
        INTERNAL_ROOT
        / "baseline"
    )

    WINDOWS_TOOLS_ROOT = (
        INTERNAL_ROOT
        / "tools"
        / "windows"
    )

else:
    APP_ROOT = (
        Path(__file__)
        .resolve()
        .parent
        .parent
    )

    ROOT = APP_ROOT

    INTERNAL_ROOT = None

    BASELINE_ROOT = (
        ROOT
        / "randomizer"
        / "baseline"
    )

    WINDOWS_TOOLS_ROOT = (
        ROOT
        / "randomizer"
        / "tools"
        / "windows"
    )


RANDOMIZER_DIR = (
    ROOT
    / "randomizer"
)

OUTPUT_DIR = (
    APP_ROOT
    / "output"
)
