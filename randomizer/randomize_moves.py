#!/usr/bin/env python3

import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from config import PROTECTED_SPECIES
from manual_customization_runtime import species_is_enabled


ROOT = Path(__file__).resolve().parent.parent

SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
LEARNSET_FILE = ROOT / "src/data/pokemon/level_up_learnsets/gen_9.h"
MOVES_FILE = ROOT / "src/data/moves_info.h"
LEARNABLES_FILE = ROOT / "src/data/pokemon/all_learnables.json"


SAME_TYPE_WEIGHT = 2.0

USE_SPECIES_SPECIFIC_POOLS = (
    "--species-specific-pools"
    in sys.argv[2:]
)

USE_SAME_TYPE_BIAS = (
    "--same-type-bias"
    in sys.argv[2:]
)

BANNED_MOVES = {
    "MOVE_NONE",
    "MOVE_STRUGGLE",
    "MOVE_PIKA_PAPOW",
    "MOVE_VEEVEE_VOLLEY",
    "MOVE_BOUNCY_BUBBLE",
    "MOVE_BUZZY_BUZZ",
    "MOVE_SIZZLY_SLIDE",
    "MOVE_GLITZY_GLOW",
    "MOVE_BADDY_BAD",
    "MOVE_SAPPY_SEED",
    "MOVE_FREEZY_FROST",
    "MOVE_SPARKLY_SWIRL",
    "MOVE_SKETCH",
}

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

print(f"Move randomizer seed: {seed}")
print(
    "Species-specific move pools: "
    + ("yes" if USE_SPECIES_SPECIFIC_POOLS else "no")
)
print(
    "Same-type move bias: "
    + (
        f"yes ({SAME_TYPE_WEIGHT}x)"
        if USE_SAME_TYPE_BIAS
        else "no"
    )
)


move_text = MOVES_FILE.read_text(
    encoding="utf-8"
)

move_header_pattern = re.compile(
    r"^\s*\[(MOVE_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

move_matches = list(
    move_header_pattern.finditer(
        move_text
    )
)

moves = {}

for index, match in enumerate(move_matches):
    move = match.group(1)
    block_start = match.start()

    if index + 1 < len(move_matches):
        block_end = move_matches[
            index + 1
        ].start()
    else:
        block_end = len(move_text)

    block = move_text[
        block_start:block_end
    ]

    type_match = re.search(
        r"\.type\s*=\s*(TYPE_[A-Z0-9_]+)",
        block,
    )

    category_match = re.search(
        r"\.category\s*=\s*(DAMAGE_CATEGORY_[A-Z0-9_]+)",
        block,
    )

    power_match = re.search(
        r"\.power\s*=\s*([0-9]+)",
        block,
    )

    if type_match is None:
        continue

    if move in BANNED_MOVES:
        continue

    moves[move] = {
        "type": type_match.group(1),
        "category": (
            category_match.group(1)
            if category_match
            else None
        ),
        "power": (
            int(power_match.group(1))
            if power_match
            else 0
        ),
    }

print(
    f"Found {len(moves)} usable moves."
)

if len(moves) < 50:
    raise RuntimeError(
        "Move parser found suspiciously few moves. Stopping."
    )


species_header_pattern = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$"
)

types_pattern = re.compile(
    r"\.types\s*=\s*MON_TYPES\(([^)]+)\)"
)

learnset_pointer_pattern = re.compile(
    r"\.levelUpLearnset\s*=\s*([A-Za-z0-9_]+)"
)

learnset_types = defaultdict(set)
learnset_species = defaultdict(set)
protected_learnsets = set()

for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):
    lines = filepath.read_text(
        encoding="utf-8"
    ).splitlines()

    current_species = None
    current_types = set()
    current_learnset = None

    def finish_species():
        if (
            current_species is None
            or current_learnset is None
        ):
            return

        if (
            current_species in PROTECTED_SPECIES
            or not species_is_enabled(current_species)
        ):
            protected_learnsets.add(
                current_learnset
            )
            return

        learnset_species[
            current_learnset
        ].add(
            current_species
        )

        for mon_type in current_types:
            learnset_types[
                current_learnset
            ].add(
                mon_type
            )

    for line in lines:
        species_match = (
            species_header_pattern.match(
                line
            )
        )

        if species_match:
            finish_species()

            current_species = (
                species_match.group(1)
            )
            current_types = set()
            current_learnset = None
            continue

        if current_species is None:
            continue

        type_match = types_pattern.search(
            line
        )

        if type_match:
            for value in (
                type_match
                .group(1)
                .split(",")
            ):
                value = value.strip()

                if value.startswith("TYPE_"):
                    current_types.add(
                        value
                    )

        learnset_match = (
            learnset_pointer_pattern.search(
                line
            )
        )

        if learnset_match:
            current_learnset = (
                learnset_match.group(1)
            )

    finish_species()

print(
    f"Found species mappings for "
    f"{len(learnset_species)} learnsets."
)

print(
    f"Found {len(protected_learnsets)} protected learnsets."
)


species_learnables = {}

