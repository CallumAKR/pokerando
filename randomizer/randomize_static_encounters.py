#!/usr/bin/env python3

import argparse
import json
import random
import re
from clean_map_restore import restore_static_encounters
from collections import defaultdict
from pathlib import Path

from config import PROTECTED_SPECIES
from fossil_options import CONFIG_FILE, FOSSILS

ROOT = Path(__file__).resolve().parent.parent

SPECIES_DIR = ROOT / "src/data/pokemon/species_info"

SCRIPT_DIRS = [
    ROOT / "data/maps",
    ROOT / "data/scripts",
]

TV_ROAMER_FILE = ROOT / "src/roamer.c"
FOSSIL_REVIVAL_FILE = (
    ROOT
    / "data/maps/RustboroCity_DevonCorp_2F/scripts.inc"
)

parser = argparse.ArgumentParser(
    description="Randomize scripted static Pokémon encounters."
)
parser.add_argument(
    "seed",
    nargs="?",
    type=int,
)
parser.add_argument(
    "--mode",
    choices=(
        "preserve",
        "full",
    ),
    required=True,
    help=(
        "preserve = keep legendary/special status; "
        "full = choose from the full eligible species pool"
    ),
)
args = parser.parse_args()

seed = (
    args.seed
    if args.seed is not None
    else random.randrange(2**32)
)
mode = args.mode

fossil_only_replacements = False

if CONFIG_FILE.exists():
    try:
        fossil_options = json.loads(
            CONFIG_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Could not read randomizer/fossil_options.json. Run the GUI "
            "again so it can regenerate the fossil settings."
        ) from exc

    if isinstance(fossil_options, dict):
        fossil_only_replacements = bool(
            fossil_options.get("fossil_only_replacements", False)
        )

rng = random.Random(seed)

print(f"Static encounter randomizer seed: {seed}")
print(f"Static encounter mode: {mode}")

restore_static_encounters(
    include_npc_trade_gifts=False,
)

# ------------------------------------------------------------
# SPECIES PARSING
# ------------------------------------------------------------

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

# ------------------------------------------------------------
# CLASSIFY SPECIES
# ------------------------------------------------------------

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


species_category = {}
pools = defaultdict(list)

for species, block in species_blocks.items():

    if species in {
        "SPECIES_NONE",
        "SPECIES_EGG",
    }:
        continue

    # Don't randomly generate manually protected Pokémon,
    # e.g. Sirfetch'd.
    if species in PROTECTED_SPECIES:
        continue

    if is_invalid_form(block):
        continue

    category = (
        "special"
        if is_special(block)
        else "normal"
    )

    species_category[species] = category
    pools[category].append(species)


for category in pools:
    pools[category].sort()


print()
print("Static encounter pools:")

print(
    f"  Normal: "
    f"{len(pools['normal'])}"
)

print(
    f"  Special "
    f"(Legendary/Mythical/Paradox/UB): "
    f"{len(pools['special'])}"
)

if not pools["normal"]:
    raise RuntimeError(
        "Normal species pool is empty."
    )

if not pools["special"]:
    raise RuntimeError(
        "Special species pool is empty."
    )

all_species_pool = sorted(
    pools["normal"]
    + pools["special"]
)

FOSSIL_SPECIES = {
    species
    for _, species, _ in FOSSILS
}

fossil_species_pool = sorted(
    species
    for species in FOSSIL_SPECIES
    if species in species_category
)

if fossil_only_replacements and not fossil_species_pool:
    raise RuntimeError(
        "Fossil-only replacements are enabled, but the eligible fossil-"
        "Pokémon pool is empty."
    )

# A few scripts use a compatibility alias rather than the canonical species
# entry name found in species_info.  Categorise those aliases through their
# canonical entries so preserve mode cannot treat a special encounter as an
# ordinary Pokémon.
SPECIES_CATEGORY_ALIASES = {
    "SPECIES_DEOXYS": "SPECIES_DEOXYS_NORMAL",
}


