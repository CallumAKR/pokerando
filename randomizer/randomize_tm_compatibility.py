#!/usr/bin/env python3

import json
import random
import re
import sys
from collections import defaultdict, deque
from pathlib import Path
from config import PROTECTED_SPECIES

ROOT = Path(__file__).resolve().parent.parent

LEARNABLES_FILE = (
    ROOT
    / "src/data/pokemon/all_learnables.json"
)

TMS_FILE = (
    ROOT
    / "include/constants/tms_hms.h"
)

TUTOR_MOVES_FILE = (
    ROOT
    / "src/data/tutor_moves.h"
)

MOVES_FILE = (
    ROOT
    / "src/data/moves_info.h"
)

SPECIES_DIR = (
    ROOT
    / "src/data/pokemon/species_info"
)

STAB_WEIGHT = 2.0

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

print(
    f"TM/HM and move tutor compatibility randomizer seed: "
    f"{seed}"
)

print(
    f"STAB weight: {STAB_WEIGHT}x"
)

# ------------------------------------------------------------
# LOAD TM / HM AND MOVE TUTOR POOLS
# ------------------------------------------------------------

tm_text = TMS_FILE.read_text(
    encoding="utf-8"
)

tm_moves = sorted(set(
    f"MOVE_{name}"
    for name in re.findall(
        r"F\((\w+)\)",
        tm_text
    )
))

print(
    f"Found {len(tm_moves)} "
    f"TM/HM moves."
)

if not tm_moves:
    raise RuntimeError(
        "No TM/HM moves found."
    )

tm_set = set(tm_moves)

tutor_text = TUTOR_MOVES_FILE.read_text(
    encoding="utf-8"
)

tutor_moves = sorted(set(
    move
    for move in re.findall(
        r"\b(MOVE_[A-Z0-9_]+)\b",
        tutor_text,
    )
    if move != "MOVE_UNAVAILABLE"
))

print(
    f"Found {len(tutor_moves)} "
    f"move tutor moves."
)

if not tutor_moves:
    raise RuntimeError(
        "No move tutor moves found in src/data/tutor_moves.h."
    )

tutor_set = set(tutor_moves)

# Expansion stores TM/HM and tutor compatibility in the same teachable
# learnset. A move may exist in both pools after a custom TM catalogue is
# selected, so randomise the distinct union rather than counting it twice.
teachable_moves = sorted(
    tm_set | tutor_set
)
teachable_set = set(teachable_moves)

print(
    f"Found {len(teachable_moves)} distinct "
    f"TM/HM or move tutor moves."
)

# ------------------------------------------------------------
# LOAD MOVE TYPES
# ------------------------------------------------------------

moves_text = MOVES_FILE.read_text(
    encoding="utf-8"
)

move_header_pattern = re.compile(
    r"^\s*\[(MOVE_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE
)

move_headers = list(
    move_header_pattern.finditer(
        moves_text
    )
)

move_types = {}

for i, match in enumerate(move_headers):

    move = match.group(1)

    start = match.start()

    end = (
        move_headers[i + 1].start()
        if i + 1 < len(move_headers)
        else len(moves_text)
    )

    block = moves_text[start:end]

    type_match = re.search(
        r"\.type\s*=\s*"
        r"(TYPE_[A-Z0-9_]+)",
        block
    )

    if type_match:
        move_types[move] = (
            type_match.group(1)
        )

# ------------------------------------------------------------
# LOAD SPECIES INFO
# ------------------------------------------------------------

species_header_pattern = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$"
)

types_pattern = re.compile(
    r"\.types\s*=\s*MON_TYPES\(([^)]+)\)"
)

evolution_target_pattern = re.compile(
    r"\{\s*EVO_[A-Z0-9_]+\s*,"
    r".*?,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
    r"(?:\s*,|\s*\})"
)

species_types = defaultdict(set)

children = defaultdict(set)
parents = defaultdict(set)

species_blocks = {}

for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):

    lines = filepath.read_text(
        encoding="utf-8"
    ).splitlines(keepends=True)

    current_species = None
    block_lines = []

    def finish_block():

        if current_species is None:
            return

        block = "".join(block_lines)

        species_blocks[
            current_species
        ] = block

        type_match = (
            types_pattern.search(block)
        )

        if type_match:

            for value in (
                type_match
                .group(1)
                .split(",")
            ):

                value = value.strip()

                if value.startswith("TYPE_"):
                    species_types[
                        current_species
                    ].add(value)

        if ".evolutions" in block:

            for target in (
                evolution_target_pattern
                .findall(block)
            ):

                if target == current_species:
                    continue

                children[
                    current_species
                ].add(target)

                parents[
                    target
                ].add(current_species)

    for line in lines:

        species_match = (
            species_header_pattern
            .match(
                line.rstrip("\r\n")
            )
        )

        if species_match:

            finish_block()

            current_species = (
                species_match.group(1)
            )

            block_lines = [line]

            continue

        if current_species is not None:
            block_lines.append(line)

    finish_block()

print(
    f"Found {len(species_blocks)} "
    f"species entries."
)

# ------------------------------------------------------------
# LOAD ALL LEARNABLES
# ------------------------------------------------------------

with LEARNABLES_FILE.open(
    "r",
    encoding="utf-8"
) as fp:

    learnables = json.load(fp)

print(
    f"Found {len(learnables)} "
    f"learnable-move entries."
)

def constant_to_json_name(
    species_constant
):

    prefix = "SPECIES_"

    if species_constant.startswith(
        prefix
    ):
        return species_constant[
            len(prefix):
        ]

    return species_constant


