#!/usr/bin/env python3

import argparse
import hashlib
import random
import re
import shutil
import sys

from pathlib import Path


from runtime_paths import ROOT, RANDOMIZER_DIR, BASELINE_ROOT
from config import PROTECTED_SPECIES

from clean_map_restore import (
    restore_static_encounters,
    restore_egg_gifts,
    restore_found_items,
    restore_lilycove_tm_shop,
    restore_lilycove_evolution_shop,
)

from randomizer_engine import (
    run_component as engine_run_component,
)

from build_backend import (
    build_rom,
)

from output_manager import (
    publish_rom,
)

from configure_tm_shop import (
    add_all_tms_to_lilycove_shop,
    configure_lilycove_evolution_shop,
)
from configure_tm_catalog import configure_tm_catalog
from tm_catalog_data import (
    DEFAULT_TM_CATALOG,
    TM_CATALOGS,
    TM_CATALOG_KEYS,
)

from starter_helpers import (
    apply_manual_starters,
    validate_manual_starters,
)

from rival_starter_continuity import (
    apply_rival_starter_continuity,
)

from wild_runtime_patch import (
    BST_TOLERANCE,
    remove_runtime_wild_patch,
)

from game_options import (
    apply_game_options,
)
from signature_move_compatibility import ensure_signature_moves_usable

from difficulty_options import (
    apply_trainer_difficulty,
)

from manual_customization import (
    apply_manual_fields,
    customization_summary,
    customizations_from_json,
    discover_mega_species,
    explicitly_enabled_species,
    isolate_custom_learnsets,
    learnset_groups,
    normalize_customizations,
    species_for_stat_mode,
)

from manual_customization_runtime import (
    configure_component_filter,
    reset_component_filter,
)


# ============================================================
# PATHS
# ============================================================


SPECIES_DIR = (
    ROOT / "src/data/pokemon/species_info"
)

LEARNSET_DIR = (
    ROOT / "src/data/pokemon/level_up_learnsets"
)

# P_LVL_UP_LEARNSETS = GEN_LATEST in this project,
# currently resolving to Gen 9.
ACTIVE_LEARNSET_FILE = (
    LEARNSET_DIR / "gen_9.h"
)


# ============================================================
# RANDOMIZER COMPONENTS
# ============================================================

COMPONENT_ORDER = [
    "pokemon_types",
    "pokemon_bst",
    "abilities",
    "evolutions",
    "move_types",
    "moves",
    "evolution_moves",
    "tms",
    "trade_evos",
    "trades",
    "wild",
    "statics",
    "eggs",
    "starters",
    "trainers",
    "items",
]


COMPONENT_LABELS = {
    "pokemon_types": "Pokémon types",
    "pokemon_bst": "Pokémon base stats",
    "abilities": "Abilities",
    "evolutions": "Evolutions",
    "move_types": "Move types",
    "moves": "Pokémon level-up moves",
    "evolution_moves": "Evolution-required moves",
    "tms": "TM compatibility",
    "trade_evos": "Trade evolutions",
    "trades": "NPC trades",
    "wild": "Wild Pokémon encounters",
    "statics": "Static Pokémon encounters",
    "eggs": "Gift eggs",
    "starters": "Starters",
    "trainers": "Trainer Pokémon",
    "items": "Items",
}


SCRIPT_CANDIDATES = {
    "pokemon_types": (
        "randomize_pokemon_types.py",
    ),

    "pokemon_bst": (
        "randomize_pokemon_bst.py",
    ),

    "abilities": (
        "randomize_abilities.py",
    ),

    "evolutions": (
        "randomize_evolutions.py",
    ),

    "move_types": (
        "randomize_move_types.py",
    ),

    "moves": (
        "randomize_moves.py",
    ),

    "evolution_moves": (
        "ensure_evolution_moves.py",
    ),

    "tms": (
        "randomize_tm_compatibility.py",
    ),

    "trade_evos": (
        "fix_trade_evolutions.py",
    ),

    "trades": (
        "randomize_trades.py",
    ),

    "wild": (
        "randomize_wild_encounters.py",
    ),

    "statics": (
        "randomize_static_encounters.py",
    ),

    "eggs": (
        "randomize_egg_gifts.py",
    ),

    "starters": (
        "randomize_starters.py",
    ),

    "trainers": (
        "randomize_trainer_pokemon.py",
    ),

    "items": (
        "randomize_items.py",
    ),
}


# ============================================================
# RANDOMIZER-OWNED CLEAN DATA
# ============================================================
#
# These files/directories are ALWAYS restored before a run,
# even when their corresponding randomizer is not selected.
#
# This prevents data from a previous seed leaking into a new
# partial randomization.
#
# IMPORTANT:
# data/maps and data/scripts are deliberately NOT listed here.
# They contain permanent game changes. Their randomizable
# species/item tokens are restored separately by
# clean_map_restore.py.
# ============================================================

GENERATED_WILD_ENCOUNTERS_HEADER = (
    ROOT / "src/data/wild_encounters.h"
)

TRAINERS_FILE = ROOT / "src/data/trainers.party"

RIVAL_DIFFICULTY_HEADER_PATTERN = re.compile(
    r"^===\s*(TRAINER_(?:MAY|BRENDAN)_"
    r"(?:ROUTE_103|RUSTBORO|ROUTE_110|ROUTE_119|LILYCOVE)_"
    r"(?:TREECKO|TORCHIC|MUDKIP))\s*===\s*$",
    re.MULTILINE,
)

EXPECTED_RIVAL_DIFFICULTY_PARTIES = 30

CLEAN_RESET_TARGETS = [
    Path("src/data/pokemon/species_info"),
    Path("src/data/pokemon/level_up_learnsets"),
    Path("src/data/pokemon/all_learnables.json"),
    Path("src/data/moves_info.h"),
    Path("src/data/trade.h"),
    Path("src/data/wild_encounters.json"),
    Path("src/data/heal_locations.json"),
    Path("src/data/trainers.party"),
    Path("src/starter_choose.c"),
]


# ============================================================
# PROTECTED POKÉMON REGEX
# ============================================================

SPECIES_HEADER_PATTERN = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

LEARNSET_POINTER_PATTERN = re.compile(
    r"\.levelUpLearnset\s*=\s*([A-Za-z0-9_]+)"
)

LEARNSET_BLOCK_PATTERN = re.compile(
    r"(static const struct LevelUpMove\s+"
    r"([A-Za-z0-9_]+)\[\]\s*=\s*\{\n)"
    r"(.*?)"
    r"(^\};)",
    re.MULTILINE | re.DOTALL,
)


# ============================================================
# FILE HELPERS
# ============================================================