def get_species_category(species):
    canonical = SPECIES_CATEGORY_ALIASES.get(
        species,
        species,
    )

    return species_category.get(
        canonical,
        "normal",
    )


# These are the event-island encounters reached with the Eon Ticket, Aurora
# Ticket, Mystic Ticket and Old Sea Map.  Preserve mode must always treat all
# of them as special, including the compatibility-only SPECIES_DEOXYS alias.
EVENT_ISLAND_SPECIAL_SPECIES = {
    "SPECIES_LATIAS",
    "SPECIES_LATIOS",
    "SPECIES_MEW",
    "SPECIES_DEOXYS",
    "SPECIES_DEOXYS_NORMAL",
    "SPECIES_LUGIA",
    "SPECIES_HO_OH",
}

misclassified_event_species = sorted(
    species
    for species in EVENT_ISLAND_SPECIAL_SPECIES
    if get_species_category(species) != "special"
)

if misclassified_event_species:
    raise RuntimeError(
        "Event-island species were not classified as special:\n  "
        + "\n  ".join(misclassified_event_species)
    )

if not all_species_pool:
    raise RuntimeError(
        "Full static encounter species pool is empty."
    )

print(
    f"  Full eligible pool: "
    f"{len(all_species_pool)}"
)

print(
    "  Randomised fossil revival Pokémon: "
    + (
        f"fossil Pokémon only ({len(fossil_species_pool)})"
        if fossil_only_replacements
        else f"selected {mode} pool"
    )
)

# ------------------------------------------------------------
# STATIC BATTLE PARSING
# ------------------------------------------------------------

# Examples:
#
# setwildbattle SPECIES_KYOGRE, 70
# setwildbattle SPECIES_REGICE, 40
# seteventmon SPECIES_MEW, 30
#
static_battle_pattern = re.compile(
    r"\b(?:setwildbattle|seteventmon)\s+"
    r"(SPECIES_[A-Z0-9_]+)"
    r"\s*,\s*([0-9]+)"
)

fossil_revival_pattern = re.compile(
    r"Randomizer_Fossil_EventScript_SetSpecies[A-Za-z0-9_]+::"
    r"\r?\n\s*setvar\s+VAR_TEMP_1\s*,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
)

standard_fossil_revival_pattern = re.compile(
    r"\bgivemon\s+(SPECIES_[A-Z0-9_]+)\s*,\s*20\b"
)


def choose_replacement(
    original_species,
    excluded=(),
    candidates_override=None,
):

    if candidates_override is not None:
        candidates = candidates_override
    elif mode == "full":
        candidates = all_species_pool
    else:
        category = get_species_category(
            original_species
        )
        candidates = pools[category]

    # Prefer an actual change.
    alternatives = [
        species
        for species in candidates
        if (
            species != original_species
            and species not in excluded
        )
    ]

    if alternatives:
        candidates = alternatives
    else:
        non_original = [
            species
            for species in candidates
            if species != original_species
        ]

        if non_original:
            candidates = non_original

    return rng.choice(candidates)


changed_battles = 0
special_battles = 0
normal_battles = 0

file_logs = []

# ------------------------------------------------------------
# HALL-OF-FAME TELEVISION ROAMER
# ------------------------------------------------------------

tv_roamer_red_pattern = re.compile(
    r"(?P<prefix>"
    r"if\s*\(gSpecialVar_0x8004\s*==\s*0\)"
    r"[^\r\n]*\r?\n\s*"
    r"TryAddRoamer\("
    r")"
    r"(?P<species>SPECIES_[A-Z0-9_]+)"
    r"(?P<suffix>\s*,\s*(?P<level>[0-9]+)\s*\);)"
)

