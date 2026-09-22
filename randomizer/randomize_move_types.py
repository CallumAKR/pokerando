#!/usr/bin/env python3

import random
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MOVES_FILE = ROOT / "src/data/moves_info.h"

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

PROTECTED_MOVES = {
    "MOVE_NONE",
    "MOVE_STRUGGLE",
}

MOVE_HEADER_PATTERN = re.compile(
    r"^\s*\[(MOVE_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

TYPE_PATTERN = re.compile(
    r"(?P<prefix>\.type\s*=\s*)"
    r"(?P<type>TYPE_[A-Z0-9_]+)"
)


seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

print(f"Move type randomizer seed: {seed}")
print(
    "Move types are randomized before Pokémon level-up moves, so optional "
    "same-type/STAB bias uses these randomized move types."
)


text = MOVES_FILE.read_text(
    encoding="utf-8"
)

headers = list(
    MOVE_HEADER_PATTERN.finditer(
        text
    )
)

if not headers:
    raise RuntimeError(
        "No move entries found in src/data/moves_info.h."
    )

replacements = []
changed_moves = 0
missing_direct_type = 0

for index, match in enumerate(headers):
    move = match.group(1)
    start = match.start()
    end = (
        headers[index + 1].start()
        if index + 1 < len(headers)
        else len(text)
    )

    if move in PROTECTED_MOVES:
        continue

    block = text[start:end]

    type_match = TYPE_PATTERN.search(
        block
    )

    if type_match is None:
        # Some special entries may inherit or compute type elsewhere.
        # Do not invent a field for them.
        missing_direct_type += 1
        continue

    original_type = type_match.group(
        "type"
    )

    candidates = [
        type_name
        for type_name in STANDARD_TYPES
        if type_name != original_type
    ]

    if not candidates:
        candidates = list(
            STANDARD_TYPES
        )

    new_type = rng.choice(
        candidates
    )

    replacement = (
        type_match.group("prefix")
        + new_type
    )

    replacements.append(
        (
            start + type_match.start(),
            start + type_match.end(),
            replacement,
        )
    )

    changed_moves += 1


for start, end, replacement in sorted(
    replacements,
    reverse=True,
):
    text = (
        text[:start]
        + replacement
        + text[end:]
    )

MOVES_FILE.write_text(
    text,
    encoding="utf-8",
)


# Hard audit the fields this script owns.
standard_type_set = set(
    STANDARD_TYPES
)

updated = MOVES_FILE.read_text(
    encoding="utf-8"
)

updated_headers = list(
    MOVE_HEADER_PATTERN.finditer(
        updated
    )
)

for index, match in enumerate(
    updated_headers
):
    move = match.group(1)

    if move in PROTECTED_MOVES:
        continue

    start = match.start()
    end = (
        updated_headers[index + 1].start()
        if index + 1 < len(updated_headers)
        else len(updated)
    )

    block = updated[start:end]
    type_match = TYPE_PATTERN.search(
        block
    )

    if type_match is None:
        continue

    if (
        type_match.group("type")
        not in standard_type_set
    ):
        raise RuntimeError(
            "Move type audit failed for "
            f"{move}: {type_match.group('type')}"
        )

print()
print(
    f"Randomized move types: "
    f"{changed_moves}"
)
print(
    f"Move entries without a direct .type field preserved: "
    f"{missing_direct_type}"
)
print(
    "MOVE_NONE and MOVE_STRUGGLE were preserved."
)
print(
    "Move type audit passed."
)
print(f"Seed: {seed}")
