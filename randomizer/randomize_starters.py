#!/usr/bin/env python3

import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from config import (
    PROTECTED_SPECIES,
    STARTER_MODE,
    FIXED_STARTERS,
    ALLOW_SPECIAL_STARTERS,
    BASE_STAGE_STARTERS_ONLY,
)

ROOT = Path(__file__).resolve().parent.parent

SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
STARTER_FILE = ROOT / "src/starter_choose.c"

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

THREE_STAGE_BASE_ONLY = (
    "--three-stage-base"
    in sys.argv[2:]
)

print(f"Starter randomizer seed: {seed}")
print(f"Starter mode: {STARTER_MODE}")
print(
    "Three-stage base starters only: "
    + ("yes" if THREE_STAGE_BASE_ONLY else "no")
)

# ============================================================
# READ SPECIES DATA
# ============================================================

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

# ============================================================
# SPECIES FLAGS
# ============================================================

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


# ============================================================
# BUILD EVOLUTION RELATIONSHIPS
# ============================================================

evolution_target_pattern = re.compile(
    r"\{\s*EVO_[A-Z0-9_]+\s*,"
    r".*?,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
    r"(?:\s*,|\s*\})"
)

parents = defaultdict(set)
children = defaultdict(set)

for species, block in species_blocks.items():

    if ".evolutions" not in block:
        continue

    for target in evolution_target_pattern.findall(
        block
    ):

        if target not in species_blocks:
            continue

        if target == species:
            continue

        parents[target].add(species)
        children[species].add(target)


def is_permanent_species(species):
    block = species_blocks.get(species)

    if block is None:
        return False

    if species in {
        "SPECIES_NONE",
        "SPECIES_EGG",
    }:
        return False

    return not is_invalid_form(block)


def has_three_stage_evolution_path(species):
    """
    True when species is a base form and has at least one permanent
    base -> middle -> final evolution path.

    Branched lines qualify if at least one branch reaches a third stage.
    Regional forms are handled naturally because they have their own species
    constants and evolution relationships in Expansion.
    """
    if parents.get(species):
        return False

    for middle in children.get(species, ()):
        if not is_permanent_species(middle):
            continue

        for final in children.get(middle, ()):
            if (
                final != species
                and is_permanent_species(final)
            ):
                return True

    return False


# ============================================================
# BUILD RANDOM STARTER POOL
# ============================================================

starter_pool = []

for species, block in species_blocks.items():

    # Never use invalid internal constants.
    if species in {
        "SPECIES_NONE",
        "SPECIES_EGG",
    }:
        continue

    # Protected Pokémon do not randomly appear.
    #
    # They can still be explicitly selected through
    # FIXED_STARTERS.
    if species in PROTECTED_SPECIES:
        continue

    # Avoid temporary / battle-only forms.
    if is_invalid_form(block):
        continue

    # By default, don't randomly choose legendary-style species.
    if (
        not ALLOW_SPECIAL_STARTERS
        and is_special(block)
    ):
        continue

    # GUI option: starter must be the base form of a line with at least
    # one base -> middle -> final path.
    if (
        THREE_STAGE_BASE_ONLY
        and not has_three_stage_evolution_path(species)
    ):
        continue

    # Legacy config option: only require no pre-evolution.
    if (
        not THREE_STAGE_BASE_ONLY
        and BASE_STAGE_STARTERS_ONLY
        and parents.get(species)
    ):
        continue

    starter_pool.append(species)


starter_pool.sort()

print(
    f"Eligible random starter species: "
    f"{len(starter_pool)}"
)

if len(starter_pool) < 3:
    raise RuntimeError(
        "Not enough eligible starter species."
    )

if THREE_STAGE_BASE_ONLY:
    invalid_three_stage = [
        species
        for species in starter_pool
        if not has_three_stage_evolution_path(species)
    ]

    if invalid_three_stage:
        raise RuntimeError(
            "Three-stage starter pool audit failed: "
            + ", ".join(invalid_three_stage[:10])
        )

    print(
        "Three-stage starter pool audit passed."
    )

# ============================================================
# VALIDATE CONFIG
# ============================================================

VALID_MODES = {
    "one_fixed",
    "random",
    "fixed",
}

if STARTER_MODE not in VALID_MODES:
    raise RuntimeError(
        f"Unknown STARTER_MODE: {STARTER_MODE}"
    )


for slot in FIXED_STARTERS:

    if slot not in {0, 1, 2}:
        raise RuntimeError(
            f"Invalid starter slot in FIXED_STARTERS: "
            f"{slot}"
        )