def remove_path(path):
    if not path.exists():
        return

    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _copy_file_if_changed(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists() and source.read_bytes() == destination.read_bytes():
        return False

    shutil.copy2(source, destination)
    return True


def copy_path(source, destination):
    """Copy baseline data without touching unchanged file timestamps."""
    changed = 0

    if source.is_dir():
        for source_file in source.rglob("*"):
            if source_file.is_file():
                relative = source_file.relative_to(source)
                changed += _copy_file_if_changed(
                    source_file,
                    destination / relative,
                )
    else:
        changed += _copy_file_if_changed(source, destination)

    return changed


# ============================================================
# PROTECTED SPECIES
# ============================================================

def find_species_block(filepath, species):
    text = filepath.read_text(
        encoding="utf-8"
    )

    matches = list(
        SPECIES_HEADER_PATTERN.finditer(text)
    )

    for index, match in enumerate(matches):

        if match.group(1) != species:
            continue

        start = match.start()

        if index + 1 < len(matches):
            end = matches[index + 1].start()
        else:
            end = len(text)

        return (
            start,
            end,
            text[start:end],
        )

    return None


def save_protected_species():
    saved = {}

    print()
    print("Saving protected Pokémon...")

    if not PROTECTED_SPECIES:
        print("  None")
        return saved

    for species in sorted(PROTECTED_SPECIES):

        found = False

        for filepath in sorted(
            SPECIES_DIR.rglob("*.h")
        ):

            result = find_species_block(
                filepath,
                species,
            )

            if result is None:
                continue

            _, _, block = result

            learnset_match = (
                LEARNSET_POINTER_PATTERN.search(
                    block
                )
            )

            learnset = (
                learnset_match.group(1)
                if learnset_match
                else None
            )

            saved[species] = {
                "file": filepath.relative_to(ROOT),
                "block": block,
                "learnset": learnset,
            }

            print(
                f"  {species}"
            )

            found = True
            break

        if not found:
            raise RuntimeError(
                "Protected species not found:\n"
                f"{species}"
            )

    return saved


def find_active_learnset(symbol):
    filepath = ACTIVE_LEARNSET_FILE

    if not filepath.exists():
        raise RuntimeError(
            "Active Gen 9 learnset file missing:\n"
            f"{filepath}"
        )

    text = filepath.read_text(
        encoding="utf-8"
    )

    for match in (
        LEARNSET_BLOCK_PATTERN.finditer(text)
    ):

        if match.group(2) == symbol:

            return {
                "file": filepath.relative_to(ROOT),
                "block": match.group(0),
            }

    return None


def save_protected_learnsets(
    protected_species
):
    saved = {}

    for species, info in (
        protected_species.items()
    ):

        symbol = info["learnset"]

        if not symbol:
            continue

        if symbol in saved:
            continue

        result = find_active_learnset(
            symbol
        )

        if result is None:
            raise RuntimeError(
                "Protected Gen 9 learnset "
                f"not found: {symbol}\n"
                f"Species: {species}"
            )

        saved[symbol] = result

    return saved


def restore_protected_species(saved):
    if not saved:
        return

    print()
    print("Restoring protected Pokémon...")

    for species, info in saved.items():

        filepath = (
            ROOT / info["file"]
        )

        result = find_species_block(
            filepath,
            species,
        )

        if result is None:
            raise RuntimeError(
                "Could not restore protected "
                f"species: {species}"
            )

        start, end, _ = result

        text = filepath.read_text(
            encoding="utf-8"
        )

        text = (
            text[:start]
            + info["block"]
            + text[end:]
        )

        filepath.write_text(
            text,
            encoding="utf-8",
        )


def restore_protected_learnsets(saved):
    if not saved:
        return

    filepath = ACTIVE_LEARNSET_FILE

    text = filepath.read_text(
        encoding="utf-8"
    )

    for symbol, info in saved.items():

        found = False

        for match in list(
            LEARNSET_BLOCK_PATTERN.finditer(text)
        ):

            if match.group(2) != symbol:
                continue

            text = (
                text[:match.start()]
                + info["block"]
                + text[match.end():]
            )

            found = True
            break

        if not found:
            raise RuntimeError(
                "Could not restore protected "
                f"learnset: {symbol}"
            )

    filepath.write_text(
        text,
        encoding="utf-8",
    )


def set_rival_difficulty_class(class_name):
    """Temporarily expose every May/Brendan party as a major trainer."""

    if class_name not in {"Rival", "Leader"}:
        raise ValueError("Rival difficulty class must be Rival or Leader.")

    text = TRAINERS_FILE.read_text(encoding="utf-8")
    headers = list(RIVAL_DIFFICULTY_HEADER_PATTERN.finditer(text))

    if len(headers) != EXPECTED_RIVAL_DIFFICULTY_PARTIES:
        raise RuntimeError(
            "Expected 30 May/Brendan parties while applying major-trainer "
            f"difficulty rules, found {len(headers)}."
        )

    replacements = []

    for header in headers:
        next_header = re.search(
            r"(?m)^===\s*TRAINER_[A-Z0-9_]+\s*===\s*$",
            text[header.end():],
        )
        section_end = (
            header.end() + next_header.start()
            if next_header is not None
            else len(text)
        )
        section = text[header.end():section_end]
        class_match = re.search(
            r"(?m)^(?P<prefix>Class:\s*)(?:Rival|Leader)(?P<suffix>\s*)$",
            section,
        )

        if class_match is None:
            raise RuntimeError(
                "Could not find the Rival class line for "
                f"{header.group(1)}."
            )

        start = header.end() + class_match.start()
        end = header.end() + class_match.end()
        replacement = (
            class_match.group("prefix")
            + class_name
            + class_match.group("suffix")
        )
        replacements.append((start, end, replacement))

    new_text = text
    for start, end, replacement in reversed(replacements):
        new_text = new_text[:start] + replacement + new_text[end:]

    if new_text != text:
        TRAINERS_FILE.write_text(new_text, encoding="utf-8")

    return len(replacements)


# ============================================================
# BASELINE VALIDATION / RESTORATION
# ============================================================

def validate_baseline():
    if not BASELINE_ROOT.exists():

        raise RuntimeError(
            "Packaged randomizer baseline is missing:\n\n"
            f"{BASELINE_ROOT}\n\n"
            "During development, run:\n"
            "  python3 randomizer/prepare_baseline.py"
        )

    # One-time migration for installations whose baseline predates move-type
    # randomization. Earlier randomizer versions never changed moves_info.h, so
    # the current game copy is safe to capture before this feature first runs.
    moves_info_relative = Path("src/data/moves_info.h")
    moves_info_baseline = (
        BASELINE_ROOT / moves_info_relative
    )

    if not moves_info_baseline.exists():
        moves_info_current = (
            ROOT / moves_info_relative
        )

        if not moves_info_current.exists():
            raise RuntimeError(
                "Cannot initialize clean move-data baseline; missing:\n"
                f"{moves_info_current}"
            )

        print()
        print(
            "Updating packaged baseline for move-type randomization..."
        )

        copy_path(
            moves_info_current,
            moves_info_baseline,
        )

        print(
            "  captured clean src/data/moves_info.h"
        )

    for relative_path in CLEAN_RESET_TARGETS:

        source = (
            BASELINE_ROOT / relative_path
        )

        if not source.exists():

            raise RuntimeError(
                "Missing packaged baseline data:\n"
                f"{source}"
            )

    for reference_path in (
        Path("data/maps"),
        Path("data/scripts"),
    ):

        source = (
            BASELINE_ROOT / reference_path
        )

        if not source.exists():

            raise RuntimeError(
                "Missing packaged map/script "
                "reference data:\n"
                f"{source}"
            )


def invalidate_generated_wild_encounters_header():
    """
    Force Expansion to regenerate src/data/wild_encounters.h from the current
    src/data/wild_encounters.json.

    This is required because baseline restoration uses shutil.copy2(), which
    preserves the baseline file timestamp. If a previously generated
    wild_encounters.h is newer than the restored clean JSON, make can consider
    the generated header up to date even though it contains encounter data from
    an older randomizer mode/run.
    """
    if GENERATED_WILD_ENCOUNTERS_HEADER.exists():
        GENERATED_WILD_ENCOUNTERS_HEADER.unlink()
        print(
            "  removed stale generated src\\data\\wild_encounters.h"
        )
        return True

    print(
        "  generated src\\data\\wild_encounters.h already absent"
    )
    return False


def restore_clean_source():
    print()
    print(
        "Restoring packaged clean randomizable data..."
    )
    print()

    for relative_path in CLEAN_RESET_TARGETS:

        source = (
            BASELINE_ROOT / relative_path
        )

        destination = (
            ROOT / relative_path
        )

        print(
            f"  {relative_path}"
        )

        changed = copy_path(
            source,
            destination,
        )

        if changed:
            print(f"    restored {changed} changed file(s)")
        else:
            print("    unchanged")

    print()
    print("Refreshing generated wild encounter data...")
    invalidate_generated_wild_encounters_header()


def restore_clean_map_randomizer_data():
    print()
    print(
        "Restoring clean map randomizer values..."
    )
    print()

    # These functions restore only the exact randomized tokens
    # they own. Whole map/script files are never replaced.

    restore_static_encounters()
    restore_egg_gifts()
    restore_found_items()
    restore_lilycove_tm_shop()
    restore_lilycove_evolution_shop()


# ============================================================
# SCRIPT LOOKUP
# ============================================================

def resolve_script(component):
    candidates = (
        SCRIPT_CANDIDATES[component]
    )

    for filename in candidates:

        path = (
            RANDOMIZER_DIR / filename
        )

        if path.exists():
            return path

    raise RuntimeError(
        "No script found for component "
        f"'{component}'. Tried:\n"
        + "\n".join(
            f"  {filename}"
            for filename in candidates
        )
    )


# ============================================================
# RUN COMPONENT
# ============================================================

def run_component(
    component,
    seed,
    pokemon_bst_mode=None,
    wild_mode=None,
    wild_allow_special=False,
    wild_similar_bst=False,
    static_mode=None,
    trainer_mode=None,
    trainer_allow_special=False,
    trainer_similar_bst=False,
    trainer_force_six_major=False,
    trainer_type_themes=False,
    move_species_specific=False,
    move_same_type_bias=False,
    include_game_corner=False,
    starter_three_stage_base=False,
):
    """
    Run one randomizer through the in-process execution engine.

    The legacy scripts still receive the same seed / --mode arguments they
    previously received from subprocess calls, but no child Python process is
    created. This is the compatibility bridge toward the standalone GUI/EXE.
    """

    return engine_run_component(
        component,
        seed,
        log_stream=None,
        pokemon_bst_mode=pokemon_bst_mode,
        wild_mode=wild_mode,
        wild_allow_special=wild_allow_special,
        wild_similar_bst=wild_similar_bst,
        static_mode=static_mode,
        trainer_mode=trainer_mode,
        trainer_allow_special=trainer_allow_special,
        trainer_similar_bst=trainer_similar_bst,
        trainer_force_six_major=trainer_force_six_major,
        trainer_type_themes=trainer_type_themes,
        move_species_specific=move_species_specific,
        move_same_type_bias=move_same_type_bias,
        include_game_corner=include_game_corner,
        starter_three_stage_base=starter_three_stage_base,
        output_stream=sys.stdout,
    )


# ============================================================
# MASTER RANDOMIZATION
# ============================================================

def randomize(
    seed,
    selected_components,
    pokemon_bst_mode=None,
    wild_mode=None,
    wild_allow_special=False,
    wild_similar_bst=False,
    static_mode=None,
    trainer_mode=None,
    trainer_allow_special=False,
    trainer_similar_bst=False,
    trainer_force_six_major=False,
    trainer_type_themes=False,
    move_species_specific=False,
    move_same_type_bias=False,
    do_build=False,
    clean_build=False,
    add_all_tms=False,
    tm_catalog_generation=DEFAULT_TM_CATALOG,
    add_evolution_items=False,
    add_regional_postcards=False,
    add_mega_stones=False,
    include_game_corner=False,
    game_permadeath=False,
    # Compatibility alias for the first Game Options build. It enables all
    # three optional received items.
    game_field_items=False,
    game_hm_free=False,
    game_hm_progression_bypass=False,
    game_perma_repel=False,
    game_cap_candy=False,
    game_mom_bonus=False,
    game_party_heal=False,
    game_time_turner=False,
    game_weather_setter=False,
    game_always_catch=False,
    game_force_shiny=False,
    game_permanent_megas=False,
    game_regional_evolutions=False,
    game_level_caps=False,
    game_always_mirage_island=False,
    difficulty_ai_mode=None,
    difficulty_level_boost=0,
    difficulty_level_scope="all",
    difficulty_iv_mode=None,
    difficulty_competitive_builds=False,
    difficulty_movesets=False,
    difficulty_held_items=False,
    difficulty_trainer_items=False,
    difficulty_force_set=False,
    difficulty_disable_bag=False,
    starter_three_stage_base=False,
    manual_starters=None,
    manual_customizations=None,
):
    validate_baseline()

    # Signature moves stay in the random pool. Remove their species-only
    # battle failures (and AI penalties) before any source is compiled.
    ensure_signature_moves_usable()

    manual_customizations = normalize_customizations(
        manual_customizations
    )

    invalid = (
        set(selected_components)
        - set(COMPONENT_ORDER)
    )

    if invalid:
        raise RuntimeError(
            "Unknown components: "
            + ", ".join(
                sorted(invalid)
            )
        )

    selected_components = [
        component
        for component in COMPONENT_ORDER
        if component in selected_components
    ]

    manual_starters = validate_manual_starters(
        manual_starters
    )

    if (
        manual_starters is not None
        and "starters" in selected_components
    ):
        raise RuntimeError(
            "Randomized starters and manually selected starters "
            "cannot both be enabled."
        )

    if (
        starter_three_stage_base
        and "starters" not in selected_components
    ):
        raise RuntimeError(
            "The three-stage starter restriction requires randomized starters."
        )

    if (
        trainer_force_six_major
        and "trainers" not in selected_components
    ):
        raise RuntimeError(
            "The six-Pokémon major-trainer option requires trainer "
            "Pokémon randomization."
        )

    if (
        trainer_type_themes
        and "trainers" not in selected_components
    ):
        raise RuntimeError(
            "The Gym / Elite Four type-theme option requires trainer "
            "Pokémon randomization."
        )

    if (
        move_species_specific
        and "moves" not in selected_components
    ):
        raise RuntimeError(
            "Species-specific move pools require level-up move randomization."
        )

    if (
        move_same_type_bias
        and "moves" not in selected_components
    ):
        raise RuntimeError(
            "Same-type move bias requires level-up move randomization."
        )

    if difficulty_ai_mode not in {None, "fair", "omniscient"}:
        raise RuntimeError(
            "Difficulty AI mode must be 'fair', 'omniscient', or disabled."
        )

    if difficulty_level_scope not in {"all", "major"}:
        raise RuntimeError(
            "Trainer level-boost scope must be 'all' or 'major'."
        )

    if not 0 <= int(difficulty_level_boost) <= 20:
        raise RuntimeError(
            "Trainer level boost must be between 0 and 20."
        )

    if difficulty_iv_mode not in {None, "scaled", "perfect"}:
        raise RuntimeError(
            "Difficulty IV mode must be 'scaled', 'perfect', or disabled."
        )

    if add_all_tms and tm_catalog_generation not in TM_CATALOGS:
        raise RuntimeError(
            "A valid TM catalogue generation is required when the "
            "Lilycove TM option is enabled."
        )

    # --------------------------------------------------------
    # REQUIRED MODE VALIDATION
    # --------------------------------------------------------

    if "pokemon_bst" in selected_components:

        if pokemon_bst_mode not in {
            "same",
            "stages",
            "full",
        }:

            raise RuntimeError(
                "Pokémon BST is selected, but no valid BST mode was supplied."
            )

    if "wild" in selected_components:

        if wild_mode not in {
            "mapping",
            "slots",
            "runtime",
        }:

            raise RuntimeError(
                "Wild encounters are selected, "
                "but no valid wild mode was supplied."
            )

    if "statics" in selected_components:

        if static_mode not in {
            "preserve",
            "full",
        }:

            raise RuntimeError(
                "Static encounters are selected, "
                "but no valid static encounter mode was supplied."
            )

    if "trainers" in selected_components:

        if trainer_mode not in {
            "mapping",
            "full",
        }:

            raise RuntimeError(
                "Trainers are selected, "
                "but no valid trainer mode was supplied."
            )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "POKEEMERALD MASTER RANDOMIZER"
    )
    print("=" * 70)

    print()
    print(
        f"Seed: {seed}"
    )

    print()
    print(
        "Selected components:"
    )

    if selected_components:

        for component in selected_components:

            extra = ""

            if component == "pokemon_bst":
                bst_labels = {
                    "same": "same BST",
                    "stages": "evolution-stage ranges",
                    "full": "fully random BST",
                }

                extra = (
                    " ["
                    + bst_labels.get(
                        pokemon_bst_mode,
                        str(pokemon_bst_mode),
                    )
                    + "]"
                )

            elif component == "wild":
                extra = (
                    f" [{wild_mode}]"
                )

            elif component == "statics":
                extra = (
                    f" [{static_mode}]"
                )

            elif component == "moves":
                rules = []

                if move_species_specific:
                    rules.append(
                        "species-specific pools"
                    )

                if move_same_type_bias:
                    rules.append(
                        "same-type bias"
                    )

                if rules:
                    extra = (
                        " ["
                        + ", ".join(rules)
                        + "]"
                    )

            elif component == "trainers":
                rules = []

                if trainer_allow_special:
                    rules.append("special")

                if trainer_similar_bst:
                    rules.append(
                        f"±{BST_TOLERANCE} BST"
                    )

                if trainer_force_six_major:
                    rules.append(
                        "6-Pokémon major trainers"
                    )

                if trainer_type_themes:
                    rules.append(
                        "Gym/E4 type themes"
                    )

                rule_text = (
                    "; " + ", ".join(rules)
                    if rules
                    else ""
                )

                extra = (
                    f" [{trainer_mode}{rule_text}]"
                )

            elif (
                component == "starters"
                and starter_three_stage_base
            ):
                extra = " [three-stage base only]"

            print(
                "  ✓ "
                + COMPONENT_LABELS[
                    component
                ]
                + extra
            )

    if manual_starters is not None:
        print("  ✓ Manual starters")

    if manual_customizations:
        print(
            "  ✓ Manual Pokémon customisation "
            f"({len(manual_customizations)} Pokémon)"
        )

    if (
        not selected_components
        and manual_starters is None
        and not manual_customizations
    ):
        print("  None")

    if manual_customizations:
        print()
        print("Customised Pokémon:")
        for species, entry in sorted(manual_customizations.items()):
            print(f"  {species}: {customization_summary(entry)}")

    print()
    print("Game options:")

    effective_perma_repel = bool(
        game_perma_repel
        or game_field_items
    )
    effective_cap_candy = bool(
        game_cap_candy
        or game_field_items
    )
    effective_party_heal = bool(
        game_party_heal
        or game_field_items
    )

    game_option_labels = [
        label
        for enabled, label in (
            (
                game_hm_progression_bypass,
                "Disable progression requirements to use HMs",
            ),
            (
                game_hm_free,
                "HM use without teaching moves and HM field tools",
            ),
            (effective_perma_repel, "Receive Perma Repel"),
            (effective_cap_candy, "Level to cap party action"),
            (game_mom_bonus, "Mom's Running Shoes bonus"),
            (effective_party_heal, "Receive Party Heal"),
            (game_time_turner, "Receive Time Turner"),
            (game_weather_setter, "Receive Weather Setter"),
            (game_always_catch, "100% catch rate"),
            (game_permadeath, "Permanent death"),
            (game_force_shiny, "Force all Pokémon shiny"),
            (game_permanent_megas, "Permanent Mega Evolutions"),
            (
                game_regional_evolutions,
                "Regional evolution postcards",
            ),
            (game_level_caps, "Level caps"),
            (
                game_always_mirage_island,
                "Mirage Island always present",
            ),
        )
        if enabled
    ]

    if game_option_labels:
        for label in game_option_labels:
            print("  ✓ " + label)
    else:
        print("  None")

    print()
    print("Difficulty options:")

    difficulty_labels = []

    if difficulty_ai_mode:
        difficulty_labels.append(
            "Trainer AI: "
            + (
                "fair smart AI"
                if difficulty_ai_mode == "fair"
                else "omniscient AI"
            )
        )

    if difficulty_level_boost:
        difficulty_labels.append(
            f"Trainer levels +{difficulty_level_boost} "
            f"({difficulty_level_scope})"
        )

    if difficulty_iv_mode:
        difficulty_labels.append(
            "Trainer IVs: "
            + (
                "scaled with progress"
                if difficulty_iv_mode == "scaled"
                else "perfect"
            )
        )

    difficulty_labels.extend(
        label
        for enabled, label in (
            (
                difficulty_competitive_builds,
                "Major trainers use competitive EVs/natures",
            ),
            (difficulty_movesets, "Improved trainer movesets"),
            (difficulty_held_items, "Major trainers receive held items"),
            (difficulty_trainer_items, "Major trainers receive healing items"),
            (difficulty_force_set, "Force Set battle style"),
            (difficulty_disable_bag, "Disable Bag items in trainer battles"),
        )
        if enabled
    )

    if difficulty_labels:
        for label in difficulty_labels:
            print("  ✓ " + label)
    else:
        print("  None")

    print()
    print("Store options:")

    store_labels = []

    if add_all_tms:
        store_labels.append(
            "Lilycove TM catalogue: "
            + TM_CATALOGS[tm_catalog_generation]["label"]
        )

    if add_evolution_items:
        store_labels.append("All evolution items in Lilycove")

    if add_regional_postcards:
        store_labels.append("Regional postcards in Lilycove")

    if add_mega_stones:
        store_labels.append("All Mega Stones in Lilycove")

    if store_labels:
        for label in store_labels:
            print("  ✓ " + label)
    else:
        print("  None")

    # --------------------------------------------------------
    # PROTECT CUSTOM POKÉMON BEFORE BASELINE RESTORE
    # --------------------------------------------------------

    protected_species = (
        save_protected_species()
    )

    protected_learnsets = (
        save_protected_learnsets(
            protected_species
        )
    )

    # --------------------------------------------------------
    # ALWAYS RESET ALL RANDOMIZABLE DATA
    # --------------------------------------------------------

    restore_clean_source()

    if remove_runtime_wild_patch():
        print(
            "Removed previous runtime wild encounter hook."
        )

    restore_clean_map_randomizer_data()

    # --------------------------------------------------------
    # RESTORE PROTECTED POKÉMON
    # --------------------------------------------------------

    restore_protected_species(
        protected_species
    )

    restore_protected_learnsets(
        protected_learnsets
    )

    # --------------------------------------------------------
    # OPTIONAL GAMEPLAY OPTIONS
    # --------------------------------------------------------

    # Always write the generated config, even when every option is OFF.
    # This prevents a setting from a previous ROM build leaking into the
    # next one.
    apply_game_options(
        permadeath=game_permadeath,
        hm_free_field_moves=game_hm_free,
        hm_progression_bypass=game_hm_progression_bypass,
        perma_repel=effective_perma_repel,
        cap_candy=effective_cap_candy,
        mom_bonus=game_mom_bonus,
        party_heal=effective_party_heal,
        time_turner=game_time_turner,
        weather_setter=game_weather_setter,
        always_catch=game_always_catch,
        force_shiny=game_force_shiny,
        permanent_megas=game_permanent_megas,
        regional_evolution_postcards=game_regional_evolutions,
        level_caps=game_level_caps,
        always_mirage_island=game_always_mirage_island,
        force_set_battle_style=difficulty_force_set,
        disable_bag_in_trainer_battles=difficulty_disable_bag,
    )

    # Always restore the ordinary Emerald TM catalogue when this option is
    # disabled, so a later-generation selection cannot leak between runs.
    effective_tm_catalog = (
        tm_catalog_generation
        if add_all_tms
        else DEFAULT_TM_CATALOG
    )
    configure_tm_catalog(effective_tm_catalog)

    if add_all_tms:
        add_all_tms_to_lilycove_shop()

    if (
        add_evolution_items
        or add_regional_postcards
        or add_mega_stones
    ):
        configure_lilycove_evolution_shop(
            add_evolution_items=add_evolution_items,
            add_regional_postcards=add_regional_postcards,
            add_mega_stones=add_mega_stones,
        )

    if manual_starters is not None:
        apply_manual_starters(
            manual_starters
        )

    # Custom species receive private learnset tables before any move-related
    # component. This prevents a form or family member that shares a table
    # from being changed as an unintended side effect.
    needs_custom_learnset_isolation = (
        "moves" in selected_components
        or "evolution_moves" in selected_components
        or any(
            entry["randomize"].get("learnset")
            or entry["randomize"].get("evolution_moves")
            for entry in manual_customizations.values()
        )
    )

    if needs_custom_learnset_isolation:
        isolate_custom_learnsets(
            manual_customizations
        )

    # --------------------------------------------------------
    # RUN ONLY SELECTED RANDOMIZERS
    # --------------------------------------------------------

    customized_species = set(
        manual_customizations
    )

    def derived_seed(label):
        digest = hashlib.sha256(
            f"{seed}:{label}".encode("utf-8")
        ).digest()
        return int.from_bytes(digest[:4], "big")

    def invoke_component(
        component,
        *,
        component_seed=None,
        bst_mode_override=None,
        move_options_override=None,
    ):
        chosen_move_options = (
            move_options_override
            if move_options_override is not None
            else (
                move_species_specific,
                move_same_type_bias,
            )
        )

        run_component(
            component,
            seed if component_seed is None else component_seed,
            pokemon_bst_mode=(
                (
                    bst_mode_override
                    if bst_mode_override is not None
                    else pokemon_bst_mode
                )
                if component == "pokemon_bst"
                else None
            ),
            wild_mode=wild_mode,
            wild_allow_special=wild_allow_special,
            wild_similar_bst=wild_similar_bst,
            static_mode=static_mode,
            trainer_mode=trainer_mode,
            trainer_allow_special=(
                trainer_allow_special
                if component == "trainers"
                else False
            ),
            trainer_similar_bst=(
                trainer_similar_bst
                if component == "trainers"
                else False
            ),
            trainer_force_six_major=(
                trainer_force_six_major
                if component == "trainers"
                else False
            ),
            trainer_type_themes=(
                trainer_type_themes
                if component == "trainers"
                else False
            ),
            move_species_specific=(
                chosen_move_options[0]
                if component == "moves"
                else False
            ),
            move_same_type_bias=(
                chosen_move_options[1]
                if component == "moves"
                else False
            ),
            include_game_corner=(
                include_game_corner
                if component == "items"
                else False
            ),
            starter_three_stage_base=(
                starter_three_stage_base
                if component == "starters"
                else False
            ),
        )

    def run_filtered(
        component,
        *,
        global_enabled,
        explicit_species=(),
        component_seed=None,
        bst_mode_override=None,
        move_options_override=None,
    ):
        configure_component_filter(
            customized_species=customized_species,
            explicitly_enabled_species=explicit_species,
            global_enabled=global_enabled,
        )
        try:
            invoke_component(
                component,
                component_seed=component_seed,
                bst_mode_override=bst_mode_override,
                move_options_override=move_options_override,
            )
        finally:
            reset_component_filter()

    represented_keys = {
        "pokemon_types": "types",
        "abilities": "abilities",
        "evolutions": "evolutions",
        "evolution_moves": "evolution_moves",
        "tms": "tm_compatibility",
        "trade_evos": "trade_evolutions",
    }

    for component in COMPONENT_ORDER:
        globally_selected = component in selected_components

        if component == "pokemon_types":
            explicit = explicitly_enabled_species(
                manual_customizations,
                "types",
            )
            if globally_selected or explicit:
                run_filtered(
                    component,
                    global_enabled=globally_selected,
                    explicit_species=explicit,
                )
            apply_manual_fields(
                manual_customizations,
                "types",
            )
            continue

        if component == "pokemon_bst":
            mega_species = discover_mega_species()
            manual_stat_species = {
                species
                for species, entry in manual_customizations.items()
                if entry["manual"]["stats"] is not None
            }

            # Fixed manual base-form stats must exist before the global pass so
            # a globally randomized Mega can derive its required +100 total.
            apply_manual_fields(
                manual_customizations,
                "stats",
                species_subset=manual_stat_species - mega_species,
            )

            for mode in ("same", "stages", "full"):
                group = (
                    species_for_stat_mode(manual_customizations, mode)
                    - mega_species
                )
                if group:
                    run_filtered(
                        component,
                        global_enabled=False,
                        explicit_species=group,
                        component_seed=derived_seed(f"custom-bst-{mode}-base"),
                        bst_mode_override=mode,
                    )

            if globally_selected:
                run_filtered(
                    component,
                    global_enabled=True,
                    explicit_species=(),
                    bst_mode_override=pokemon_bst_mode,
                )

            # Custom Mega totals are chosen after base forms have reached their
            # final values, preserving the +100 rule in stages/full modes.
            for mode in ("same", "stages", "full"):
                group = (
                    species_for_stat_mode(manual_customizations, mode)
                    & mega_species
                )
                if group:
                    run_filtered(
                        component,
                        global_enabled=False,
                        explicit_species=group,
                        component_seed=derived_seed(f"custom-bst-{mode}-mega"),
                        bst_mode_override=mode,
                    )

            apply_manual_fields(
                manual_customizations,
                "stats",
                species_subset=manual_stat_species & mega_species,
            )
            continue

        if component == "abilities":
            explicit = explicitly_enabled_species(
                manual_customizations,
                "abilities",
            )
            if globally_selected or explicit:
                run_filtered(
                    component,
                    global_enabled=globally_selected,
                    explicit_species=explicit,
                )
            apply_manual_fields(
                manual_customizations,
                "abilities",
            )
            continue

        if component == "moves":
            if globally_selected:
                run_filtered(
                    component,
                    global_enabled=True,
                    explicit_species=(),
                )

            for options, group in sorted(learnset_groups(manual_customizations).items()):
                run_filtered(
                    component,
                    global_enabled=False,
                    explicit_species=group,
                    component_seed=derived_seed(
                        "custom-moves-"
                        + "-".join("1" if value else "0" for value in options)
                    ),
                    move_options_override=options,
                )
            continue

        if component in represented_keys:
            explicit = explicitly_enabled_species(
                manual_customizations,
                represented_keys[component],
            )
            if globally_selected or explicit:
                run_filtered(
                    component,
                    global_enabled=globally_selected,
                    explicit_species=explicit,
                )
            continue

        # Move types and all placement/game systems are intentionally outside
        # the Manual Customisation protection boundary.
        if globally_selected:
            reset_component_filter()
            invoke_component(component)

    reset_component_filter()

    # --------------------------------------------------------
    # FINAL PROTECTION PASS
    # --------------------------------------------------------

    restore_protected_species(
        protected_species
    )

    restore_protected_learnsets(
        protected_learnsets
    )

    # Starter and trainer randomisation have both reached their final species
    # state now. Apply continuity before the difficulty pass so the rival's
    # IVs, EVs, nature, moveset, ability and held item are all generated for
    # the actual continuous starter rather than the original Emerald starter.
    apply_rival_starter_continuity()

    rival_party_count = set_rival_difficulty_class("Leader")
    print(
        "  Rival parties treated as major trainers for difficulty: "
        f"{rival_party_count}"
    )

    try:
        apply_trainer_difficulty(
            seed=derived_seed("trainer-difficulty"),
            ai_mode=difficulty_ai_mode,
            level_boost=int(difficulty_level_boost),
            level_scope=difficulty_level_scope,
            iv_mode=difficulty_iv_mode,
            competitive_builds=difficulty_competitive_builds,
            improved_movesets=difficulty_movesets,
            held_items=difficulty_held_items,
            trainer_items=difficulty_trainer_items,
        )
    finally:
        set_rival_difficulty_class("Rival")

    print()
    print("=" * 70)
    print(
        "RANDOMIZATION COMPLETE"
    )
    print("=" * 70)

    print()
    print(
        f"Seed: {seed}"
    )

    if do_build:
        built_rom = build_rom(clean=clean_build)

        published_rom = publish_rom(
            built_rom,
            seed,
        )

        print()
        print(
            f"Published ROM: {published_rom}"
        )

    return published_rom if do_build else None


