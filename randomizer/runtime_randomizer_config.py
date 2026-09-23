#!/usr/bin/env python3

import json
import re

from runtime_paths import ROOT


HEADER_PATH = ROOT / "include" / "randomizer_runtime_config.h"
MAP_GROUPS_PATH = ROOT / "data" / "maps" / "map_groups.json"
MAPS_DIR = ROOT / "data" / "maps"
TRAINERS_PATH = ROOT / "src" / "data" / "trainers.party"

STATIC_COMMAND_PATTERN = re.compile(
    r"\b(?:setwildbattle|seteventmon)\s+"
    r"(SPECIES_[A-Z0-9_]+)\s*,"
)
TRAINER_HEADER_PATTERN = re.compile(
    r"^===\s*(TRAINER_[A-Z0-9_]+)\s*===\s*$",
    re.MULTILINE,
)
GYM_MAP_PREFIXES = (
    "RustboroCity",
    "DewfordTown",
    "MauvilleCity",
    "LavaridgeTown",
    "PetalburgCity",
    "FortreeCity",
    "MossdeepCity",
    "SootopolisCity",
)

RUNTIME_COMPONENTS = {
    "pokemon_types",
    "pokemon_bst",
    "abilities",
    "evolutions",
    "move_types",
    "moves",
    "evolution_moves",
    "tms",
    "trades",
    "wild",
    "statics",
    "eggs",
    "starters",
    "trainers",
    "items",
}

# Components whose C-side consumers have been converted.  Keeping this list
# separate lets unfinished conversions retain the established build-time path.
RUNTIME_IMPLEMENTED_COMPONENTS = {
    "pokemon_types",
    "pokemon_bst",
    "abilities",
    "evolutions",
    "move_types",
    "moves",
    "evolution_moves",
    "tms",
    "wild",
    "statics",
    "eggs",
    "trades",
    "starters",
}

BST_MODES = {
    None: 0,
    "same": 0,
    "stages": 1,
    "full": 2,
}

WILD_MODES = {
    None: 0,
    "mapping": 0,
    "slots": 1,
    "runtime": 2,
}

STATIC_MODES = {
    None: 0,
    "preserve": 0,
    "full": 1,
}

TRAINER_MODES = {
    None: 0,
    "mapping": 0,
    "full": 1,
}


def _protected_expression(species):
    species = sorted(set(species))
    if not species:
        return "0"
    return " || ".join(f"((species) == {name})" for name in species)


def _runtime_protection(manual_customizations, randomize_field):
    protected = []
    for species, entry in manual_customizations.items():
        if not entry.get("randomize", {}).get(randomize_field):
            protected.append(species)
    return protected


def _runtime_static_sources():
    """Return packed map ids and original species used by static battles."""
    groups = json.loads(MAP_GROUPS_PATH.read_text(encoding="utf-8"))
    sources = set()

    for group_id, group_name in enumerate(groups["group_order"]):
        for map_id, map_name in enumerate(groups[group_name]):
            script = MAPS_DIR / map_name / "scripts.inc"
            if not script.exists():
                continue
            text = script.read_text(encoding="utf-8")
            packed_map = map_id | (group_id << 8)
            for species in STATIC_COMMAND_PATTERN.findall(text):
                sources.add((packed_map, species))

    return sorted(sources)


def _static_source_macro():
    sources = _runtime_static_sources()
    if not sources:
        return ["#define RANDOMIZER_RUNTIME_STATIC_SOURCES(F)"]

    lines = ["#define RANDOMIZER_RUNTIME_STATIC_SOURCES(F) \\"]
    for index, (map_id, species) in enumerate(sources):
        suffix = " \\" if index + 1 < len(sources) else ""
        lines.append(f"    F(0x{map_id:04X}, {species}){suffix}")
    return lines


def _trainer_metadata():
    text = TRAINERS_PATH.read_text(encoding="utf-8")
    headers = list(TRAINER_HEADER_PATTERN.finditer(text))
    result = {}

    for index, header in enumerate(headers):
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        section = text[header.end():end]
        class_match = re.search(r"^Class:\s*(.+?)\s*$", section, re.MULTILINE)
        name_match = re.search(r"^Name:\s*(.+?)\s*$", section, re.MULTILINE)
        result[header.group(1)] = (
            class_match.group(1).strip() if class_match else "Unknown",
            name_match.group(1).strip() if name_match else None,
        )
    return result


