#!/usr/bin/env python3

import ast
import math
import random
import re
import sys
from collections import defaultdict
from pathlib import Path

from config import PROTECTED_SPECIES
from manual_customization_runtime import species_is_enabled


ROOT = Path(__file__).resolve().parent.parent
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
FORM_CHANGE_TABLES = (
    ROOT
    / "src/data/pokemon/form_change_tables.h"
)

STAT_MIN_SHARE = 0.10
STAT_MAX_SHARE = 0.50
MAX_BASE_STAT = 255

# Stage-aware mode guarantees sensible overall evolution progression.
MIN_EVOLUTION_GAIN = 25
THREE_STAGE_BASE_FINAL_MIN_GAIN = 110

# These bands deliberately leave room for a middle stage.
#
# In a three-stage family:
#   base max 350
#   final min 470
# so base -> final is at least +120 before the direct edge/path checks.
STAGE_BST_RANGES = {
    "three_base": (180, 350),
    "three_middle": (350, 470),
    "three_final": (470, 650),
    "two_base": (180, 450),
    "two_final": (400, 650),
    "single": (180, 650),
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
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

EVOLUTION_TARGET_PATTERN = re.compile(
    r"\{\s*EVO_[A-Z0-9_]+\s*,\s*[^,{}\n]+\s*,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
)

FORM_CHANGE_TABLE_PATTERN = re.compile(
    r"static const struct FormChange\s+"
    r"(s[A-Za-z0-9_]+)\[\]\s*=\s*\{"
    r"(.*?)\n\};",
    re.DOTALL,
)

MEGA_TARGET_PATTERN = re.compile(
    r"\{\s*FORM_CHANGE_BATTLE_MEGA_EVOLUTION_ITEM\s*,\s*"
    r"(SPECIES_[A-Z0-9_]+)\s*,\s*"
    r"ITEM_[A-Z0-9_]+"
)


def parse_mode(argv):
    mode = None

    for index, value in enumerate(argv):
        if value == "--mode" and index + 1 < len(argv):
            mode = argv[index + 1]

    if mode not in {
        "same",
        "stages",
        "full",
    }:
        raise RuntimeError(
            "Pokémon BST randomization requires "
            "--mode same, --mode stages, or --mode full."
        )

    return mode


MODE = parse_mode(
    sys.argv[2:]
)

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

MODE_LABELS = {
    "same": "Keep BST the same; randomize stat distribution",
    "stages": "Randomize BST within evolution-stage ranges; Megas gain +100",
    "full": "Fully randomize BST with no evolution-stage ranges; Megas gain +100",
}

print(f"Pokémon BST randomizer seed: {seed}")
print(f"Mode: {MODE_LABELS[MODE]}")
print(
    "Per-stat guard: minimum 10% of total BST, maximum 50% of total BST "
    "(also capped at 255 because base stats are byte-sized)."
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
                "<pokemon-bst>",
                "eval",
            ),
            {"__builtins__": {}},
            {},
        )
        return int(value)
    except Exception:
        return None


def parse_stat_expression(
    expression,
    macro_expressions=None,
    resolving=None,
):
    expression = expression.strip()

    direct = safe_arithmetic(
        expression
    )

    if direct is not None:
        return direct

    macro_name = re.fullmatch(
        r"[A-Z][A-Z0-9_]*",
        expression,
    )

    if (
        macro_name
        and macro_expressions is not None
        and macro_name.group(0) in macro_expressions
    ):
        name = macro_name.group(0)
        resolving = set(
            resolving
            or ()
        )

        if name in resolving:
            return None

        resolving.add(
            name
        )

        return parse_stat_expression(
            macro_expressions[name],
            macro_expressions,
            resolving,
        )

    # Expansion frequently uses generation/config ternaries. The current
    # randomizer consistently targets the active/updated first branch.
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