# ============================================================
# CLI HELPERS
# ============================================================

def parse_component_list(value):
    if not value:
        return []

    return [
        part.strip()
        for part in value.split(",")
        if part.strip()
    ]


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description=(
            "pokeemerald-expansion "
            "master randomizer"
        )
    )

    parser.add_argument(
        "seed",
        nargs="?",
        type=int,
        help=(
            "Optional seed. A random seed "
            "is generated if omitted."
        ),
    )

    parser.add_argument(
        "--components",
        default=None,
        help=(
            "Comma-separated components. "
            "Example: starters,wild,trainers"
        ),
    )

    parser.add_argument(
        "--exclude",
        default="",
        help=(
            "Comma-separated components "
            "to exclude."
        ),
    )

    parser.add_argument(
        "--pokemon-bst-mode",
        choices=[
            "same",
            "stages",
            "full",
        ],
        default=None,
        help=(
            "Required when pokemon_bst is selected: "
            "same, stages, or full."
        ),
    )

    parser.add_argument(
        "--wild-mode",
        choices=[
            "mapping",
            "slots",
            "runtime",
        ],
        default=None,
        help=(
            "Required when wild encounters "
            "are selected."
        ),
    )

    parser.add_argument(
        "--wild-allow-special",
        action="store_true",
        help=(
            "Allow Legendary/Mythical/Ultra Beast/Paradox Pokemon "
            "in the wild replacement pool."
        ),
    )

    parser.add_argument(
        "--wild-similar-bst",
        action="store_true",
        help=(
            f"Keep wild replacement Pokemon within ±{BST_TOLERANCE} BST "
            "of the original."
        ),
    )

    parser.add_argument(
        "--static-mode",
        choices=[
            "preserve",
            "full",
        ],
        default=None,
        help=(
            "Required when static encounters are selected. "
            "'preserve' keeps legendary/special status; "
            "'full' uses the full eligible species pool."
        ),
    )

    parser.add_argument(
        "--move-species-specific-pools",
        action="store_true",
        help=(
            "Restrict randomized level-up moves to each species' "
            "own learnable-move pool."
        ),
    )

    parser.add_argument(
        "--move-same-type-bias",
        action="store_true",
        help=(
            "Bias randomized level-up moves toward moves matching "
            "the species' own type."
        ),
    )

    parser.add_argument(
        "--trainer-mode",
        choices=[
            "mapping",
            "full",
        ],
        default=None,
        help=(
            "Required when trainers "
            "are selected."
        ),
    )

    parser.add_argument(
        "--trainer-allow-special",
        action="store_true",
        help=(
            "Allow Legendary/Mythical/Ultra Beast/Paradox Pokemon "
            "in the trainer replacement pool."
        ),
    )

    parser.add_argument(
        "--trainer-similar-bst",
        action="store_true",
        help=(
            f"Keep trainer replacement Pokemon within ±{BST_TOLERANCE} BST "
            "of the original."
        ),
    )

    parser.add_argument(
        "--trainer-force-six-major",
        action="store_true",
        help=(
            "Expand Gym Leader, Elite Four and Champion trainer parties "
            "to six Pokemon."
        ),
    )

    parser.add_argument(
        "--trainer-type-themes",
        action="store_true",
        help=(
            "Give each Hoenn Gym and Elite Four member a randomized "
            "type theme."
        ),
    )

    parser.add_argument(
        "--include-game-corner",
        action="store_true",
        help="Include Game Corner item prizes in item randomization.",
    )

    parser.add_argument(
        "--starter-three-stage-base",
        action="store_true",
        help=(
            "When starters are randomized, restrict them to base Pokémon "
            "that have a three-stage evolution path."
        ),
    )

    parser.add_argument(
        "--permadeath",
        action="store_true",
        help="Enable permanent death.",
    )

    parser.add_argument(
        "--field-items",
        action="store_true",
        help=(
            "Compatibility option that gives Perma Repel and Party Heal "
            "and enables the Level to cap party action."
        ),
    )

    parser.add_argument(
        "--hm-free-field-moves",
        action="store_true",
        help=(
            "Enable direct HM field interactions without learned moves and "
            "give the custom support/HM field tools."
        ),
    )

    parser.add_argument(
        "--remove-hm-progression-requirements",
        action="store_true",
        help=(
            "Allow HM field actions and tools regardless of badge/story "
            "progression."
        ),
    )

    parser.add_argument(
        "--perma-repel",
        action="store_true",
        help="Enable and give the Perma Repel key item.",
    )

    parser.add_argument(
        "--cap-candy",
        action="store_true",
        help="Enable Level to cap in the Pokémon party menu.",
    )

    parser.add_argument(
        "--mom-bonus",
        action="store_true",
        help="Mom gives 99 Ultra Balls and maximum money with the Running Shoes.",
    )

    parser.add_argument(
        "--party-heal",
        action="store_true",
        help="Give the Party Restorer key item.",
    )

    parser.add_argument(
        "--time-turner",
        action="store_true",
        help="Give the reusable Day/Evening/Night Time Turner key item.",
    )

    parser.add_argument(
        "--weather-setter",
        action="store_true",
        help="Give the reusable overworld Weather Setter key item.",
    )

    parser.add_argument(
        "--always-catch",
        action="store_true",
        help="Make valid wild Pokémon captures guaranteed.",
    )

    parser.add_argument(
        "--force-shiny",
        action="store_true",
        help="Force all Pokémon to report as shiny.",
    )

    parser.add_argument(
        "--permanent-megas",
        action="store_true",
        help=(
            "Make Mega Stones consumable party-menu evolution items that "
            "produce permanent Mega species."
        ),
    )

    parser.add_argument(
        "--regional-evolution-postcards",
        action="store_true",
        help=(
            "Let held regional postcards satisfy regional evolution "
            "requirements and make both Ursaluna forms obtainable."
        ),
    )

    parser.add_argument(
        "--level-caps",
        action="store_true",
        help=(
            "Enable the project's existing hard badge/story level caps."
        ),
    )

    parser.add_argument(
        "--always-mirage-island",
        action="store_true",
        help="Make Mirage Island remain present every day.",
    )

    parser.add_argument(
        "--difficulty-ai",
        choices=["fair", "omniscient"],
        default=None,
        help="Upgrade every trainer to fair smart AI or omniscient AI.",
    )

    parser.add_argument(
        "--trainer-level-boost",
        type=int,
        choices=range(0, 21),
        default=0,
        metavar="0-20",
        help="Add this many levels to affected trainer Pokémon.",
    )

    parser.add_argument(
        "--trainer-level-scope",
        choices=["all", "major"],
        default="all",
        help="Apply the level boost to all trainers or major trainers only.",
    )

    parser.add_argument(
        "--trainer-ivs",
        choices=["scaled", "perfect"],
        default=None,
        help="Scale trainer IVs with progress or set every trainer IV to 31.",
    )

    parser.add_argument(
        "--competitive-major-builds",
        action="store_true",
        help="Give major trainers role-appropriate EVs and natures.",
    )

    parser.add_argument(
        "--improved-trainer-movesets",
        action="store_true",
        help="Generate role-appropriate legal movesets for trainer Pokémon.",
    )

    parser.add_argument(
        "--major-trainer-held-items",
        action="store_true",
        help="Give major-trainer Pokémon role-appropriate held items.",
    )

    parser.add_argument(
        "--major-trainer-healing-items",
        action="store_true",
        help="Give Gym Leaders, Elite Four and Champion healing items.",
    )

    parser.add_argument(
        "--force-set-battle-style",
        action="store_true",
        help="Force Set battle style during trainer battles.",
    )

    parser.add_argument(
        "--disable-bag-in-trainer-battles",
        action="store_true",
        help="Prevent the player from using Bag items in trainer battles.",
    )

    parser.add_argument(
        "--build",
        action="store_true",
        help="Build the ROM after randomization.",
    )

    parser.add_argument(
        "--clean-build",
        action="store_true",
        help="Force make clean before building the ROM.",
    )

    parser.add_argument(
        "--all-tms-lilycove",
        action="store_true",
        help="Add the selected generation's TMs to Lilycove 4F.",
    )

    parser.add_argument(
        "--tm-catalog-generation",
        choices=TM_CATALOG_KEYS,
        default=DEFAULT_TM_CATALOG,
        help=(
            "TM catalogue used by --all-tms-lilycove "
            "(gen1 through gen8; default: gen3)."
        ),
    )

    parser.add_argument(
        "--evolution-items-lilycove",
        action="store_true",
        help=(
            "Add all non-Mega evolution items, including stones and "
            "trade-evolution items, to Lilycove 2F."
        ),
    )

    parser.add_argument(
        "--regional-postcards-lilycove",
        action="store_true",
        help=(
            "Add the Alola, Galar and Hisui evolution postcards to "
            "Lilycove 2F."
        ),
    )

    parser.add_argument(
        "--mega-stones-lilycove",
        action="store_true",
        help="Add all Mega Stones to Lilycove 2F.",
    )

    parser.add_argument(
        "--manual-customizations",
        default=None,
        help=(
            "Optional JSON file containing per-Pokémon Manual "
            "Customisation settings."
        ),
    )

    args = parser.parse_args()

    manual_customizations = (
        customizations_from_json(args.manual_customizations)
        if args.manual_customizations
        else None
    )

    seed = (
        args.seed
        if args.seed is not None
        else random.randrange(2**32)
    )

    if args.components is None:

        selected = set(
            COMPONENT_ORDER
        )

    else:

        selected = set(
            parse_component_list(
                args.components
            )
        )

    excluded = set(
        parse_component_list(
            args.exclude
        )
    )

    selected -= excluded

    if (
        "pokemon_bst" in selected
        and args.pokemon_bst_mode is None
    ):

        parser.error(
            "Pokémon BST is selected. "
            "Specify --pokemon-bst-mode same, "
            "--pokemon-bst-mode stages, or "
            "--pokemon-bst-mode full."
        )

    if (
        "wild" in selected
        and args.wild_mode is None
    ):

        parser.error(
            "Wild encounters are selected. "
            "Specify --wild-mode mapping, "
            "--wild-mode slots, or "
            "--wild-mode runtime."
        )

    if (
        "statics" in selected
        and args.static_mode is None
    ):

        parser.error(
            "Static encounters are selected. "
            "Specify --static-mode preserve "
            "or --static-mode full."
        )

    if (
        "trainers" in selected
        and args.trainer_mode is None
    ):

        parser.error(
            "Trainers are selected. "
            "Specify --trainer-mode mapping "
            "or --trainer-mode full."
        )

    try:

        randomize(
            seed,
            selected,
            pokemon_bst_mode=args.pokemon_bst_mode,
            wild_mode=args.wild_mode,
            wild_allow_special=args.wild_allow_special,
            wild_similar_bst=args.wild_similar_bst,
            static_mode=args.static_mode,
            trainer_mode=args.trainer_mode,
            trainer_allow_special=args.trainer_allow_special,
            trainer_similar_bst=args.trainer_similar_bst,
            trainer_force_six_major=args.trainer_force_six_major,
            trainer_type_themes=args.trainer_type_themes,
            move_species_specific=args.move_species_specific_pools,
            move_same_type_bias=args.move_same_type_bias,
            do_build=args.build,
            clean_build=args.clean_build,
            add_all_tms=args.all_tms_lilycove,
            tm_catalog_generation=args.tm_catalog_generation,
            add_evolution_items=args.evolution_items_lilycove,
            add_regional_postcards=args.regional_postcards_lilycove,
            add_mega_stones=args.mega_stones_lilycove,
            include_game_corner=args.include_game_corner,
            game_permadeath=args.permadeath,
            game_field_items=args.field_items,
            game_hm_free=args.hm_free_field_moves,
            game_hm_progression_bypass=(
                args.remove_hm_progression_requirements
            ),
            game_perma_repel=args.perma_repel,
            game_cap_candy=args.cap_candy,
            game_mom_bonus=args.mom_bonus,
            game_party_heal=args.party_heal,
            game_time_turner=args.time_turner,
            game_weather_setter=args.weather_setter,
            game_always_catch=args.always_catch,
            game_force_shiny=args.force_shiny,
            game_permanent_megas=args.permanent_megas,
            game_regional_evolutions=(
                args.regional_evolution_postcards
            ),
            game_level_caps=args.level_caps,
            game_always_mirage_island=args.always_mirage_island,
            difficulty_ai_mode=args.difficulty_ai,
            difficulty_level_boost=args.trainer_level_boost,
            difficulty_level_scope=args.trainer_level_scope,
            difficulty_iv_mode=args.trainer_ivs,
            difficulty_competitive_builds=args.competitive_major_builds,
            difficulty_movesets=args.improved_trainer_movesets,
            difficulty_held_items=args.major_trainer_held_items,
            difficulty_trainer_items=args.major_trainer_healing_items,
            difficulty_force_set=args.force_set_battle_style,
            difficulty_disable_bag=args.disable_bag_in_trainer_battles,
            starter_three_stage_base=args.starter_three_stage_base,
            manual_customizations=manual_customizations,
        )

    except Exception as exc:

        print()
        print("=" * 70)
        print(
            "MASTER RANDOMIZER FAILED"
        )
        print("=" * 70)

        print()
        print(exc)

        sys.exit(1)


if __name__ == "__main__":
    main()
