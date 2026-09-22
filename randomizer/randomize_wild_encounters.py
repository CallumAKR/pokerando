#!/usr/bin/env python3

import argparse
import ast
import json
import random
import re

from config import PROTECTED_SPECIES
from runtime_paths import ROOT
from wild_runtime_patch import (
    BST_TOLERANCE,
    install_runtime_wild_patch,
)


SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
ENCOUNTERS_FILE = ROOT / "src/data/wild_encounters.json"

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

BASE_STAT_FIELDS = (
    "baseHP",
    "baseAttack",
    "baseDefense",
    "baseSpeed",
    "baseSpAttack",
    "baseSpDefense",
)

SPECIES_HEADER_PATTERN = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$"
)


parser = argparse.ArgumentParser(
    description="Randomize normal wild Pokemon encounters."
)
parser.add_argument(
    "seed",
    nargs="?",
    type=int,
)
parser.add_argument(
    "--mode",
    choices=(
        "mapping",
        "slots",
        "runtime",
    ),
    required=True,
)
parser.add_argument(
    "--allow-special",
    action="store_true",
)
parser.add_argument(
    "--similar-bst",
    action="store_true",
)
args = parser.parse_args()

seed = (
    args.seed
    if args.seed is not None
    else random.randrange(2**32)
)
rng = random.Random(seed)

print(f"Wild encounter randomizer seed: {seed}")
print(f"Wild encounter mode: {args.mode}")
print(
    "Legendary / special Pokemon allowed: "
    + ("yes" if args.allow_special else "no")
)
print(
    f"Similar BST (±{BST_TOLERANCE}): "
    + ("yes" if args.similar_bst else "no")
)


species_blocks = {}