def _runtime_trainer_theme_groups():
    metadata = _trainer_metadata()
    known = set(metadata)
    groups = []

    for city_prefix in GYM_MAP_PREFIXES:
        trainer_ids = set()
        for gym_dir in sorted(MAPS_DIR.glob(f"{city_prefix}_Gym*")):
            for script in sorted(gym_dir.rglob("*.inc")):
                text = script.read_text(encoding="utf-8")
                trainer_ids.update(
                    trainer_id
                    for trainer_id in re.findall(r"\bTRAINER_[A-Z0-9_]+\b", text)
                    if trainer_id in known
                )

        leader_names = {
            metadata[trainer_id][1]
            for trainer_id in trainer_ids
            if metadata[trainer_id][0] == "Leader" and metadata[trainer_id][1]
        }
        trainer_ids.update(
            trainer_id
            for trainer_id, (trainer_class, display_name) in metadata.items()
            if trainer_class == "Leader" and display_name in leader_names
        )
        groups.append(trainer_ids)

    elite_groups = {}
    for trainer_id, (trainer_class, display_name) in metadata.items():
        if trainer_class == "Elite Four" and display_name:
            elite_groups.setdefault(display_name, set()).add(trainer_id)
    groups.extend(elite_groups[name] for name in sorted(elite_groups))

    return sorted(
        (trainer_id, group_id)
        for group_id, trainer_ids in enumerate(groups)
        for trainer_id in trainer_ids
    )


def _trainer_theme_macro():
    assignments = _runtime_trainer_theme_groups()
    if not assignments:
        return ["#define RANDOMIZER_RUNTIME_TRAINER_THEME_GROUPS(F)"]

    lines = ["#define RANDOMIZER_RUNTIME_TRAINER_THEME_GROUPS(F) \\"]
    for index, (trainer_id, group_id) in enumerate(assignments):
        suffix = " \\" if index + 1 < len(assignments) else ""
        lines.append(f"    F({trainer_id}, {group_id}){suffix}")
    return lines


