#!/usr/bin/env python3

import random
import re
import sys
from pathlib import Path

from config import PROTECTED_SPECIES
from manual_customization_runtime import species_is_enabled


ROOT = Path(__file__).resolve().parent.parent
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"

STANDARD_TYPES = (
    "TYPE_NORMAL",
    "TYPE_FIRE",
    "TYPE_WATER",
    "TYPE_ELECTRIC",
    "TYPE_GRASS",
    "TYPE_ICE",
    "TYPE_FIGHTING",
    "TYPE_POISON",
    "TYPE_GROUND",
    "TYPE_FLYING",
    "TYPE_PSYCHIC",
    "TYPE_BUG",
    "TYPE_ROCK",
    "TYPE_GHOST",
    "TYPE_DRAGON",
    "TYPE_DARK",
    "TYPE_STEEL",
    "TYPE_FAIRY",
)

SKIP_SPECIES = {
    "SPECIES_NONE",
    "SPECIES_EGG",
}

SPECIES_HEADER_PATTERN = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

TYPE_PATTERN = re.compile(
    r"(?P<prefix>\.types\s*=\s*MON_TYPES\()"
    r"(?P<body>[^)]*)"
    r"(?P<suffix>\))",
    re.DOTALL,
)


seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

print(f"Pokémon type randomizer seed: {seed}")
print(
    "Type randomization runs before move-learnset and trainer type-theme "
    "randomization, so later systems use the randomized Pokémon types."
)


def choose_types(original_types):
    """
    Preserve whether the species is effectively mono- or dual-type.

    MON_TYPES(TYPE_FIRE, TYPE_FIRE) is treated as one effective type.
    A true two-type Pokémon receives two different randomized types.
    """
    effective_count = len(
        dict.fromkeys(original_types)
    )

    if effective_count <= 1:
        chosen = rng.choice(
            STANDARD_TYPES
        )
        return (chosen,)

    return tuple(
        rng.sample(
            STANDARD_TYPES,
            2,
        )
    )


changed_species = 0
mono_species = 0
dual_species = 0
protected_species = 0
inherited_species = 0

for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):
    text = filepath.read_text(
        encoding="utf-8"
    )

    headers = list(
        SPECIES_HEADER_PATTERN.finditer(
            text
        )
    )

    replacements = []

    for index, match in enumerate(headers):
        species = match.group(1)
        start = match.start()
        end = (
            headers[index + 1].start()
            if index + 1 < len(headers)
            else len(text)
        )

        block = text[start:end]

        if (
            species in PROTECTED_SPECIES
            or species in SKIP_SPECIES
            or not species_is_enabled(species)
        ):
            if species in PROTECTED_SPECIES:
                protected_species += 1
            continue

        type_match = TYPE_PATTERN.search(
            block
        )

        if type_match is None:
            # Forms that inherit their species data are intentionally left
            # without a new explicit field; they continue to inherit the
            # now-randomized base species type.
            inherited_species += 1
            continue

        original_types = [
            token.strip()
            for token in type_match.group("body").split(",")
            if token.strip().startswith("TYPE_")
            and token.strip() != "TYPE_NONE"
        ]

        if not original_types:
            continue

        chosen = choose_types(
            original_types
        )

        if len(chosen) == 1:
            mono_species += 1
            new_body = chosen[0]
        else:
            dual_species += 1
            new_body = (
                chosen[0]
                + ", "
                + chosen[1]
            )

        new_type_expression = (
            type_match.group("prefix")
            + new_body
            + type_match.group("suffix")
        )

        block_start = (
            start
            + type_match.start()
        )
        block_end = (
            start
            + type_match.end()
        )

        replacements.append(
            (
                block_start,
                block_end,
                new_type_expression,
            )
        )

        changed_species += 1

    for start, end, replacement in sorted(
        replacements,
        reverse=True,
    ):
        text = (
            text[:start]
            + replacement
            + text[end:]
        )

    if replacements:
        filepath.write_text(
            text,
            encoding="utf-8",
        )


# Hard post-write audit: every explicit randomized MON_TYPES field contains
# only standard types, and dual types are not duplicates.
standard_type_set = set(
    STANDARD_TYPES
)

for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):
    text = filepath.read_text(
        encoding="utf-8"
    )

    headers = list(
        SPECIES_HEADER_PATTERN.finditer(
            text
        )
    )

    for index, match in enumerate(headers):
        species = match.group(1)

        if (
            species in PROTECTED_SPECIES
            or species in SKIP_SPECIES
            or not species_is_enabled(species)
        ):
            continue

        start = match.start()
        end = (
            headers[index + 1].start()
            if index + 1 < len(headers)
            else len(text)
        )

        block = text[start:end]
        type_match = TYPE_PATTERN.search(
            block
        )

        if type_match is None:
            continue

        parsed = [
            token.strip()
            for token in type_match.group("body").split(",")
            if token.strip().startswith("TYPE_")
            and token.strip() != "TYPE_NONE"
        ]

        if not parsed:
            continue

        if any(
            type_name not in standard_type_set
            for type_name in parsed
        ):
            raise RuntimeError(
                "Pokémon type audit failed for "
                f"{species}: {parsed}"
            )

        if (
            len(parsed) >= 2
            and parsed[0] == parsed[1]
        ):
            raise RuntimeError(
                "Pokémon dual-type audit failed for "
                f"{species}: duplicate {parsed[0]}"
            )

print()
print(
    f"Randomized explicit Pokémon type entries: "
    f"{changed_species}"
)
print(
    f"  Monotype entries: {mono_species}"
)
print(
    f"  Dual-type entries: {dual_species}"
)
print(
    f"Protected species left unchanged: "
    f"{protected_species}"
)
print(
    f"Species/forms inheriting type data left implicit: "
    f"{inherited_species}"
)
print(
    "Pokémon type audit passed."
)
print(f"Seed: {seed}")