def parse_stats(
    block,
    macro_expressions=None,
):
    values = {}

    for field in BASE_STAT_FIELDS:
        match = re.search(
            rf"\.{field}\s*=\s*([^,\n]+)",
            block,
        )

        if not match:
            return None

        value = parse_stat_expression(
            match.group(1),
            macro_expressions,
        )

        if value is None:
            return None

        values[field] = value

    return values


def collect_macro_expressions(text):
    expressions = {}

    for match in re.finditer(
        r"(?m)^\s*#define\s+([A-Z][A-Z0-9_]*)\s+([^\n/]+)",
        text,
    ):
        # Like ternary stat expressions, conditional macro definitions use
        # the first/current updated branch consistently in this randomizer.
        expressions.setdefault(
            match.group(1),
            match.group(2).strip(),
        )

    return expressions


def replace_stats(
    block,
    new_stats,
):
    result = block

    for field in BASE_STAT_FIELDS:
        value = new_stats[
            field
        ]

        result, count = re.subn(
            rf"(\.{field}\s*=\s*)[^,\n]+",
            lambda match: (
                match.group(1)
                + str(value)
            ),
            result,
            count=1,
        )

        if count != 1:
            raise RuntimeError(
                f"Could not rewrite {field}."
            )

    return result


# ------------------------------------------------------------
# READ SPECIES BLOCKS
# ------------------------------------------------------------

species_blocks = {}
species_locations = {}
file_texts = {}
original_stats = {}
original_bst = {}
invalid_species = set()

for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):
    text = filepath.read_text(
        encoding="utf-8"
    )

    file_texts[
        filepath
    ] = text

    macro_expressions = collect_macro_expressions(
        text
    )

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

        block = text[
            start:end
        ]

        species_blocks[
            species
        ] = block

        species_locations[
            species
        ] = (
            filepath,
            start,
            end,
        )

        if is_invalid_form(block):
            invalid_species.add(
                species
            )

        stats = parse_stats(
            block,
            macro_expressions,
        )

        if stats is not None:
            original_stats[
                species
            ] = stats

            original_bst[
                species
            ] = sum(
                stats.values()
            )

print(
    f"Found {len(species_blocks)} species entries."
)
print(
    f"Found {len(original_bst)} species with explicit parseable base stats."
)


# ------------------------------------------------------------
# CANONICAL MEGA PAIRS
# ------------------------------------------------------------

species_by_form_table = defaultdict(
    list
)

for species, block in species_blocks.items():
    match = re.search(
        r"\.formChangeTable\s*=\s*(s[A-Za-z0-9_]+)",
        block,
    )

    if match:
        species_by_form_table[
            match.group(1)
        ].append(
            species
        )

form_change_text = FORM_CHANGE_TABLES.read_text(
    encoding="utf-8"
)

mega_to_base = {}
mega_mapping_entries = 0

for match in FORM_CHANGE_TABLE_PATTERN.finditer(
    form_change_text
):
    table_name = match.group(1)
    mega_targets = MEGA_TARGET_PATTERN.findall(
        match.group(2)
    )

    if not mega_targets:
        continue

    base_candidates = [
        species
        for species in species_by_form_table.get(
            table_name,
            ()
        )
        if species in original_bst
        and species not in invalid_species
    ]

    if len(base_candidates) != 1:
        raise RuntimeError(
            "Could not resolve one canonical non-Mega source for "
            f"{table_name}: {base_candidates}."
        )

    base_species = base_candidates[0]

    for mega_species in mega_targets:
        mega_mapping_entries += 1

        if mega_species not in original_bst:
            raise RuntimeError(
                "Mega form-change target has no parseable stats: "
                f"{mega_species}."
            )

        previous_base = mega_to_base.get(
            mega_species
        )

        if (
            previous_base is not None
            and previous_base != base_species
        ):
            raise RuntimeError(
                f"Mega target {mega_species} maps from both "
                f"{previous_base} and {base_species}."
            )

        mega_to_base[
            mega_species
        ] = base_species

if not mega_to_base:
    raise RuntimeError(
        "No item-driven Mega Evolution pairs were found."
    )

print(
    "Found "
    f"{mega_mapping_entries} canonical Mega Stone transformations "
    f"covering {len(mega_to_base)} Mega species."
)


