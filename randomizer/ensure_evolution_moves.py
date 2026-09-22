#!/usr/bin/env python3
"""Keep move-dependent evolutions possible after learnset randomization.

The evolution data remains the source of truth.  For every species whose
evolution condition names a move (or a move type), this component adds the
needed move to that species' level-up learnset at level 0.  In Expansion,
level-0 moves are available through the move relearner but are not placed in a
new Pokemon's default moveset.

This component deliberately runs after move-type and level-up-move
randomization.  As a result, IF_KNOWS_MOVE_TYPE conditions use the move types
that will actually be present in the generated ROM.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from manual_customization_runtime import species_is_enabled


ROOT = Path(__file__).resolve().parent.parent

SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
LEARNSET_FILE = ROOT / "src/data/pokemon/level_up_learnsets/gen_9.h"
MOVES_FILE = ROOT / "src/data/moves_info.h"
LEARNABLES_FILE = ROOT / "src/data/pokemon/all_learnables.json"


SPECIES_HEADER_PATTERN = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

LEARNSET_POINTER_PATTERN = re.compile(
    r"\.levelUpLearnset\s*=\s*([A-Za-z0-9_]+)"
)

REQUIRED_MOVE_PATTERNS = (
    (
        "knows move",
        re.compile(
            r"\{\s*IF_KNOWS_MOVE\s*,\s*(MOVE_[A-Z0-9_]+)\s*\}"
        ),
    ),
    (
        "uses move",
        re.compile(
            r"\{\s*IF_USED_MOVE_X_TIMES\s*,\s*"
            r"(MOVE_[A-Z0-9_]+)\s*,\s*[0-9]+\s*\}"
        ),
    ),
)

REQUIRED_MOVE_TYPE_PATTERN = re.compile(
    r"\{\s*IF_KNOWS_MOVE_TYPE\s*,\s*(TYPE_[A-Z0-9_]+)\s*\}"
)

RECOIL_CONDITION_PATTERN = re.compile(
    r"\{\s*IF_RECOIL_DAMAGE_GE\s*,\s*[0-9]+\s*\}"
)

MOVE_HEADER_PATTERN = re.compile(
    r"^\s*\[(MOVE_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

MOVE_TYPE_PATTERN = re.compile(
    r"\.type\s*=\s*(TYPE_[A-Z0-9_]+)"
)

LEARNSET_PATTERN = re.compile(
    r"(static const struct LevelUpMove\s+"
    r"([A-Za-z0-9_]+)\[\]\s*=\s*\{\r?\n)"
    r"(.*?)"
    r"(^\};)",
    re.MULTILINE | re.DOTALL,
)

MOVE_ENTRY_LINE_PATTERN = re.compile(
    r"^[ \t]*LEVEL_UP_MOVE\(\s*[0-9]+\s*,\s*"
    r"(MOVE_[A-Z0-9_]+)\s*\),?[ \t]*(?:\r?\n|$)",
    re.MULTILINE,
)

LEVEL_ZERO_ENTRY_PATTERN_TEMPLATE = (
    r"LEVEL_UP_MOVE\(\s*0\s*,\s*{move}\s*\)"
)


# Basculin's condition records accumulated recoil rather than naming a move.
# Take Down is the explicit project rule requested for White-Striped Basculin.
SPECIES_MOVE_EXCEPTIONS = {
    "SPECIES_BASCULIN_WHITE_STRIPED": (
        "MOVE_TAKE_DOWN",
        "recoil evolution",
    ),
}


# Prefer recognisable, ordinary moves when a condition accepts any move of a
# particular type.  If move-type randomization changes all of these, the code
# falls back to another currently valid, generally learnable move of that type.
TYPE_MOVE_PREFERENCES = {
    "TYPE_FAIRY": (
        "MOVE_FAIRY_WIND",
        "MOVE_DISARMING_VOICE",
        "MOVE_BABY_DOLL_EYES",
        "MOVE_DRAINING_KISS",
        "MOVE_DAZZLING_GLEAM",
        "MOVE_PLAY_ROUGH",
        "MOVE_MOONBLAST",
    ),
}


class EvolutionMoveError(RuntimeError):
    pass


def _read_species_blocks(species_dir):
    for filepath in sorted(species_dir.rglob("*.h")):
        text = filepath.read_text(encoding="utf-8")
        headers = list(SPECIES_HEADER_PATTERN.finditer(text))

        for index, header in enumerate(headers):
            block_end = (
                headers[index + 1].start()
                if index + 1 < len(headers)
                else len(text)
            )
            yield (
                header.group(1),
                text[header.start():block_end],
                filepath,
            )


def _parse_move_types(moves_file):
    text = moves_file.read_text(encoding="utf-8")
    headers = list(MOVE_HEADER_PATTERN.finditer(text))
    move_types = {}

    for index, header in enumerate(headers):
        block_end = (
            headers[index + 1].start()
            if index + 1 < len(headers)
            else len(text)
        )
        block = text[header.start():block_end]
        type_match = MOVE_TYPE_PATTERN.search(block)

        if type_match is not None:
            move_types[header.group(1)] = type_match.group(1)

    if len(move_types) < 50:
        raise EvolutionMoveError(
            "Move parser found suspiciously few typed moves in "
            "src/data/moves_info.h."
        )

    return move_types


def _read_generally_learnable_moves(learnables_file, learnset_text):
    moves = set()

    if learnables_file.exists():
        with learnables_file.open("r", encoding="utf-8") as handle:
            learnables = json.load(handle)

        for species_moves in learnables.values():
            moves.update(species_moves)

    # This fallback also makes the component usable in development trees where
    # all_learnables.json has not yet been generated.
    if not moves:
        moves.update(
            match.group(1)
            for match in MOVE_ENTRY_LINE_PATTERN.finditer(learnset_text)
        )

    return moves


def _choose_move_for_type(required_type, move_types, generally_learnable):
    candidates = {
        move
        for move, move_type in move_types.items()
        if move_type == required_type and move in generally_learnable
    }

    if not candidates:
        raise EvolutionMoveError(
            "Could not find a generally learnable move whose current type is "
            f"{required_type}. The matching evolution cannot be guaranteed."
        )

    for preferred_move in TYPE_MOVE_PREFERENCES.get(required_type, ()):
        if preferred_move in candidates:
            return preferred_move

    return sorted(candidates)[0]


def _discover_requirements(species_dir, moves_file, learnables_file, learnset_text):
    move_types = _parse_move_types(moves_file)
    generally_learnable = _read_generally_learnable_moves(
        learnables_file,
        learnset_text,
    )
    requirements_by_learnset = defaultdict(set)
    audit_rows = []

    for species, block, filepath in _read_species_blocks(species_dir):
        if not species_is_enabled(species):
            continue

        pointer_match = LEARNSET_POINTER_PATTERN.search(block)

        if pointer_match is None:
            continue

        learnset = pointer_match.group(1)
        species_requirements = set()

        for reason, pattern in REQUIRED_MOVE_PATTERNS:
            for match in pattern.finditer(block):
                species_requirements.add((match.group(1), reason))

        for match in REQUIRED_MOVE_TYPE_PATTERN.finditer(block):
            required_type = match.group(1)
            move = _choose_move_for_type(
                required_type,
                move_types,
                generally_learnable,
            )
            species_requirements.add(
                (move, f"knows a current {required_type} move")
            )

        exception = SPECIES_MOVE_EXCEPTIONS.get(species)
        if exception is not None and RECOIL_CONDITION_PATTERN.search(block):
            species_requirements.add(exception)

        for move, reason in sorted(species_requirements):
            if move not in move_types:
                raise EvolutionMoveError(
                    f"{species} requires unknown move {move} in "
                    f"{filepath.relative_to(ROOT)}."
                )

            requirements_by_learnset[learnset].add(move)
            audit_rows.append((species, learnset, move, reason))

    return requirements_by_learnset, sorted(audit_rows)


def _rewrite_learnsets(learnset_text, requirements_by_learnset):
    found_learnsets = set()
    modified_learnsets = set()

    def replace_learnset(match):
        header = match.group(1)
        symbol = match.group(2)
        body = match.group(3)
        footer = match.group(4)

        required_moves = requirements_by_learnset.get(symbol)
        if not required_moves:
            return match.group(0)

        found_learnsets.add(symbol)

        def remove_required_entry(entry_match):
            if entry_match.group(1) in required_moves:
                return ""
            return entry_match.group(0)

        body_without_duplicates = MOVE_ENTRY_LINE_PATTERN.sub(
            remove_required_entry,
            body,
        )
        level_zero_entries = "".join(
            f"    LEVEL_UP_MOVE( 0, {move}),\n"
            for move in sorted(required_moves)
        )
        new_body = level_zero_entries + body_without_duplicates

        if new_body != body:
            modified_learnsets.add(symbol)

        return header + new_body + footer

    updated_text = LEARNSET_PATTERN.sub(replace_learnset, learnset_text)
    missing = set(requirements_by_learnset) - found_learnsets

    if missing:
        raise EvolutionMoveError(
            "Could not find required active level-up learnset table(s): "
            + ", ".join(sorted(missing))
        )

    for symbol, moves in requirements_by_learnset.items():
        match = re.search(
            r"static const struct LevelUpMove\s+"
            + re.escape(symbol)
            + r"\[\]\s*=\s*\{(.*?)^\};",
            updated_text,
            re.MULTILINE | re.DOTALL,
        )

        if match is None:
            raise EvolutionMoveError(
                f"Post-write audit could not find {symbol}."
            )

        for move in moves:
            occurrences = re.findall(
                LEVEL_ZERO_ENTRY_PATTERN_TEMPLATE.format(
                    move=re.escape(move)
                ),
                match.group(1),
            )
            if len(occurrences) != 1:
                raise EvolutionMoveError(
                    f"Post-write audit expected exactly one level-0 {move} "
                    f"entry in {symbol}; found {len(occurrences)}."
                )

    return updated_text, modified_learnsets


def apply_evolution_move_safeguards(root=ROOT):
    species_dir = root / "src/data/pokemon/species_info"
    learnset_file = root / "src/data/pokemon/level_up_learnsets/gen_9.h"
    moves_file = root / "src/data/moves_info.h"
    learnables_file = root / "src/data/pokemon/all_learnables.json"

    learnset_text = learnset_file.read_text(encoding="utf-8")
    requirements_by_learnset, audit_rows = _discover_requirements(
        species_dir,
        moves_file,
        learnables_file,
        learnset_text,
    )
    updated_text, modified_learnsets = _rewrite_learnsets(
        learnset_text,
        requirements_by_learnset,
    )

    learnset_file.write_text(updated_text, encoding="utf-8")

    print(
        "Evolution requirements discovered from current species data: "
        f"{len(audit_rows)}"
    )
    for species, _learnset, move, reason in audit_rows:
        print(f"  {species}: {move} ({reason})")

    print()
    print(
        "Level-up learnsets guaranteed: "
        f"{len(requirements_by_learnset)}"
    )
    print(f"Learnset tables changed: {len(modified_learnsets)}")
    print(
        "Audit passed: every required move appears exactly once at level 0."
    )

    return audit_rows


def main():
    # The shared randomizer engine supplies the seed as argv[1].  This
    # component is deterministic, but displaying the seed keeps logs uniform.
    seed = sys.argv[1] if len(sys.argv) > 1 else "not supplied"
    print(f"Evolution move safeguard seed: {seed} (deterministic component)")
    apply_evolution_move_safeguards()


if __name__ == "__main__":
    main()
