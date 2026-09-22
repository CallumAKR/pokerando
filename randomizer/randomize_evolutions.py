#!/usr/bin/env python3

import ast
import random
import re
import sys
from pathlib import Path

from config import PROTECTED_SPECIES
from manual_customization_runtime import species_is_enabled


ROOT = Path(__file__).resolve().parent.parent
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"

EVOLUTION_TARGET_BST_TOLERANCE = 25

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
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

# The target species is the third field in Expansion evolution entries.
# Only that SPECIES_* token is replaced; method/conditions stay unchanged.
EVOLUTION_TARGET_PATTERN = re.compile(
    r"(\{\s*EVO_[A-Z0-9_]+\s*,\s*[^,{}\n]+\s*,\s*)"
    r"(SPECIES_[A-Z0-9_]+)"
)


seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

print(f"Evolution randomizer seed: {seed}")
print(
    "Rule: every randomized evolution target must have strictly higher BST "
    "than the species that evolves."
)
print(
    f"Power matching: prefer targets within ±{EVOLUTION_TARGET_BST_TOLERANCE} "
    "BST of the original evolution target."
)


def has_flag(block, flag):
    return (
        re.search(
            rf"\.{re.escape(flag)}\s*=\s*TRUE",
            block,
        )
        is not None
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


def safe_arithmetic(text):
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
            compile(
                node,
                "<evolution-bst>",
                "eval",
            ),
            {"__builtins__": {}},
            {},
        )
        return int(value)
    except Exception:
        return None


def parse_stat_expression(expression):
    expression = expression.strip()

    direct = safe_arithmetic(
        expression
    )

    if direct is not None:
        return direct

    ternary = re.search(
        r"\?\s*([^:]+?)\s*:\s*(.+)$",
        expression,
    )

    if ternary:
        preferred = safe_arithmetic(
            ternary.group(1)
        )

        if preferred is not None:
            return preferred

        fallback = safe_arithmetic(
            ternary.group(2)
        )

        if fallback is not None:
            return fallback

    return None


species_blocks = {}
species_locations = {}
file_texts = {}

for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):
    text = filepath.read_text(
        encoding="utf-8"
    )
    file_texts[filepath] = text

    headers = list(
        SPECIES_HEADER_PATTERN.finditer(
            text
        )
    )

    for index, match in enumerate(headers):
        species = match.group(1)
        start = match.start()
        end = (
            headers[index + 1].start()
            if index + 1 < len(headers)
            else len(text)
        )

        species_blocks[species] = text[start:end]
        species_locations[species] = (
            filepath,
            start,
            end,
        )

print(
    f"Found {len(species_blocks)} species entries."
)


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


eligible_targets = []

for species, block in species_blocks.items():
    if species in PROTECTED_SPECIES:
        continue

    if is_invalid_form(block):
        continue

    if species_bst(species) is None:
        continue

    eligible_targets.append(
        species
    )

eligible_targets.sort()

print(
    f"Eligible permanent evolution targets with parsed BST: "
    f"{len(eligible_targets)}"
)

if not eligible_targets:
    raise RuntimeError(
        "No eligible evolution targets were found."
    )


edge_mapping = {}
changed_edges = 0
unchanged_edges = 0
unparsed_edges = 0
fallback_edges = 0
protected_sources = 0
changed_audit = []


def choose_target(
    source_species,
    original_target,
):
    global fallback_edges

    key = (
        source_species,
        original_target,
    )

    if key in edge_mapping:
        return edge_mapping[key]

    source_bst = species_bst(
        source_species
    )
    original_target_bst = species_bst(
        original_target
    )

    if (
        source_bst is None
        or original_target_bst is None
    ):
        edge_mapping[key] = original_target
        return original_target

    # Strictly increasing BST also makes a randomized evolution cycle
    # impossible, because BST cannot increase around a closed loop.
    stronger = [
        species
        for species in eligible_targets
        if species != source_species
        and species_bst(species) > source_bst
    ]

    if not stronger:
        edge_mapping[key] = original_target
        return original_target

    preferred = [
        species
        for species in stronger
        if abs(
            species_bst(species)
            - original_target_bst
        )
        <= EVOLUTION_TARGET_BST_TOLERANCE
    ]

    candidates = preferred

    if not candidates:
        fallback_edges += 1

        closest_difference = min(
            abs(
                species_bst(species)
                - original_target_bst
            )
            for species in stronger
        )

        candidates = [
            species
            for species in stronger
            if abs(
                species_bst(species)
                - original_target_bst
            )
            == closest_difference
        ]

    changed_candidates = [
        species
        for species in candidates
        if species != original_target
    ]

    if changed_candidates:
        candidates = changed_candidates

    result = rng.choice(
        candidates
    )

    edge_mapping[key] = result

    return result