def configure_runtime_randomizer(
    *,
    seed,
    selected_components,
    pokemon_bst_mode=None,
    starter_three_stage_base=False,
    wild_allow_special=False,
    wild_similar_bst=False,
    wild_mode=None,
    static_mode=None,
    enable_all_fossils=False,
    fossil_only_replacements=False,
    trainer_allow_special=False,
    trainer_similar_bst=False,
    trainer_mode=None,
    trainer_type_themes=False,
    rival_starter_continuity=False,
    move_species_specific=False,
    move_same_type_bias=False,
    manual_customizations=None,
):
    """Write the flags that make GUI choices become per-save ROM rules."""
    selected = set(selected_components)
    manual_customizations = manual_customizations or {}

    component_macros = {
        "pokemon_types": "RANDOMIZER_RUNTIME_POKEMON_TYPES",
        "pokemon_bst": "RANDOMIZER_RUNTIME_POKEMON_BST",
        "abilities": "RANDOMIZER_RUNTIME_ABILITIES",
        "evolutions": "RANDOMIZER_RUNTIME_EVOLUTIONS",
        "move_types": "RANDOMIZER_RUNTIME_MOVE_TYPES",
        "moves": "RANDOMIZER_RUNTIME_MOVES",
        "evolution_moves": "RANDOMIZER_RUNTIME_EVOLUTION_MOVES",
        "tms": "RANDOMIZER_RUNTIME_TMS",
        "trades": "RANDOMIZER_RUNTIME_TRADES",
        "wild": "RANDOMIZER_RUNTIME_WILD",
        "statics": "RANDOMIZER_RUNTIME_STATICS",
        "eggs": "RANDOMIZER_RUNTIME_EGGS",
        "starters": "RANDOMIZER_RUNTIME_STARTERS",
        "trainers": "RANDOMIZER_RUNTIME_TRAINERS",
        "items": "RANDOMIZER_RUNTIME_ITEMS",
    }

    lines = [
        "#ifndef GUARD_RANDOMIZER_RUNTIME_CONFIG_H",
        "#define GUARD_RANDOMIZER_RUNTIME_CONFIG_H",
        "",
        "/* Generated by the standalone randomizer. */",
        "#include \"constants/species.h\"",
        "",
        f"#define RANDOMIZER_RUNTIME_ROM_SALT {int(seed) & 0xFFFFFFFF}u",
        "",
    ]

    for component, macro in component_macros.items():
        lines.append(f"#define {macro} {int(component in selected)}")

    lines.extend([
        "",
        f"#define RANDOMIZER_RUNTIME_BST_MODE {BST_MODES[pokemon_bst_mode]}",
        "#define RANDOMIZER_RUNTIME_BST_NATURAL_MIN 175",
        "#define RANDOMIZER_RUNTIME_BST_NATURAL_MAX 1125",
        f"#define RANDOMIZER_RUNTIME_STARTERS_THREE_STAGE {int(bool(starter_three_stage_base))}",
        f"#define RANDOMIZER_RUNTIME_WILD_ALLOW_SPECIAL {int(bool(wild_allow_special))}",
        f"#define RANDOMIZER_RUNTIME_WILD_SIMILAR_BST {int(bool(wild_similar_bst))}",
        f"#define RANDOMIZER_RUNTIME_WILD_MODE {WILD_MODES[wild_mode]}",
        f"#define RANDOMIZER_RUNTIME_STATIC_MODE {STATIC_MODES[static_mode]}",
        f"#define RANDOMIZER_RUNTIME_ALL_FOSSILS {int(bool(enable_all_fossils))}",
        f"#define RANDOMIZER_RUNTIME_FOSSIL_ONLY {int(bool(fossil_only_replacements))}",
        f"#define RANDOMIZER_RUNTIME_TRAINER_ALLOW_SPECIAL {int(bool(trainer_allow_special))}",
        f"#define RANDOMIZER_RUNTIME_TRAINER_SIMILAR_BST {int(bool(trainer_similar_bst))}",
        f"#define RANDOMIZER_RUNTIME_TRAINER_MODE {TRAINER_MODES[trainer_mode]}",
        f"#define RANDOMIZER_RUNTIME_TRAINER_TYPE_THEMES {int(bool(trainer_type_themes))}",
        f"#define RANDOMIZER_RUNTIME_RIVAL_CONTINUITY {int(bool(rival_starter_continuity))}",
        f"#define RANDOMIZER_RUNTIME_MOVE_SPECIES_SPECIFIC {int(bool(move_species_specific))}",
        f"#define RANDOMIZER_RUNTIME_MOVE_SAME_TYPE_BIAS {int(bool(move_same_type_bias))}",
        "",
    ])
    lines.extend(_static_source_macro())
    lines.extend([
        "",
    ])
    lines.extend(_trainer_theme_macro())
    lines.extend([
        "",
        "#define RANDOMIZER_RUNTIME_PROTECT_TYPES(species) (\\",
        "    " + _protected_expression(
            _runtime_protection(manual_customizations, "types")
        ) + ")",
        "#define RANDOMIZER_RUNTIME_PROTECT_STATS(species) (\\",
        "    " + _protected_expression(
            _runtime_protection(manual_customizations, "stats_mode")
        ) + ")",
        "#define RANDOMIZER_RUNTIME_PROTECT_ABILITIES(species) (\\",
        "    " + _protected_expression(
            _runtime_protection(manual_customizations, "abilities")
        ) + ")",
        "#define RANDOMIZER_RUNTIME_PROTECT_EVOLUTIONS(species) (\\",
        "    " + _protected_expression(
            _runtime_protection(manual_customizations, "evolutions")
        ) + ")",
        "#define RANDOMIZER_RUNTIME_PROTECT_MOVES(species) (\\",
        "    " + _protected_expression(
            _runtime_protection(manual_customizations, "learnset")
        ) + ")",
        "#define RANDOMIZER_RUNTIME_PROTECT_EVOLUTION_MOVES(species) (\\",
        "    " + _protected_expression(
            _runtime_protection(manual_customizations, "evolution_moves")
        ) + ")",
        "#define RANDOMIZER_RUNTIME_PROTECT_TMS(species) (\\",
        "    " + _protected_expression(
            _runtime_protection(manual_customizations, "tm_compatibility")
        ) + ")",
        "",
        "#endif // GUARD_RANDOMIZER_RUNTIME_CONFIG_H",
        "",
    ])

    text = "\n".join(lines)
    old = HEADER_PATH.read_text(encoding="utf-8") if HEADER_PATH.exists() else None
    if old == text:
        return False
    HEADER_PATH.write_text(text, encoding="utf-8")
    return True