def read_species_blocks(filepath):
    lines = filepath.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines(keepends=True)

    i = 0

    while i < len(lines):
        match = SPECIES_HEADER_PATTERN.match(
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


for filepath in sorted(SPECIES_DIR.rglob("*.h")):
    read_species_blocks(filepath)

print(
    f"Found {len(species_blocks)} species entries."
)

if len(species_blocks) < 500:
    raise RuntimeError(
        "Species parser found suspiciously few species."
    )


def has_flag(block, flag):
    return (
        re.search(
            rf"\.{re.escape(flag)}\s*=\s*TRUE",
            block,
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


def get_base_species(block):
    match = re.search(
        r"\.baseSpecies\s*=\s*(SPECIES_[A-Z0-9_]+)",
        block,
    )
    return match.group(1) if match else None


def _safe_arithmetic(text):
    cleaned = text.strip()
    cleaned = re.sub(
        r"(?<=\d)[uUlL]+\b",
        "",
        cleaned,
    )

    if not re.fullmatch(
        r"[0-9xXa-fA-F+\-*/()% \t]+",
        cleaned,
    ):
        return None

    try:
        node = ast.parse(
            cleaned,
            mode="eval",
        )
    except SyntaxError:
        return None

    allowed = (
        ast.Expression,
        ast.Constant,
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
    )

    if any(
        not isinstance(item, allowed)
        for item in ast.walk(node)
    ):
        return None

    try:
        value = eval(
            compile(node, "<bst>", "eval"),
            {"__builtins__": {}},
            {},
        )
        return int(value)
    except Exception:
        return None


def parse_stat_expression(expression):
    expression = expression.strip()

    direct = _safe_arithmetic(
        expression
    )
    if direct is not None:
        return direct

    # Historical stat definitions commonly use:
    # (P_UPDATED_STATS >= GEN_X) ? updated : old
    # The randomizer targets the current/latest rules, so prefer the
    # first (updated) branch.
    ternary = re.search(
        r"\?\s*([^:]+?)\s*:\s*(.+)$",
        expression,
    )

    if ternary:
        preferred = _safe_arithmetic(
            ternary.group(1)
        )
        if preferred is not None:
            return preferred

        fallback = _safe_arithmetic(
            ternary.group(2)
        )
        if fallback is not None:
            return fallback

    return None


bst_cache = {}


def species_bst(
    species,
    visited=None,
):
    if species in bst_cache:
        return bst_cache[species]

    block = species_blocks.get(
        species
    )

    if block is None:
        bst_cache[species] = None
        return None

    if visited is None:
        visited = set()

    if species in visited:
        bst_cache[species] = None
        return None

    visited = set(visited)
    visited.add(species)

    values = []

    for field in BASE_STAT_FIELDS:
        match = re.search(
            rf"\.{field}\s*=\s*([^,\n]+)",
            block,
        )

        if not match:
            values = []
            break

        value = parse_stat_expression(
            match.group(1)
        )

        if value is None:
            values = []
            break

        values.append(value)

    if len(values) == len(BASE_STAT_FIELDS):
        result = sum(values)
        bst_cache[species] = result
        return result

    base_species = get_base_species(
        block
    )

    if base_species:
        result = species_bst(
            base_species,
            visited,
        )
        bst_cache[species] = result
        return result

    bst_cache[species] = None
    return None


species_special = {}
eligible_all = []

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

    special = is_special(block)
    species_special[species] = special

    if special and not args.allow_special:
        continue

    eligible_all.append(species)

eligible_all.sort()

if not eligible_all:
    raise RuntimeError(
        "Wild replacement species pool is empty."
    )

special_count = sum(
    1
    for species in eligible_all
    if species_special.get(species, False)
)

print()
print("Eligible wild replacement pool:")
print(f"  Total: {len(eligible_all)}")
print(f"  Special: {special_count}")
print(
    f"  Ordinary: {len(eligible_all) - special_count}"
)

if args.similar_bst:
    known_bst = sum(
        species_bst(species) is not None
        for species in eligible_all
    )
    print(
        f"  Species with parsed BST: "
        f"{known_bst}/{len(eligible_all)}"
    )


def candidate_pool(
    original_species,
):
    candidates = eligible_all

    if args.similar_bst:
        original_bst = species_bst(
            original_species
        )

        if original_bst is not None:
            bst_candidates = []

            for species in candidates:
                candidate_bst = species_bst(
                    species
                )

                if (
                    candidate_bst is not None
                    and abs(
                        candidate_bst
                        - original_bst
                    )
                    <= BST_TOLERANCE
                ):
                    bst_candidates.append(
                        species
                    )

            if bst_candidates:
                candidates = bst_candidates
            else:
                # Similar BST is a hard rule. If nothing eligible falls
                # inside the window, keep the original rather than widening
                # the pool to a much stronger/weaker Pokemon.
                return [original_species]
        else:
            # If this unusual source species has no parseable BST, do not
            # silently ignore the user's BST restriction.
            return [original_species]

    alternatives = [
        species
        for species in candidates
        if species != original_species
    ]

    return (
        alternatives
        if alternatives
        else [original_species]
    )


global_replacement_map = {}
mapping_targets_used = set()


def get_mapping(
    original_species,
):
    if original_species in global_replacement_map:
        return global_replacement_map[
            original_species
        ]

    candidates = candidate_pool(
        original_species
    )

    unused = [
        species
        for species in candidates
        if species not in mapping_targets_used
    ]

    if unused:
        candidates = unused

    replacement = rng.choice(
        candidates
    )

    global_replacement_map[
        original_species
    ] = replacement
    mapping_targets_used.add(
        replacement
    )

    return replacement


def choose_slot_replacement(
    original_species,
):
    return rng.choice(
        candidate_pool(
            original_species
        )
    )


def collect_original_wild_species():
    with ENCOUNTERS_FILE.open(
        "r",
        encoding="utf-8",
    ) as fp:
        data = json.load(fp)

    by_map = {}

    def walk(obj, map_name):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if (
                    key == "species"
                    and isinstance(value, str)
                    and value.startswith("SPECIES_")
                ):
                    by_map.setdefault(
                        map_name,
                        set(),
                    ).add(value)
                else:
                    walk(
                        value,
                        map_name,
                    )

        elif isinstance(obj, list):
            for value in obj:
                walk(
                    value,
                    map_name,
                )

    for group in data.get(
        "wild_encounter_groups",
        [],
    ):
        for encounter in group.get(
            "encounters",
            [],
        ):
            walk(
                encounter,
                encounter.get(
                    "map",
                    "UNKNOWN_MAP",
                ),
            )

    return by_map


def audit_bst_rule_for_encounter_species():
    if not args.similar_bst:
        return 0

    by_map = collect_original_wild_species()

    originals = sorted(
        {
            species
            for species_set in by_map.values()
            for species in species_set
        }
    )

    checked = 0

    for original in originals:
        original_bst = species_bst(
            original
        )

        if original_bst is None:
            continue

        for candidate in candidate_pool(
            original
        ):
            if candidate == original:
                continue

            candidate_bst = species_bst(
                candidate
            )

            if candidate_bst is None:
                raise RuntimeError(
                    "BST audit found an unknown-BST candidate: "
                    f"{original} -> {candidate}"
                )

            difference = abs(
                candidate_bst
                - original_bst
            )

            if difference > BST_TOLERANCE:
                raise RuntimeError(
                    "BST audit failed: "
                    f"{original} ({original_bst}) -> "
                    f"{candidate} ({candidate_bst}) "
                    f"differs by {difference}."
                )

        checked += 1

    print(
        f"BST candidate audit passed for "
        f"{checked} encounter-table species."
    )

    route101 = sorted(
        by_map.get(
            "MAP_ROUTE101",
            set(),
        )
    )

    if route101:
        details = []

        for species in route101:
            bst = species_bst(
                species
            )

            details.append(
                f"{species}="
                f"{bst if bst is not None else 'unknown'}"
            )

        print(
            "MAP_ROUTE101 source BSTs: "
            + ", ".join(details)
        )

    return checked


if args.mode == "runtime":
    audit_bst_rule_for_encounter_species()

    by_map = collect_original_wild_species()

    source_species = sorted(
        {
            species
            for species_set in by_map.values()
            for species in species_set
        }
    )

    # Crucial runtime guarantee:
    # Python creates the final legal list for every encounter-table source
    # species. The ROM never re-evaluates BST/special eligibility.
    runtime_candidate_map = {
        original: candidate_pool(original)
        for original in source_species
    }

    # Second hard audit of the exact lists that will be compiled into the ROM.
    if args.similar_bst:
        for original, candidates in runtime_candidate_map.items():
            original_bst = species_bst(
                original
            )

            if original_bst is None:
                if candidates != [original]:
                    raise RuntimeError(
                        "Runtime BST audit expected an unknown-BST source "
                        f"to remain unchanged: {original}"
                    )
                continue

            for candidate in candidates:
                if candidate == original:
                    continue

                candidate_bst = species_bst(
                    candidate
                )

                if candidate_bst is None:
                    raise RuntimeError(
                        "Runtime candidate has no BST: "
                        f"{original} -> {candidate}"
                    )

                difference = abs(
                    candidate_bst
                    - original_bst
                )

                if difference > BST_TOLERANCE:
                    raise RuntimeError(
                        "Runtime candidate exceeds BST threshold: "
                        f"{original} ({original_bst}) -> "
                        f"{candidate} ({candidate_bst}), "
                        f"difference {difference}."
                    )

    route101 = sorted(
        by_map.get(
            "MAP_ROUTE101",
            set(),
        )
    )

    if route101:
        print()
        print("MAP_ROUTE101 compiled runtime pools:")

        for original in route101:
            original_bst = species_bst(
                original
            )
            candidates = runtime_candidate_map[
                original
            ]

            candidate_bsts = [
                species_bst(candidate)
                for candidate in candidates
                if species_bst(candidate) is not None
            ]

            if candidate_bsts:
                bst_span = (
                    f"{min(candidate_bsts)}-{max(candidate_bsts)}"
                )
            else:
                bst_span = "unknown"

            print(
                f"  {original}: BST {original_bst}, "
                f"{len(candidates)} candidate(s), "
                f"candidate BST span {bst_span}"
            )

    header = install_runtime_wild_patch(
        runtime_candidate_map,
        seed=seed,
    )

    print()
    print(
        "Runtime wild encounter reroll enabled."
    )
    print(
        "Encounter-table species and levels remain unchanged; "
        "each battle chooses only from its Python-approved replacement pool."
    )
    print(
        "Runtime route-table mode suppresses roamer, mass-outbreak, and "
        "fixed Feebas overrides so they cannot bypass the BST pool."
    )
    print(
        "Clean generated wild_encounters.h will be rebuilt from the current "
        "wild_encounters.json during the ROM build."
    )
    print(
        f"Generated: "
        f"{header.relative_to(ROOT)}"
    )
    print(f"Seed: {seed}")
    raise SystemExit(0)


with ENCOUNTERS_FILE.open(
    "r",
    encoding="utf-8",
) as fp:
    encounter_data = json.load(fp)

changed_slots = 0
unchanged_slots = 0
randomized_maps = set()


def randomize_object(
    obj,
    map_name,
):
    global changed_slots
    global unchanged_slots

    if isinstance(obj, dict):
        for key, value in obj.items():
            if (
                key == "species"
                and isinstance(value, str)
                and value.startswith("SPECIES_")
            ):
                original = value

                replacement = (
                    get_mapping(original)
                    if args.mode == "mapping"
                    else choose_slot_replacement(
                        original
                    )
                )

                obj[key] = replacement
                randomized_maps.add(
                    map_name
                )

                if replacement == original:
                    unchanged_slots += 1
                else:
                    changed_slots += 1
            else:
                randomize_object(
                    value,
                    map_name,
                )

    elif isinstance(obj, list):
        for value in obj:
            randomize_object(
                value,
                map_name,
            )


for group in encounter_data.get(
    "wild_encounter_groups",
    [],
):
    for encounter in group.get(
        "encounters",
        [],
    ):
        randomize_object(
            encounter,
            encounter.get(
                "map",
                "UNKNOWN_MAP",
            ),
        )


with ENCOUNTERS_FILE.open(
    "w",
    encoding="utf-8",
) as fp:
    json.dump(
        encounter_data,
        fp,
        indent=2,
    )
    fp.write("\n")


print()
print(
    f"Randomized maps: "
    f"{len(randomized_maps)}"
)
print(
    f"Changed encounter slots: "
    f"{changed_slots}"
)
print(
    f"Unchanged encounter slots: "
    f"{unchanged_slots}"
)

if args.mode == "mapping":
    print(
        f"Global species mappings: "
        f"{len(global_replacement_map)}"
    )

print(f"Seed: {seed}")
