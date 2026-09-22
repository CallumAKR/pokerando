#!/usr/bin/env python3

import re
import sys
import random
from pathlib import Path
from collections import defaultdict
from config import PROTECTED_FAMILIES
from manual_customization_runtime import species_is_enabled

ROOT = Path(__file__).resolve().parent.parent

SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
ABILITIES_DATA = ROOT / "src/data/abilities.h"
ABILITIES_CONSTANTS = ROOT / "include/constants/abilities.h"

BANNED_ABILITIES = {
    "ABILITY_NONE",
    # These mechanics require a particular species, form, or battle partner.
    # Keeping them out of the random pool does not remove the abilities from
    # their original species or from manual customisation.
    "ABILITY_SCHOOLING",
    "ABILITY_FORECAST",
    "ABILITY_STANCE_CHANGE",
    "ABILITY_SHIELDS_DOWN",
    "ABILITY_ZEN_MODE",
    "ABILITY_BATTLE_BOND",
    "ABILITY_POWER_CONSTRUCT",
    "ABILITY_HUNGER_SWITCH",
    "ABILITY_ZERO_TO_HERO",
    "ABILITY_MULTITYPE",
    "ABILITY_RKS_SYSTEM",
    "ABILITY_DISGUISE",
    "ABILITY_ICE_FACE",
    "ABILITY_GULP_MISSILE",
    "ABILITY_COMMANDER",
    "ABILITY_TERA_SHIFT",
    "ABILITY_TERA_SHELL",
    "ABILITY_TERAFORM_ZERO",
}


seed = int(sys.argv[1]) if len(sys.argv) > 1 else random.randrange(2**32)
rng = random.Random(seed)

print(f"Ability randomizer seed: {seed}")

# ------------------------------------------------------------
# LOAD SPECIES BLOCKS
# ------------------------------------------------------------

species_header_pattern = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$"
)

species_blocks = {}

for filepath in sorted(SPECIES_DIR.rglob("*.h")):
    lines = filepath.read_text(encoding="utf-8").splitlines(keepends=True)

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

        while i < len(lines) and "{" not in lines[i]:
            i += 1

        if i >= len(lines):
            break

        depth = 0
        opened = False

        while i < len(lines):

            for ch in lines[i]:
                if ch == "{":
                    depth += 1
                    opened = True

                elif ch == "}":
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

print(f"Found {len(species_blocks)} species entries.")

if not species_blocks:
    raise RuntimeError("No species entries found.")

# ------------------------------------------------------------
# LOAD ABILITY POOL
# ------------------------------------------------------------

abilities = set()

if ABILITIES_DATA.exists():
    ability_data_text = ABILITIES_DATA.read_text(
        encoding="utf-8"
    )

    abilities.update(
        re.findall(
            r"\[(ABILITY_[A-Z0-9_]+)\]\s*=",
            ability_data_text
        )
    )

if not abilities:
    constants_text = ABILITIES_CONSTANTS.read_text(
        encoding="utf-8"
    )

    abilities.update(
        re.findall(
            r"\bABILITY_[A-Z0-9_]+\b",
            constants_text
        )
    )

abilities = sorted(
    ability
    for ability in abilities
    if ability not in BANNED_ABILITIES
)

print(f"Found {len(abilities)} usable abilities.")

if len(abilities) < 3:
    raise RuntimeError("Not enough abilities found.")

# ------------------------------------------------------------
# BUILD EVOLUTION GRAPH
# ------------------------------------------------------------

graph = defaultdict(set)

for species in species_blocks:
    graph[species]

evolution_target_pattern = re.compile(
    r"\{\s*EVO_[A-Z0-9_]+\s*,"
    r".*?,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
    r"(?:\s*,|\s*\})"
)

for species, block in species_blocks.items():

    if ".evolutions" not in block:
        continue

    for target in evolution_target_pattern.findall(block):

        if target not in species_blocks:
            continue

        if target == species:
            continue

        graph[species].add(target)
        graph[target].add(species)

# ------------------------------------------------------------
# FIND EVOLUTION FAMILIES
# ------------------------------------------------------------

families = []
visited = set()

for species in sorted(graph):

    if species in visited:
        continue

    stack = [species]
    family = []

    while stack:
        current = stack.pop()

        if current in visited:
            continue

        visited.add(current)
        family.append(current)

        for neighbour in graph[current]:
            if neighbour not in visited:
                stack.append(neighbour)

    families.append(sorted(family))

families.sort(key=lambda family: family[0])

print(f"Built {len(families)} evolution families.")

# ------------------------------------------------------------
# ASSIGN ABILITIES
# ------------------------------------------------------------

family_assignments = {}

for family in families:

    protected_by = None

    for protected_species in PROTECTED_FAMILIES:
        if protected_species in family:
            protected_by = protected_species
            break

    if protected_by is not None:

        chosen = tuple(PROTECTED_FAMILIES[protected_by])

        if len(chosen) != 3:
            raise RuntimeError(
                "Protected ability family must define exactly three "
                f"ability slots: {protected_by}"
            )

        print()
        print(
            f"PROTECTED FAMILY ({protected_by}): "
            f"{', '.join(family)}"
        )

        print(
            f"  -> {chosen[0]}, "
            f"{chosen[1]}, "
            f"{chosen[2]}"
        )

    else:
        chosen = tuple(
            rng.sample(abilities, 3)
        )

    for species in family:
        family_assignments[species] = chosen

# ------------------------------------------------------------
# REWRITE SPECIES ABILITY LINES
# ------------------------------------------------------------

ability_line_pattern = re.compile(
    r"^(\s*)\.abilities\s*=\s*\{[^}]+\},?\s*$"
)

changed_species = 0
changed_files = 0

for filepath in sorted(SPECIES_DIR.rglob("*.h")):

    lines = filepath.read_text(
        encoding="utf-8"
    ).splitlines(keepends=True)

    current_species = None
    changed_file = False

    for index, line in enumerate(lines):

        species_match = species_header_pattern.match(
            line.rstrip("\r\n")
        )

        if species_match:
            current_species = species_match.group(1)
            continue

        ability_match = ability_line_pattern.match(
            line.rstrip("\r\n")
        )

        if ability_match is None:
            continue

        if current_species is None:
            continue

        if current_species not in family_assignments:
            continue

        if not species_is_enabled(current_species):
            continue

        chosen = family_assignments[
            current_species
        ]

        indent = ability_match.group(1)

        lines[index] = (
            f"{indent}.abilities = {{ "
            f"{chosen[0]}, "
            f"{chosen[1]}, "
            f"{chosen[2]} "
            f"}},\n"
        )

        changed_species += 1
        changed_file = True

    if changed_file:

        filepath.write_text(
            "".join(lines),
            encoding="utf-8"
        )

        changed_files += 1

print()
print(
    f"Changed abilities for "
    f"{changed_species} species."
)

print(
    f"Changed {changed_files} source files."
)

print(f"Seed: {seed}")
