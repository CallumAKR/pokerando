#!/usr/bin/env python3
"""Publish the finished randomized ROM into the user-facing output directory."""

import shutil
from pathlib import Path

from runtime_paths import OUTPUT_DIR


def safe_seed(seed):
    """Make a seed safe to use as part of a Windows filename."""
    return str(seed).replace("/", "_").replace("\\", "_")


def publish_rom(source_rom, seed):
    """Copy the built ROM to output/ using a seed-specific filename."""
    source_rom = Path(source_rom)

    if not source_rom.exists():
        raise RuntimeError(
            f"Cannot publish missing ROM:\n{source_rom}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    destination = (
        OUTPUT_DIR
        / f"Pokemon Emerald Randomized - {safe_seed(seed)}.gba"
    )

    shutil.copy2(
        source_rom,
        destination,
    )

    return destination