tv_roamer_blue_pattern = re.compile(
    r"(?P<prefix>"
    r"\belse\s*\r?\n\s*"
    r"TryAddRoamer\("
    r")"
    r"(?P<species>SPECIES_[A-Z0-9_]+)"
    r"(?P<suffix>\s*,\s*(?P<level>[0-9]+)\s*\);)"
)


def randomize_tv_roamer():
    if not TV_ROAMER_FILE.exists():
        raise RuntimeError(
            "Cannot randomize the television roamer; missing:\n"
            f"{TV_ROAMER_FILE}"
        )

    text = TV_ROAMER_FILE.read_text(
        encoding="utf-8"
    )
    red_matches = list(tv_roamer_red_pattern.finditer(text))
    blue_matches = list(tv_roamer_blue_pattern.finditer(text))

    if len(red_matches) != 1 or len(blue_matches) != 1:
        raise RuntimeError(
            "Could not safely locate both television roamer branches in "
            "src/roamer.c.\n\n"
            f"Red branches:  {len(red_matches)}\n"
            f"Blue branches: {len(blue_matches)}"
        )

    red_match = red_matches[0]
    blue_match = blue_matches[0]
    red_original = red_match.group("species")
    blue_original = blue_match.group("species")
    red_replacement = choose_replacement(red_original)
    blue_replacement = choose_replacement(
        blue_original,
        excluded={red_replacement},
    )

    replacements = [
        (
            red_match.start("species"),
            red_match.end("species"),
            red_replacement,
        ),
        (
            blue_match.start("species"),
            blue_match.end("species"),
            blue_replacement,
        ),
    ]

    for start, end, replacement in sorted(
        replacements,
        reverse=True,
    ):
        text = text[:start] + replacement + text[end:]

    TV_ROAMER_FILE.write_text(
        text,
        encoding="utf-8",
    )

    return [
        (
            red_original,
            red_replacement,
            int(red_match.group("level")),
            get_species_category(red_original),
        ),
        (
            blue_original,
            blue_replacement,
            int(blue_match.group("level")),
            get_species_category(blue_original),
        ),
    ]


tv_roamer_log = randomize_tv_roamer()

for _, _, _, category in tv_roamer_log:
    changed_battles += 1

    if category == "special":
        special_battles += 1
    else:
        normal_battles += 1

file_logs.append(
    (
        TV_ROAMER_FILE.relative_to(ROOT),
        tv_roamer_log,
    )
)

# ------------------------------------------------------------
# PROCESS SCRIPT FILES
# ------------------------------------------------------------

script_files = []

for directory in SCRIPT_DIRS:

    if not directory.exists():
        continue

    script_files.extend(
        directory.rglob("*.inc")
    )