# ------------------------------------------------------------
# PERMANENT EVOLUTION GRAPH
# ------------------------------------------------------------

parents = defaultdict(set)
children = defaultdict(set)

graph_nodes = {
    species
    for species in original_bst
    if species not in invalid_species
}

for source_species in graph_nodes:
    block = species_blocks[
        source_species
    ]

    for target_species in (
        EVOLUTION_TARGET_PATTERN.findall(
            block
        )
    ):
        if target_species not in graph_nodes:
            continue

        if target_species == source_species:
            continue

        children[
            source_species
        ].add(
            target_species
        )

        parents[
            target_species
        ].add(
            source_species
        )


up_depth_cache = {}
down_depth_cache = {}


def max_parent_depth(
    species,
    visiting=None,
):
    if species in up_depth_cache:
        return up_depth_cache[
            species
        ]

    if visiting is None:
        visiting = set()

    if species in visiting:
        return 0

    visiting = set(
        visiting
    )
    visiting.add(
        species
    )

    values = [
        1
        + max_parent_depth(
            parent,
            visiting,
        )
        for parent in parents.get(
            species,
            ()
        )
    ]

    result = (
        max(values)
        if values
        else 0
    )

    up_depth_cache[
        species
    ] = result

    return result


def max_child_depth(
    species,
    visiting=None,
):
    if species in down_depth_cache:
        return down_depth_cache[
            species
        ]

    if visiting is None:
        visiting = set()

    if species in visiting:
        return 0

    visiting = set(
        visiting
    )
    visiting.add(
        species
    )

    values = [
        1
        + max_child_depth(
            child,
            visiting,
        )
        for child in children.get(
            species,
            ()
        )
    ]

    result = (
        max(values)
        if values
        else 0
    )

    down_depth_cache[
        species
    ] = result

    return result


def stage_category(
    species,
):
    up = max_parent_depth(
        species
    )
    down = max_child_depth(
        species
    )

    # Any path containing 3+ Pokémon belongs to the three-stage bands.
    if up + down >= 2:
        if up == 0:
            return "three_base"

        if down == 0:
            return "three_final"

        return "three_middle"

    if down > 0:
        return "two_base"

    if up > 0:
        return "two_final"

    return "single"


categories = {
    species: stage_category(
        species
    )
    for species in graph_nodes
}


# ------------------------------------------------------------
# STAT DISTRIBUTION
# ------------------------------------------------------------

def stat_bounds(
    bst,
):
    minimum = max(
        1,
        math.ceil(
            bst
            * STAT_MIN_SHARE
        ),
    )

    maximum = min(
        MAX_BASE_STAT,
        math.floor(
            bst
            * STAT_MAX_SHARE
        ),
    )

    if 6 * minimum > bst:
        raise RuntimeError(
            f"BST {bst} cannot satisfy the 10% minimum stat rule."
        )

    if 6 * maximum < bst:
        raise RuntimeError(
            f"BST {bst} cannot satisfy the 50%/255 maximum stat rule."
        )

    return (
        minimum,
        maximum,
    )


def random_stat_distribution(
    bst,
):
    minimum, maximum = stat_bounds(
        bst
    )

    values = [
        minimum
        for _ in BASE_STAT_FIELDS
    ]

    remaining = (
        bst
        - sum(values)
    )

    capacity = (
        maximum
        - minimum
    )

    order = list(
        range(
            len(values)
        )
    )

    rng.shuffle(
        order
    )

    for position, index in enumerate(
        order
    ):
        remaining_slots = order[
            position + 1:
        ]

        remaining_capacity = (
            len(remaining_slots)
            * capacity
        )

        min_extra = max(
            0,
            remaining
            - remaining_capacity,
        )

        max_extra = min(
            capacity,
            remaining,
        )

        if position == len(order) - 1:
            extra = remaining
        else:
            extra = rng.randint(
                min_extra,
                max_extra,
            )

        values[
            index
        ] += extra

        remaining -= extra

    if remaining != 0:
        raise RuntimeError(
            "Internal stat-distribution error: BST remainder was not zero."
        )

    if sum(values) != bst:
        raise RuntimeError(
            "Internal stat-distribution error: stats do not total BST."
        )

    if any(
        value < minimum
        or value > maximum
        for value in values
    ):
        raise RuntimeError(
            "Internal stat-distribution error: generated stat outside guard."
        )

    return dict(
        zip(
            BASE_STAT_FIELDS,
            values,
        )
    )