for slot, species in FIXED_STARTERS.items():

    if species not in species_blocks:
        raise RuntimeError(
            f"Fixed starter does not exist: "
            f"{species}"
        )


if STARTER_MODE == "fixed":

    if set(FIXED_STARTERS.keys()) != {0, 1, 2}:
        raise RuntimeError(
            'STARTER_MODE = "fixed" requires '
            "slots 0, 1 and 2 in FIXED_STARTERS."
        )


# ============================================================
# CHOOSE STARTERS
# ============================================================

starters = [None, None, None]
used_species = set()


def use_fixed_starter(slot):

    species = FIXED_STARTERS[slot]

    if species in used_species:
        raise RuntimeError(
            f"Duplicate fixed starter: {species}"
        )

    starters[slot] = species
    used_species.add(species)


# ------------------------------------------------------------
# FIXED MODE
# ------------------------------------------------------------

if STARTER_MODE == "fixed":

    for slot in range(3):
        use_fixed_starter(slot)


# ------------------------------------------------------------
# ONE_FIXED MODE
# ------------------------------------------------------------

elif STARTER_MODE == "one_fixed":

    # Despite the name, this supports one or more fixed slots.
    # Any slot not specified will be randomized.

    for slot in sorted(FIXED_STARTERS):
        use_fixed_starter(slot)

    for slot in range(3):

        if starters[slot] is not None:
            continue

        candidates = [
            species
            for species in starter_pool
            if species not in used_species
        ]

        if not candidates:
            raise RuntimeError(
                "Ran out of unique starter candidates."
            )

        species = rng.choice(candidates)

        starters[slot] = species
        used_species.add(species)


# ------------------------------------------------------------
# FULL RANDOM MODE
# ------------------------------------------------------------

elif STARTER_MODE == "random":

    candidates = [
        species
        for species in starter_pool
        if species not in used_species
    ]

    chosen = rng.sample(
        candidates,
        3
    )

    starters = chosen
    used_species.update(chosen)


# ============================================================
# FINAL THREE-STAGE AUDIT
# ============================================================

if THREE_STAGE_BASE_ONLY:
    invalid_chosen = [
        species
        for species in starters
        if not has_three_stage_evolution_path(species)
    ]

    if invalid_chosen:
        raise RuntimeError(
            "Selected starter failed the three-stage base rule: "
            + ", ".join(invalid_chosen)
        )

# ============================================================
# PRINT RESULT
# ============================================================

print()

for slot, species in enumerate(starters):

    fixed = (
        STARTER_MODE != "random"
        and slot in FIXED_STARTERS
    )

    marker = (
        " [FIXED]"
        if fixed
        else ""
    )

    print(
        f"Starter {slot + 1}: "
        f"{species}{marker}"
    )


# ============================================================
# MODIFY starter_choose.c
# ============================================================

text = STARTER_FILE.read_text(
    encoding="utf-8"
)

# We preserve the FireRed/LeafGreen starter on the left side
# of each conditional and replace only the Emerald starter.

starter_patterns = [
    re.compile(
        r"(#define\s+GRASS_STARTER\s+"
        r"\(IS_FRLG\s*\?\s*"
        r"SPECIES_[A-Z0-9_]+\s*:\s*)"
        r"SPECIES_[A-Z0-9_]+"
        r"(\s*\))"
    ),

    re.compile(
        r"(#define\s+FIRE_STARTER\s+"
        r"\(IS_FRLG\s*\?\s*"
        r"SPECIES_[A-Z0-9_]+\s*:\s*)"
        r"SPECIES_[A-Z0-9_]+"
        r"(\s*\))"
    ),

    re.compile(
        r"(#define\s+WATER_STARTER\s+"
        r"\(IS_FRLG\s*\?\s*"
        r"SPECIES_[A-Z0-9_]+\s*:\s*)"
        r"SPECIES_[A-Z0-9_]+"
        r"(\s*\))"
    ),
]


new_text = text

for slot in range(3):

    pattern = starter_patterns[slot]
    species = starters[slot]

    new_text, count = pattern.subn(
        lambda match:
            match.group(1)
            + species
            + match.group(2),
        new_text,
        count=1
    )

    if count != 1:
        raise RuntimeError(
            f"Could not locate starter slot "
            f"{slot + 1} in starter_choose.c"
        )


STARTER_FILE.write_text(
    new_text,
    encoding="utf-8"
)


print()

print(
    f"Updated: "
    f"{STARTER_FILE}"
)


print(
    f"Seed: {seed}"
)