for filepath in sorted(set(script_files)):

    text = filepath.read_text(
        encoding="utf-8"
    )

    battle_entries = [
        (
            match.group(1),
            int(match.group(2)),
            False,
        )
        for match in static_battle_pattern.finditer(text)
    ]

    is_devon_fossil_file = filepath == FOSSIL_REVIVAL_FILE
    is_all_fossil_file = (
        is_devon_fossil_file
        and "@ RANDOMIZER_ALL_FOSSILS_BEGIN" in text
    )

    if is_all_fossil_file:
        battle_entries.extend(
            (
                match.group(1),
                20,
                True,
            )
            for match in fossil_revival_pattern.finditer(text)
        )
    elif is_devon_fossil_file:
        battle_entries.extend(
            (
                match.group(1),
                20,
                True,
            )
            for match in standard_fossil_revival_pattern.finditer(text)
        )

    if not battle_entries:
        continue

    # Each original species in this file maps consistently
    # to one replacement.
    replacement_map = {}

    battle_log = []

    for original_species, level, is_fossil_revival in battle_entries:

        if original_species not in replacement_map:

            replacement_map[
                original_species
            ] = choose_replacement(
                original_species,
                candidates_override=(
                    fossil_species_pool
                    if fossil_only_replacements and is_fossil_revival
                    else None
                ),
            )

        replacement = replacement_map[
            original_species
        ]

        category = get_species_category(
            original_species
        )

        if category == "special":
            special_battles += 1
        else:
            normal_battles += 1

        changed_battles += 1

        battle_log.append(
            (
                original_species,
                replacement,
                level,
                category,
            )
        )

    # --------------------------------------------------------
    # Replace only static-encounter-owned species references
    # --------------------------------------------------------
    #
    # Keep this deliberately symmetrical with clean_map_restore.py.
    # We only own these command forms:
    #
    #   setwildbattle SPECIES_...
    #   seteventmon SPECIES_...
    #   playmoncry SPECIES_...
    #   setvar VAR_0x8004, SPECIES_...
    #   setvar VAR_TEMP_4, SPECIES_... (Southern Island)
    #
    # Other references to the same species in the script are permanent
    # game/cutscene data and must not be touched by this randomizer.
    #

    new_text = text

    for original_species, replacement in (
        replacement_map.items()
    ):

        command_patterns = (
            (
                (
                    rf"(\bsetwildbattle\s+)"
                    rf"{re.escape(original_species)}"
                    rf"(\s*,)"
                ),
                rf"\1{replacement}\2",
            ),
            (
                (
                    rf"(\bseteventmon\s+)"
                    rf"{re.escape(original_species)}"
                    rf"(\s*,)"
                ),
                rf"\1{replacement}\2",
            ),
            (
                (
                    rf"(\bplaymoncry\s+)"
                    rf"{re.escape(original_species)}"
                    rf"(\s*,)"
                ),
                rf"\1{replacement}\2",
            ),
            (
                (
                    rf"(\bsetvar\s+VAR_0x8004\s*,\s*)"
                    rf"{re.escape(original_species)}"
                    rf"\b"
                ),
                rf"\1{replacement}",
            ),
            (
                (
                    rf"(\bsetvar\s+VAR_TEMP_4\s*,\s*)"
                    rf"{re.escape(original_species)}"
                    rf"\b"
                ),
                rf"\1{replacement}",
            ),
        )

        if is_all_fossil_file:
            command_patterns += (
                (
                    (
                        rf"(\bsetvar\s+VAR_TEMP_1\s*,\s*)"
                        rf"{re.escape(original_species)}"
                        rf"\b"
                    ),
                    rf"\1{replacement}",
                ),
            )
        elif is_devon_fossil_file:
            command_patterns += (
                (
                    (
                        rf"(\bgivemon\s+)"
                        rf"{re.escape(original_species)}"
                        rf"(\s*,\s*20\b)"
                    ),
                    rf"\1{replacement}\2",
                ),
                (
                    (
                        rf"(\bbufferspeciesname\s+[^,]+\s*,\s*)"
                        rf"{re.escape(original_species)}"
                        rf"\b"
                    ),
                    rf"\1{replacement}",
                ),
                (
                    (
                        rf"(\bsetvar\s+VAR_TEMP_TRANSFERRED_SPECIES\s*,\s*)"
                        rf"{re.escape(original_species)}"
                        rf"\b"
                    ),
                    rf"\1{replacement}",
                ),
            )

        for pattern, replacement_text in command_patterns:
            new_text = re.sub(
                pattern,
                replacement_text,
                new_text,
            )

    if new_text != text:

        filepath.write_text(
            new_text,
            encoding="utf-8"
        )

        file_logs.append(
            (
                filepath.relative_to(ROOT),
                battle_log,
            )
        )

print()
print(
    f"Changed static battles: "
    f"{changed_battles}"
)

print(
    f"Normal static battles: "
    f"{normal_battles}"
)

print(
    f"Special static battles: "
    f"{special_battles}"
)

print(
    f"Changed script files: "
    f"{len(file_logs)}"
)


print(
    f"Seed: {seed}"
)