# ------------------------------------------------------------
# CHOOSE TARGET BSTS
# ------------------------------------------------------------

randomizable_species = sorted(
    species
    for species in original_bst
    if species not in PROTECTED_SPECIES
    and species not in invalid_species
    and species_is_enabled(species)
)

randomizable_mega_species = sorted(
    species
    for species in mega_to_base
    if species not in PROTECTED_SPECIES
    and species_is_enabled(species)
)

all_randomizable_species = (
    randomizable_species
    + randomizable_mega_species
)

if not all_randomizable_species:
    print("No source Pokémon are enabled for this BST pass.")
    print(f"Seed: {seed}")
    raise SystemExit(0)

target_bst = {}


if MODE == "same":
    for species in randomizable_species:
        target_bst[
            species
        ] = original_bst[
            species
        ]


elif MODE == "full":
    natural_range_species = [
        species
        for species in original_bst
        if species not in PROTECTED_SPECIES
        and species not in invalid_species
    ]

    natural_min = min(
        original_bst[
            species
        ]
        for species in natural_range_species
    )

    natural_max = max(
        original_bst[
            species
        ]
        for species in natural_range_species
    )

    print()
    print(
        "Fully random BST range is based on the natural eligible Pokémon "
        f"range in this Expansion build: {natural_min}–{natural_max}."
    )
    print(
        "Evolution-stage protection is intentionally OFF in this mode."
    )

    for species in randomizable_species:
        target_bst[
            species
        ] = rng.randint(
            natural_min,
            natural_max,
        )


elif MODE == "stages":
    print()
    print("Evolution-stage BST ranges:")

    for category in (
        "three_base",
        "three_middle",
        "three_final",
        "two_base",
        "two_final",
        "single",
    ):
        low, high = STAGE_BST_RANGES[
            category
        ]

        print(
            f"  {category}: {low}–{high}"
        )

    # Fixed/protected nodes keep their current BST. Randomized nodes are
    # processed from earliest to latest evolutionary depth so parent BSTs are
    # already known when choosing a child.
    final_or_fixed_bst = {
        species: original_bst[
            species
        ]
        for species in graph_nodes
        if species not in randomizable_species
    }

    ordered = sorted(
        randomizable_species,
        key=lambda species: (
            max_parent_depth(
                species
            ),
            species,
        ),
    )

    for species in ordered:
        category = categories.get(
            species,
            "single",
        )

        low, high = STAGE_BST_RANGES[
            category
        ]

        parent_values = [
            final_or_fixed_bst[
                parent
            ]
            for parent in parents.get(
                species,
                ()
            )
            if parent in final_or_fixed_bst
        ]

        if parent_values:
            low = max(
                low,
                max(parent_values)
                + MIN_EVOLUTION_GAIN,
            )

        # A randomized base/middle must leave room below a protected child.
        protected_child_values = [
            original_bst[
                child
            ]
            for child in children.get(
                species,
                ()
            )
            if child not in randomizable_species
            and child in original_bst
        ]

        if protected_child_values:
            high = min(
                high,
                min(protected_child_values)
                - MIN_EVOLUTION_GAIN,
            )

        # For a final stage, explicitly guarantee a little over +100 versus
        # any two-step ancestor already assigned/fixed.
        if category == "three_final":
            grandparent_values = []

            for parent in parents.get(
                species,
                ()
            ):
                for grandparent in parents.get(
                    parent,
                    ()
                ):
                    if grandparent in final_or_fixed_bst:
                        grandparent_values.append(
                            final_or_fixed_bst[
                                grandparent
                            ]
                        )

            if grandparent_values:
                low = max(
                    low,
                    max(grandparent_values)
                    + THREE_STAGE_BASE_FINAL_MIN_GAIN,
                )

        if low > high:
            raise RuntimeError(
                "Evolution-stage BST constraints became impossible for "
                f"{species}: required range {low}–{high}. "
                "This usually indicates a protected/custom evolution line "
                "whose fixed BST conflicts with the stage guard."
            )

        chosen = rng.randint(
            low,
            high,
        )

        target_bst[
            species
        ] = chosen

        final_or_fixed_bst[
            species
        ] = chosen