rewritten_blocks = {}

for source_species, block in species_blocks.items():
    if ".evolutions" not in block:
        continue

    matches = list(
        EVOLUTION_TARGET_PATTERN.finditer(
            block
        )
    )

    if not matches:
        continue

    if (
        source_species in PROTECTED_SPECIES
        or not species_is_enabled(source_species)
    ):
        protected_sources += 1
        continue

    source_bst = species_bst(
        source_species
    )

    def replace_edge(match):
        global changed_edges, unchanged_edges, unparsed_edges

        prefix = match.group(1)
        original_target = match.group(2)

        original_target_bst = species_bst(
            original_target
        )

        if (
            source_bst is None
            or original_target_bst is None
        ):
            unparsed_edges += 1
            return match.group(0)

        new_target = choose_target(
            source_species,
            original_target,
        )

        if new_target == original_target:
            unchanged_edges += 1
            return match.group(0)

        new_bst = species_bst(
            new_target
        )

        if (
            new_bst is None
            or new_bst <= source_bst
        ):
            raise RuntimeError(
                "Evolution BST audit failed before write: "
                f"{source_species} BST {source_bst} -> "
                f"{new_target} BST {new_bst}."
            )

        changed_edges += 1
        changed_audit.append(
            (
                source_species,
                source_bst,
                original_target,
                original_target_bst,
                new_target,
                new_bst,
            )
        )

        return prefix + new_target

    new_block = EVOLUTION_TARGET_PATTERN.sub(
        replace_edge,
        block,
    )

    if new_block != block:
        rewritten_blocks[
            source_species
        ] = new_block


replacements_by_file = {}

for species, new_block in rewritten_blocks.items():
    filepath, start, end = species_locations[
        species
    ]

    replacements_by_file.setdefault(
        filepath,
        []
    ).append(
        (
            start,
            end,
            new_block,
        )
    )

for filepath, replacements in replacements_by_file.items():
    text = file_texts[
        filepath
    ]

    for start, end, new_block in sorted(
        replacements,
        reverse=True,
    ):
        text = (
            text[:start]
            + new_block
            + text[end:]
        )

    filepath.write_text(
        text,
        encoding="utf-8",
    )


for (
    source_species,
    source_bst,
    original_target,
    original_target_bst,
    new_target,
    new_bst,
) in changed_audit:
    if new_bst <= source_bst:
        raise RuntimeError(
            "Final evolution BST audit failed: "
            f"{source_species} BST {source_bst} -> "
            f"{new_target} BST {new_bst}."
        )

print()
print(
    f"Randomized evolution edges: "
    f"{changed_edges}"
)
print(
    f"Evolution edges left unchanged: "
    f"{unchanged_edges}"
)
print(
    f"Edges skipped because BST could not be parsed: "
    f"{unparsed_edges}"
)
print(
    f"Power-match fallbacks outside ±"
    f"{EVOLUTION_TARGET_BST_TOLERANCE}: "
    f"{fallback_edges}"
)
print(
    f"Protected species with evolution data left unchanged: "
    f"{protected_sources}"
)

if changed_audit:
    weakest_gain = min(
        new_bst - source_bst
        for (
            _,
            source_bst,
            _,
            _,
            _,
            new_bst,
        ) in changed_audit
    )

    print(
        "BST upgrade audit passed for every changed evolution edge. "
        f"Smallest randomized BST increase: +{weakest_gain}."
    )

print(f"Seed: {seed}")