def json_name_to_constant(
    json_name
):
    return f"SPECIES_{json_name}"

# ------------------------------------------------------------
# RECORD ORIGINAL DATA
# ------------------------------------------------------------

original_teachable_sets = {}
non_teachable_moves = {}

for json_species, move_list in (
    learnables.items()
):

    original_teachable_sets[
        json_species
    ] = {
        move
        for move in move_list
        if move in teachable_set
    }

    non_teachable_moves[
        json_species
    ] = [
        move
        for move in move_list
        if move not in teachable_set
    ]

# ------------------------------------------------------------
# RANDOM TEACHABLE-MOVE SELECTION
# ------------------------------------------------------------

def choose_one_teachable_move(
    species_constant,
    excluded
):

    candidates = [
        move
        for move in teachable_moves
        if move not in excluded
    ]

    if not candidates:
        return None

    types = species_types.get(
        species_constant,
        set()
    )

    weights = []

    for move in candidates:

        weight = 1.0

        if (
            move_types.get(move)
            in types
        ):
            weight *= STAB_WEIGHT

        weights.append(weight)

    return rng.choices(
        candidates,
        weights=weights,
        k=1
    )[0]


def fill_teachable_set(
    species_constant,
    starting_set,
    desired_count
):

    result = set(starting_set)

    desired_count = min(
        max(
            desired_count,
            len(result)
        ),
        len(teachable_moves)
    )

    while len(result) < desired_count:

        choice = choose_one_teachable_move(
            species_constant,
            result
        )

        if choice is None:
            break

        result.add(choice)

    return result

# ------------------------------------------------------------
# ORDER SPECIES BY EVOLUTION
# ------------------------------------------------------------

all_json_constants = {
    json_name_to_constant(name)
    for name in learnables
}

indegree = {}

for species in all_json_constants:

    valid_parents = {
        parent
        for parent in parents.get(
            species,
            set()
        )
        if parent in all_json_constants
    }

    indegree[species] = len(
        valid_parents
    )

queue = deque(sorted(
    species
    for species, degree
    in indegree.items()
    if degree == 0
))

ordered_species = []

while queue:

    species = queue.popleft()

    ordered_species.append(
        species
    )

    for child in sorted(
        children.get(
            species,
            set()
        )
    ):

        if child not in indegree:
            continue

        indegree[child] -= 1

        if indegree[child] == 0:
            queue.append(child)

remaining = sorted(
    all_json_constants
    - set(ordered_species)
)

ordered_species.extend(
    remaining
)

# ------------------------------------------------------------
# RANDOMIZE TM/HM AND MOVE TUTOR COMPATIBILITY
# ------------------------------------------------------------

assigned_teachable_sets = {}

protected_count = 0

for species_constant in (
    ordered_species
):

    json_species = (
        constant_to_json_name(
            species_constant
        )
    )

    if json_species not in learnables:
        continue

    # -----------------------------------
    # PROTECTED SPECIES
    # -----------------------------------

    if (
        species_constant
        in PROTECTED_SPECIES
    ):

        assigned_teachable_sets[
            species_constant
        ] = set(
            original_teachable_sets.get(
                json_species,
                set()
            )
        )

        protected_count += 1

        print(
            f"Protected teachable-move compatibility: "
            f"{species_constant}"
        )

        continue

    # -----------------------------------
    # NORMAL RANDOMIZATION
    # -----------------------------------

    original_count = len(
        original_teachable_sets.get(
            json_species,
            set()
        )
    )

    inherited = set()

    for parent in parents.get(
        species_constant,
        set()
    ):

        if parent in assigned_teachable_sets:

            inherited.update(
                assigned_teachable_sets[parent]
            )

    desired_count = max(
        original_count,
        len(inherited)
    )

    assigned_teachable_sets[
        species_constant
    ] = fill_teachable_set(
        species_constant,
        inherited,
        desired_count
    )

# ------------------------------------------------------------
# WRITE NEW JSON
# ------------------------------------------------------------

changed_species = 0
gained_due_to_inheritance = 0

for json_species in learnables:

    species_constant = (
        json_name_to_constant(
            json_species
        )
    )

    randomized_teachables = (
        assigned_teachable_sets.get(
            species_constant
        )
    )

    if randomized_teachables is None:

        randomized_teachables = (
            original_teachable_sets.get(
                json_species,
                set()
            )
        )

    original_count = len(
        original_teachable_sets.get(
            json_species,
            set()
        )
    )

    if (
        len(randomized_teachables)
        > original_count
    ):
        gained_due_to_inheritance += 1

    new_moves = sorted(set(
        non_teachable_moves[
            json_species
        ]
        + list(randomized_teachables)
    ))

    if (
        set(new_moves)
        != set(
            learnables[
                json_species
            ]
        )
    ):
        changed_species += 1

    learnables[
        json_species
    ] = new_moves

with LEARNABLES_FILE.open(
    "w",
    encoding="utf-8"
) as fp:

    json.dump(
        learnables,
        fp,
        indent=2,
        sort_keys=True
    )

    fp.write("\n")

print()
print(
    f"Protected {protected_count} "
    f"species."
)

print(
    f"Changed TM/HM and move tutor compatibility for "
    f"{changed_species} species."
)

print(
    f"{gained_due_to_inheritance} "
    f"species gained extra compatibility "
    f"to preserve evolution inheritance."
)


print(f"Seed: {seed}")