# Mega targets are canonical form-table pairs, not ordinary evolution-graph
# stages. Same-BST mode preserves each Mega's own natural total. Modes that
# choose a new total for the base form preserve Mega Evolution's +100 upgrade.
for mega_species in randomizable_mega_species:
    base_species = mega_to_base[
        mega_species
    ]

    if MODE == "same":
        target_bst[
            mega_species
        ] = original_bst[
            mega_species
        ]
    else:
        base_bst = target_bst.get(
            base_species,
            original_bst[
                base_species
            ],
        )

        target_bst[
            mega_species
        ] = base_bst + 100


# ------------------------------------------------------------
# RANDOMIZE STAT SHAPES
# ------------------------------------------------------------

rewritten_blocks = {}
changed_species = 0
same_bst_species = 0

for species in all_randomizable_species:
    bst = target_bst[
        species
    ]

    generated = random_stat_distribution(
        bst
    )

    # Avoid leaving an identical stat vector when possible, particularly in
    # "same BST" mode where distribution randomization is the whole feature.
    original_vector = original_stats[
        species
    ]

    attempts = 0

    while (
        generated == original_vector
        and attempts < 12
    ):
        generated = random_stat_distribution(
            bst
        )
        attempts += 1

    block = species_blocks[
        species
    ]

    rewritten_blocks[
        species
    ] = replace_stats(
        block,
        generated,
    )

    changed_species += 1

    if (
        bst
        == original_bst[
            species
        ]
    ):
        same_bst_species += 1


# ------------------------------------------------------------
# WRITE BACK BY ORIGINAL FILE OFFSETS
# ------------------------------------------------------------

replacements_by_file = defaultdict(
    list
)

for species, new_block in (
    rewritten_blocks.items()
):
    filepath, start, end = (
        species_locations[
            species
        ]
    )

    replacements_by_file[
        filepath
    ].append(
        (
            start,
            end,
            new_block,
        )
    )

for filepath, replacements in (
    replacements_by_file.items()
):
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


# ------------------------------------------------------------
# HARD AUDIT
# ------------------------------------------------------------

audited_bst = {}

for species in all_randomizable_species:
    new_block = rewritten_blocks[
        species
    ]

    parsed = parse_stats(
        new_block
    )

    if parsed is None:
        raise RuntimeError(
            f"BST audit could not re-read {species}."
        )

    bst = sum(
        parsed.values()
    )

    expected = target_bst[
        species
    ]

    if bst != expected:
        raise RuntimeError(
            f"BST audit failed for {species}: expected {expected}, got {bst}."
        )

    minimum, maximum = stat_bounds(
        bst
    )

    if any(
        value < minimum
        or value > maximum
        for value in parsed.values()
    ):
        raise RuntimeError(
            f"Stat guard audit failed for {species}: "
            f"{parsed}; allowed {minimum}–{maximum}."
        )

    audited_bst[
        species
    ] = bst


if MODE == "same":
    for species in all_randomizable_species:
        if (
            audited_bst[
                species
            ]
            != original_bst[
                species
            ]
        ):
            raise RuntimeError(
                f"Same-BST audit failed for {species}."
            )


