#!/usr/bin/env python3

import random
import re
import sys
from pathlib import Path
from clean_map_restore import restore_egg_gifts

from config import PROTECTED_SPECIES

ROOT = Path(__file__).resolve().parent.parent

SPECIES_DIR = ROOT / "src/data/pokemon/species_info"

SCRIPT_DIRS = [
    ROOT / "data/maps",
    ROOT / "data/scripts",
]

# If False, gift eggs only become normal Pokémon.
ALLOW_SPECIAL_EGGS = False

# Only used if ALLOW_SPECIAL_EGGS = True.
# 0.02 = 2%
SPECIAL_EGG_CHANCE = 0.02

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

print(f"Egg gift randomizer seed: {seed}")

restore_egg_gifts()
# ------------------------------------------------------------
# READ SPECIES DATA
# ------------------------------------------------------------

species_header_pattern = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$"
)

species_blocks = {}


def read_species_blocks(filepath):
    lines = filepath.read_text(
        encoding="utf-8"
    ).splitlines(keepends=True)

    i = 0

    while i < len(lines):

        match = species_header_pattern.match(
            lines[i].rstrip("\r\n")
        )

        if not match:
            i += 1
            continue

        species = match.group(1)
        start = i

        i += 1

        while (
            i < len(lines)
            and "{" not in lines[i]
        ):
            i += 1

        if i >= len(lines):
            break

        depth = 0
        opened = False

        while i < len(lines):

            for char in lines[i]:

                if char == "{":
                    depth += 1
                    opened = True

                elif char == "}":
                    depth -= 1

            if opened and depth == 0:
                end = i
                break

            i += 1

        else:
            break

        species_blocks[species] = "".join(
            lines[start:end + 1]
        )

        i = end + 1


for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):
    read_species_blocks(filepath)

print(
    f"Found {len(species_blocks)} "
    f"species entries."
)

if len(species_blocks) < 500:
    raise RuntimeError(
        "Species parser found suspiciously few species."
    )

# ------------------------------------------------------------
# CLASSIFY SPECIES
# ------------------------------------------------------------

SPECIAL_FLAGS = {
    "isRestrictedLegendary",
    "isSubLegendary",
    "isMythical",
    "isUltraBeast",
    "isParadox",
}

INVALID_FORM_FLAGS = {
    "isMegaEvolution",
    "isPrimalReversion",
    "isUltraBurst",
    "isGigantamax",
    "isTeraForm",
    "isTotem",
}


def has_flag(block, flag):
    return (
        re.search(
            rf"\.{re.escape(flag)}\s*=\s*TRUE",
            block
        )
        is not None
    )


def is_special(block):
    return any(
        has_flag(block, flag)
        for flag in SPECIAL_FLAGS
    )


def is_invalid_form(block):
    return any(
        has_flag(block, flag)
        for flag in INVALID_FORM_FLAGS
    )


normal_pool = []
special_pool = []

for species, block in species_blocks.items():

    if species in {
        "SPECIES_NONE",
        "SPECIES_EGG",
    }:
        continue

    if species in PROTECTED_SPECIES:
        continue

    if is_invalid_form(block):
        continue

    if is_special(block):
        special_pool.append(species)
    else:
        normal_pool.append(species)

normal_pool.sort()
special_pool.sort()

print()
print(
    f"Normal egg pool: "
    f"{len(normal_pool)}"
)

print(
    f"Special egg pool "
    f"(Legendary/Mythical/Paradox/UB): "
    f"{len(special_pool)}"
)

if not normal_pool:
    raise RuntimeError(
        "Normal egg pool is empty."
    )

# ------------------------------------------------------------
# FIND GIFT EGG COMMANDS
# ------------------------------------------------------------

giveegg_pattern = re.compile(
    r"\bgiveegg\s+(SPECIES_[A-Z0-9_]+)"
)

script_files = []

for directory in SCRIPT_DIRS:

    if not directory.exists():
        continue

    script_files.extend(
        directory.rglob("*.inc")
    )

changed_eggs = 0
changed_files = 0

spoiler_entries = []

# ------------------------------------------------------------
# RANDOMIZE GIFT EGGS
# ------------------------------------------------------------

for filepath in sorted(
    set(script_files)
):

    text = filepath.read_text(
        encoding="utf-8"
    )

    if not giveegg_pattern.search(text):
        continue

    def replace_egg(match):
        global changed_eggs

        original_species = match.group(1)

        candidates = normal_pool
        category = "normal"

        if (
            ALLOW_SPECIAL_EGGS
            and special_pool
            and rng.random() < SPECIAL_EGG_CHANCE
        ):
            candidates = special_pool
            category = "special"

        alternatives = [
            species
            for species in candidates
            if species != original_species
        ]

        if alternatives:
            candidates = alternatives

        replacement = rng.choice(
            candidates
        )

        changed_eggs += 1

        spoiler_entries.append(
            {
                "file": str(
                    filepath.relative_to(ROOT)
                ),
                "original": original_species,
                "replacement": replacement,
                "category": category,
            }
        )

        print(
            f"{filepath.relative_to(ROOT)}: "
            f"{original_species} "
            f"-> {replacement}"
        )

        return (
            f"giveegg {replacement}"
        )

    new_text = giveegg_pattern.sub(
        replace_egg,
        text
    )

    if new_text != text:

        filepath.write_text(
            new_text,
            encoding="utf-8"
        )

        changed_files += 1

# ------------------------------------------------------------
# SUMMARY
# ------------------------------------------------------------

print()
print(
    f"Randomized {changed_eggs} "
    f"gift eggs."
)

print(
    f"Changed {changed_files} "
    f"script files."
)


print(
    f"Seed: {seed}"
)
