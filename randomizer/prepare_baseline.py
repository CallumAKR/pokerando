#!/usr/bin/env python3

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RANDOMIZER_DIR = ROOT / "randomizer"

# Development-only clean checkout.
# This is used ONCE to create the packaged baseline.
CLEAN_ROOT = ROOT.parent / "pokeemerald-clean"

BASELINE_ROOT = RANDOMIZER_DIR / "baseline"

# Full files/directories that are safe for the randomizer to own/reset.
RESET_TARGETS = [
    Path("src/data/pokemon/species_info"),
    Path("src/data/pokemon/level_up_learnsets"),
    Path("src/data/pokemon/all_learnables.json"),
    Path("src/data/moves_info.h"),
    Path("src/data/trade.h"),
    Path("src/data/wild_encounters.json"),
    Path("src/data/heal_locations.json"),
    Path("src/wild_encounter.c"),
    Path("src/data/trainers.party"),
    Path("src/starter_choose.c"),
]

# We keep clean copies of maps/scripts only as REFERENCE DATA.
# The master never copies these directories wholesale back into the game.
# clean_map_restore.py restores only the specific species/item tokens owned
# by the static/egg/item randomizers.
REFERENCE_TARGETS = [
    Path("data/maps"),
    Path("data/scripts"),
]


def remove_path(path):
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def copy_path(source, destination):
    if source.is_dir():
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copytree(
            source,
            destination,
            dirs_exist_ok=True,
        )
    else:
        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )


def main():
    if not CLEAN_ROOT.exists():
        raise RuntimeError(
            "Clean pokeemerald-expansion checkout not found:\n"
            f"{CLEAN_ROOT}\n\n"
            "The baseline can only be prepared from the untouched "
            "clean checkout."
        )

    print("=" * 70)
    print("PREPARING PACKAGED RANDOMIZER BASELINE")
    print("=" * 70)
    print()
    print(f"Clean source: {CLEAN_ROOT}")
    print(f"Baseline:     {BASELINE_ROOT}")
    print()

    # Rebuild the baseline from scratch so stale files cannot survive.
    remove_path(BASELINE_ROOT)
    BASELINE_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Copying reset-owned data...")

    for relative_path in RESET_TARGETS:
        source = CLEAN_ROOT / relative_path
        destination = BASELINE_ROOT / relative_path

        if not source.exists():
            raise RuntimeError(
                "Missing clean baseline source:\n"
                f"{source}"
            )

        print(f"  {relative_path}")
        copy_path(
            source,
            destination,
        )

    print()
    print("Copying map/script reference data...")

    for relative_path in REFERENCE_TARGETS:
        source = CLEAN_ROOT / relative_path
        destination = BASELINE_ROOT / relative_path

        if not source.exists():
            raise RuntimeError(
                "Missing clean reference source:\n"
                f"{source}"
            )

        print(f"  {relative_path}")
        copy_path(
            source,
            destination,
        )

    manifest = BASELINE_ROOT / "README_BASELINE.txt"

    manifest.write_text(
        "This directory is the packaged clean baseline used by the randomizer.\n"
        "\n"
        "Files under src/ are safe reset-owned randomizable data.\n"
        "Files under data/maps and data/scripts are REFERENCE DATA ONLY.\n"
        "They must never be copied wholesale into the modified game source.\n"
        "clean_map_restore.py restores only specific randomized tokens from them.\n",
        encoding="utf-8",
    )

    print()
    print("=" * 70)
    print("BASELINE READY")
    print("=" * 70)
    print()
    print(
        "The randomizer can now use randomizer/baseline instead of "
        "~/pokeemerald-clean."
    )


if __name__ == "__main__":
    main()