if MODE in {"stages", "full"}:
    for mega_species in randomizable_mega_species:
        base_species = mega_to_base[
            mega_species
        ]
        base_value = audited_bst.get(
            base_species,
            original_bst[
                base_species
            ],
        )
        mega_value = audited_bst[
            mega_species
        ]

        if mega_value != base_value + 100:
            raise RuntimeError(
                "Mega BST audit failed: "
                f"{base_species} BST {base_value} -> "
                f"{mega_species} BST {mega_value}; expected +100."
            )


if MODE == "stages":
    stage_edge_gains = []
    three_stage_path_gains = []

    for source, source_children in (
        children.items()
    ):
        for child in source_children:
            # Ignore fully fixed/protected edges. Any edge touched by this
            # component must respect the stage-aware progression rule.
            if (
                source not in randomizable_species
                and child not in randomizable_species
            ):
                continue

            source_value = (
                audited_bst.get(
                    source,
                    original_bst.get(
                        source
                    ),
                )
            )

            child_value = (
                audited_bst.get(
                    child,
                    original_bst.get(
                        child
                    ),
                )
            )

            if (
                source_value is None
                or child_value is None
            ):
                continue

            gain = (
                child_value
                - source_value
            )

            if gain < MIN_EVOLUTION_GAIN:
                raise RuntimeError(
                    "Evolution-stage BST audit failed: "
                    f"{source} BST {source_value} -> "
                    f"{child} BST {child_value}; "
                    f"minimum gain is +{MIN_EVOLUTION_GAIN}."
                )

            stage_edge_gains.append(
                gain
            )

            for grandchild in children.get(
                child,
                ()
            ):
                grandchild_value = (
                    audited_bst.get(
                        grandchild,
                        original_bst.get(
                            grandchild
                        ),
                    )
                )

                if grandchild_value is None:
                    continue

                path_gain = (
                    grandchild_value
                    - source_value
                )

                if (
                    source in randomizable_species
                    or child in randomizable_species
                    or grandchild in randomizable_species
                ):
                    if (
                        path_gain
                        < THREE_STAGE_BASE_FINAL_MIN_GAIN
                    ):
                        raise RuntimeError(
                            "Three-stage BST audit failed: "
                            f"{source} BST {source_value} -> "
                            f"{grandchild} BST {grandchild_value}; "
                            "base-to-final minimum is "
                            f"+{THREE_STAGE_BASE_FINAL_MIN_GAIN}."
                        )

                    three_stage_path_gains.append(
                        path_gain
                    )

    print()
    if stage_edge_gains:
        print(
            "Evolution-stage edge audit passed. "
            f"Smallest direct evolution gain: +{min(stage_edge_gains)}."
        )

    if three_stage_path_gains:
        print(
            "Three-stage spacing audit passed. "
            "Smallest base-to-final gain across audited two-step paths: "
            f"+{min(three_stage_path_gains)}."
        )


print()
print(
    f"Randomized Pokémon stat entries: "
    f"{changed_species}"
)
print(
    "Canonical Mega species randomized: "
    f"{len(randomizable_mega_species)}"
)

if MODE == "same":
    print(
        f"BST totals preserved exactly: "
        f"{same_bst_species}/{changed_species}"
    )

if MODE == "stages":
    category_counts = defaultdict(
        int
    )

    for species in randomizable_species:
        category_counts[
            categories.get(
                species,
                "single",
            )
        ] += 1

    print("Stage categories randomized:")

    for category in (
        "three_base",
        "three_middle",
        "three_final",
        "two_base",
        "two_final",
        "single",
    ):
        print(
            f"  {category}: "
            f"{category_counts[category]}"
        )

if MODE in {"stages", "full"}:
    print(
        "Mega BST pairing audit passed: every randomized Mega is exactly "
        "+100 BST over its current randomized base form."
    )

print(
    f"Protected Pokémon left unchanged: "
    f"{sum(1 for species in original_bst if species in PROTECTED_SPECIES)}"
)
print(
    f"Other temporary battle-only forms left unchanged: "
    f"{len(invalid_species - set(randomizable_mega_species))}"
)
print(
    "10%–50% per-stat guard audit passed for every randomized Pokémon."
)
print(f"Seed: {seed}")