if USE_SPECIES_SPECIFIC_POOLS:
    with LEARNABLES_FILE.open(
        "r",
        encoding="utf-8",
    ) as fp:
        species_learnables = json.load(
            fp
        )

    print(
        f"Read {len(species_learnables)} "
        "species-specific learnable-move pools."
    )


def constant_to_json_name(
    species_constant,
):
    prefix = "SPECIES_"

    if species_constant.startswith(
        prefix
    ):
        return species_constant[
            len(prefix):
        ]

    return species_constant


learnset_move_pools = {}
shared_learnset_count = 0
empty_species_pool_count = 0

if USE_SPECIES_SPECIFIC_POOLS:
    for symbol, species_set in (
        learnset_species.items()
    ):
        pool = set()

        if len(species_set) > 1:
            shared_learnset_count += 1

        for species in species_set:
            json_name = constant_to_json_name(
                species
            )

            for move in species_learnables.get(
                json_name,
                []
            ):
                if move in moves:
                    pool.add(
                        move
                    )

        if not pool:
            empty_species_pool_count += 1

        learnset_move_pools[
            symbol
        ] = sorted(
            pool
        )

    print(
        f"Shared learnset tables using union pools: "
        f"{shared_learnset_count}"
    )
    print(
        f"Species learnset tables with no usable pool: "
        f"{empty_species_pool_count}"
    )


all_moves = sorted(
    moves
)


def choose_move(
    symbol,
    types,
    already_chosen,
):
    if USE_SPECIES_SPECIFIC_POOLS:
        base_pool = learnset_move_pools.get(
            symbol,
            []
        )
    else:
        base_pool = all_moves

    candidates = [
        move
        for move in base_pool
        if move not in already_chosen
    ]

    if not candidates:
        candidates = list(
            base_pool
        )

    if not candidates:
        return None

    if not USE_SAME_TYPE_BIAS:
        return rng.choice(
            candidates
        )

    weights = []

    for move in candidates:
        move_type = moves[
            move
        ]["type"]

        weight = 1.0

        if move_type in types:
            weight *= SAME_TYPE_WEIGHT

        weights.append(
            weight
        )

    return rng.choices(
        candidates,
        weights=weights,
        k=1,
    )[0]


learnset_text = LEARNSET_FILE.read_text(
    encoding="utf-8"
)

learnset_pattern = re.compile(
    r"(static const struct LevelUpMove\s+"
    r"([A-Za-z0-9_]+)\[\]\s*=\s*\{\n)"
    r"(.*?)"
    r"(^\};)",
    re.MULTILINE | re.DOTALL,
)

move_entry_pattern = re.compile(
    r"LEVEL_UP_MOVE\(\s*([0-9]+)\s*,\s*"
    r"(MOVE_[A-Z0-9_]+)\s*\)"
)

changed_learnsets = 0
changed_moves = 0
preserved_empty_pool_learnsets = 0


def replace_learnset(match):
    global changed_learnsets
    global changed_moves
    global preserved_empty_pool_learnsets

    header = match.group(1)
    symbol = match.group(2)
    body = match.group(3)
    footer = match.group(4)

    if symbol in protected_learnsets:
        return match.group(0)

    if symbol not in learnset_species:
        return match.group(0)

    if (
        USE_SPECIES_SPECIFIC_POOLS
        and not learnset_move_pools.get(
            symbol
        )
    ):
        preserved_empty_pool_learnsets += 1
        print(
            "No usable species-specific move pool for "
            f"{symbol}; preserving that learnset."
        )
        return match.group(0)

    types = learnset_types.get(
        symbol,
        set(),
    )

    chosen_moves = set()

    def replace_move_entry(
        move_match
    ):
        nonlocal chosen_moves
        global changed_moves

        level = move_match.group(1)

        new_move = choose_move(
            symbol,
            types,
            chosen_moves,
        )

        if new_move is None:
            return move_match.group(0)

        chosen_moves.add(
            new_move
        )
        changed_moves += 1

        return (
            f"LEVEL_UP_MOVE({int(level):2d}, "
            f"{new_move})"
        )

    new_body = move_entry_pattern.sub(
        replace_move_entry,
        body,
    )

    changed_learnsets += 1

    return (
        header
        + new_body
        + footer
    )


new_learnset_text = learnset_pattern.sub(
    replace_learnset,
    learnset_text,
)

LEARNSET_FILE.write_text(
    new_learnset_text,
    encoding="utf-8",
)

print()
print(
    f"Randomized {changed_learnsets} learnsets."
)
print(
    f"Replaced {changed_moves} level-up moves."
)

if USE_SPECIES_SPECIFIC_POOLS:
    print(
        "Species-specific pool audit: randomized moves were selected only "
        "from the actual species' learnable-move pool."
    )
    print(
        "Evolution-chain independence: move pools remain attached to the "
        "species itself, not to randomized evolution targets."
    )
    print(
        f"Learnsets preserved because their species pool was empty: "
        f"{preserved_empty_pool_learnsets}"
    )

print(f"Seed: {seed}")
