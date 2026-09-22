#!/usr/bin/env python3
"""Validation and source editing for per-Pokémon manual customisation."""

import copy
import json
import re
from collections import defaultdict
from pathlib import Path

from runtime_paths import ROOT


SPECIES_HEADER_PATTERN = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)
LEARNSET_POINTER_PATTERN = re.compile(
    r"\.levelUpLearnset\s*=\s*([A-Za-z0-9_]+)"
)
BASE_SPECIES_PATTERN = re.compile(
    r"\.baseSpecies\s*=\s*(SPECIES_[A-Z0-9_]+)"
)
LEARNSET_BLOCK_PATTERN = re.compile(
    r"(static const struct LevelUpMove\s+"
    r"([A-Za-z0-9_]+)\[\]\s*=\s*\{\r?\n)"
    r"(.*?)"
    r"(^\};)",
    re.MULTILINE | re.DOTALL,
)

STANDARD_TYPES = (
    "TYPE_NORMAL", "TYPE_FIRE", "TYPE_WATER", "TYPE_ELECTRIC",
    "TYPE_GRASS", "TYPE_ICE", "TYPE_FIGHTING", "TYPE_POISON",
    "TYPE_GROUND", "TYPE_FLYING", "TYPE_PSYCHIC", "TYPE_BUG",
    "TYPE_ROCK", "TYPE_GHOST", "TYPE_DRAGON", "TYPE_DARK",
    "TYPE_STEEL", "TYPE_FAIRY",
)

STAT_FIELDS = (
    "baseHP",
    "baseAttack",
    "baseDefense",
    "baseSpeed",
    "baseSpAttack",
    "baseSpDefense",
)

RANDOM_BOOLEAN_KEYS = (
    "abilities",
    "learnset",
    "learnset_species_specific",
    "learnset_same_type_bias",
    "tm_compatibility",
    "evolutions",
    "trade_evolutions",
    "evolution_moves",
    "types",
)

STAT_MODES = {None, "same", "stages", "full"}


class ManualCustomizationError(RuntimeError):
    pass


def _species_paths(root):
    return Path(root) / "src/data/pokemon/species_info"


def _read_species_records(root=ROOT):
    records = {}

    for filepath in sorted(_species_paths(root).rglob("*.h")):
        # Cloud/sync tools can expose a short-lived staging directory while
        # baseline files are being replaced. It is not game source and may
        # disappear between rglob() and read_text().
        if any(part.startswith(".") for part in filepath.parts):
            continue

        try:
            text = filepath.read_text(encoding="utf-8")
        except FileNotFoundError:
            continue
        headers = list(SPECIES_HEADER_PATTERN.finditer(text))

        for index, header in enumerate(headers):
            end = (
                headers[index + 1].start()
                if index + 1 < len(headers)
                else len(text)
            )
            records[header.group(1)] = {
                "path": filepath,
                "block": text[header.start():end],
            }

    return records


def available_abilities(root=ROOT):
    path = Path(root) / "src/data/abilities.h"
    abilities = set()

    if path.exists():
        abilities.update(
            re.findall(
                r"\[(ABILITY_[A-Z0-9_]+)\]\s*=",
                path.read_text(encoding="utf-8"),
            )
        )

    abilities.discard("ABILITY_NONE")
    return ("ABILITY_NONE", *sorted(abilities))


def _empty_entry():
    return {
        "randomize": {
            **{key: False for key in RANDOM_BOOLEAN_KEYS},
            "stats_mode": None,
        },
        "manual": {
            "abilities": None,
            "types": None,
            "stats": None,
        },
    }


def normalize_customizations(customizations, root=ROOT):
    """Return a validated, canonical deep copy of the GUI customisation map."""
    if customizations is None:
        return {}

    if not isinstance(customizations, dict):
        raise ManualCustomizationError(
            "Manual customisations must be a species-to-settings mapping."
        )

    records = _read_species_records(root)
    known_abilities = set(available_abilities(root))
    normalized = {}

    for species, raw_entry in customizations.items():
        if species not in records or species in {"SPECIES_NONE", "SPECIES_EGG"}:
            raise ManualCustomizationError(
                f"Unknown or non-customisable Pokémon: {species}"
            )

        if not isinstance(raw_entry, dict):
            raise ManualCustomizationError(
                f"Customisation for {species} must be an object."
            )

        entry = _empty_entry()
        randomize = raw_entry.get("randomize", {})
        manual = raw_entry.get("manual", {})

        if not isinstance(randomize, dict) or not isinstance(manual, dict):
            raise ManualCustomizationError(
                f"Customisation sections for {species} must be objects."
            )

        unknown_random = set(randomize) - set(RANDOM_BOOLEAN_KEYS) - {"stats_mode"}
        unknown_manual = set(manual) - {"abilities", "types", "stats"}

        if unknown_random or unknown_manual:
            unknown = sorted(unknown_random | unknown_manual)
            raise ManualCustomizationError(
                f"Unknown {species} customisation setting(s): {', '.join(unknown)}"
            )

        for key in RANDOM_BOOLEAN_KEYS:
            entry["randomize"][key] = bool(randomize.get(key, False))

        stats_mode = randomize.get("stats_mode")
        if stats_mode not in STAT_MODES:
            raise ManualCustomizationError(
                f"Invalid stat mode for {species}: {stats_mode}"
            )
        entry["randomize"]["stats_mode"] = stats_mode

        ability_values = manual.get("abilities")
        if ability_values is not None:
            ability_values = tuple(ability_values)
            if len(ability_values) != 3:
                raise ManualCustomizationError(
                    f"Manual abilities for {species} require all three slots."
                )
            unknown = [value for value in ability_values if value not in known_abilities]
            if unknown:
                raise ManualCustomizationError(
                    f"Unknown manual ability for {species}: {unknown[0]}"
                )
            entry["manual"]["abilities"] = list(ability_values)

        type_values = manual.get("types")
        if type_values is not None:
            type_values = [value for value in type_values if value not in {None, "", "TYPE_NONE"}]
            if len(type_values) not in {1, 2}:
                raise ManualCustomizationError(
                    f"Manual types for {species} require one or two actual types."
                )
            if any(value not in STANDARD_TYPES for value in type_values):
                raise ManualCustomizationError(
                    f"Unknown manual type for {species}."
                )
            if len(set(type_values)) != len(type_values):
                raise ManualCustomizationError(
                    f"Manual types for {species} cannot be duplicates."
                )
            entry["manual"]["types"] = type_values

        stat_values = manual.get("stats")
        if stat_values is not None:
            if not isinstance(stat_values, dict) or set(stat_values) != set(STAT_FIELDS):
                raise ManualCustomizationError(
                    f"Manual stats for {species} require all six stat fields."
                )
            checked_stats = {}
            for field in STAT_FIELDS:
                try:
                    value = int(stat_values[field])
                except (TypeError, ValueError) as exc:
                    raise ManualCustomizationError(
                        f"Manual {field} for {species} must be an integer."
                    ) from exc
                if not 1 <= value <= 250:
                    raise ManualCustomizationError(
                        f"Manual {field} for {species} must be between 1 and 250."
                    )
                checked_stats[field] = value
            entry["manual"]["stats"] = checked_stats

        if entry["manual"]["abilities"] is not None and entry["randomize"]["abilities"]:
            raise ManualCustomizationError(
                f"{species} cannot randomize and manually set abilities together."
            )
        if entry["manual"]["types"] is not None and entry["randomize"]["types"]:
            raise ManualCustomizationError(
                f"{species} cannot randomize and manually set types together."
            )
        if entry["manual"]["stats"] is not None and entry["randomize"]["stats_mode"]:
            raise ManualCustomizationError(
                f"{species} cannot randomize and manually set stats together."
            )
        if not entry["randomize"]["learnset"]:
            entry["randomize"]["learnset_species_specific"] = False
            entry["randomize"]["learnset_same_type_bias"] = False

        normalized[species] = entry

    return normalized


def customizations_from_json(path, root=ROOT):
    with Path(path).open("r", encoding="utf-8") as handle:
        return normalize_customizations(json.load(handle), root=root)


def explicitly_enabled_species(customizations, key):
    return {
        species
        for species, entry in customizations.items()
        if entry["randomize"].get(key)
    }


def species_for_stat_mode(customizations, mode):
    return {
        species
        for species, entry in customizations.items()
        if entry["randomize"].get("stats_mode") == mode
    }


def discover_mega_species(root=ROOT):
    return {
        species
        for species, record in _read_species_records(root).items()
        if re.search(
            r"\.isMegaEvolution\s*=\s*TRUE",
            record["block"],
        )
    }


def learnset_groups(customizations):
    groups = defaultdict(set)
    for species, entry in customizations.items():
        settings = entry["randomize"]
        if settings.get("learnset"):
            groups[(
                settings.get("learnset_species_specific", False),
                settings.get("learnset_same_type_bias", False),
            )].add(species)
    return dict(groups)


def _rewrite_species_blocks(replacements):
    by_path = defaultdict(list)
    for record, new_block in replacements:
        by_path[record["path"]].append((record["block"], new_block))

    for filepath, block_replacements in by_path.items():
        text = filepath.read_text(encoding="utf-8")
        for old_block, new_block in block_replacements:
            if text.count(old_block) != 1:
                raise ManualCustomizationError(
                    f"Could not uniquely locate a species block in {filepath}."
                )
            text = text.replace(old_block, new_block, 1)
        filepath.write_text(text, encoding="utf-8")


def _replace_or_insert(block, pattern, replacement):
    updated, count = re.subn(pattern, replacement, block, count=1, flags=re.MULTILINE)
    if count:
        return updated

    opening = re.search(r"\{\r?\n", block)
    if opening is None:
        raise ManualCustomizationError("Species block has no initializer body.")

    indent_match = re.search(r"(?m)^(\s+)\.[A-Za-z]", block)
    indent = indent_match.group(1) if indent_match else "        "
    insertion = replacement if replacement.endswith("\n") else replacement + "\n"
    insertion = indent + insertion.lstrip()
    return block[:opening.end()] + insertion + block[opening.end():]


def _replace_designator(block, field, expression):
    """Replace every conditional/macro variant of one struct designator."""
    pattern = re.compile(
        rf"(?m)^(?P<indent>\s*)\.{re.escape(field)}\s*=\s*"
        rf".+?,(?P<tail>[ \t]*(?:\\)?)$"
    )

    updated, count = pattern.subn(
        lambda match: (
            f"{match.group('indent')}.{field} = {expression},"
            f"{match.group('tail')}"
        ),
        block,
    )

    if count:
        return updated

    return _replace_or_insert(
        block,
        r"(?!)",
        f"        .{field} = {expression},",
    )


def apply_manual_fields(customizations, category, root=ROOT, species_subset=None):
    if category not in {"types", "abilities", "stats"}:
        raise ValueError(f"Unsupported manual category: {category}")

    records = _read_species_records(root)
    replacements = []
    selected = set(species_subset) if species_subset is not None else None

    for species, entry in customizations.items():
        if selected is not None and species not in selected:
            continue
        values = entry["manual"].get(category)
        if values is None:
            continue

        block = records[species]["block"]

        if category == "types":
            expression = ", ".join(values)
            block = _replace_designator(
                block,
                "types",
                f"MON_TYPES({expression})",
            )
        elif category == "abilities":
            expression = ", ".join(values)
            block = _replace_designator(
                block,
                "abilities",
                f"{{ {expression} }}",
            )
        else:
            for field in STAT_FIELDS:
                block = _replace_designator(
                    block,
                    field,
                    str(values[field]),
                )

        replacements.append((records[species], block))

    _rewrite_species_blocks(replacements)

    if replacements:
        print(f"Applied manual {category} to {len(replacements)} Pokémon.")


def _effective_learnset(species, records, visiting=None):
    if visiting is None:
        visiting = set()
    if species in visiting:
        return None
    visiting = set(visiting)
    visiting.add(species)

    record = records.get(species)
    if record is None:
        return None
    pointer = LEARNSET_POINTER_PATTERN.search(record["block"])
    if pointer:
        return pointer.group(1)
    base = BASE_SPECIES_PATTERN.search(record["block"])
    if base:
        return _effective_learnset(base.group(1), records, visiting)
    return None


def _custom_learnset_symbol(species):
    words = species.removeprefix("SPECIES_").split("_")
    return "sManual" + "".join(word.title() for word in words) + "LevelUpLearnset"


def isolate_custom_learnsets(customizations, root=ROOT):
    """Give every customised species a private copy of its active learnset."""
    if not customizations:
        return {}

    records = _read_species_records(root)
    learnset_file = Path(root) / "src/data/pokemon/level_up_learnsets/gen_9.h"
    learnset_text = learnset_file.read_text(encoding="utf-8")
    blocks = {
        match.group(2): match.group(0)
        for match in LEARNSET_BLOCK_PATTERN.finditer(learnset_text)
    }

    replacements = []
    appended = []
    mapping = {}

    for species in sorted(customizations):
        source_symbol = _effective_learnset(species, records)
        if source_symbol is None:
            continue
        source_block = blocks.get(source_symbol)
        if source_block is None:
            raise ManualCustomizationError(
                f"Could not find active learnset {source_symbol} for {species}."
            )

        new_symbol = _custom_learnset_symbol(species)
        clone = re.sub(
            rf"(?<=struct LevelUpMove\s){re.escape(source_symbol)}(?=\[\])",
            new_symbol,
            source_block,
            count=1,
        )
        if clone == source_block:
            raise ManualCustomizationError(
                f"Could not clone learnset {source_symbol} for {species}."
            )

        block = records[species]["block"]
        if LEARNSET_POINTER_PATTERN.search(block):
            block = LEARNSET_POINTER_PATTERN.sub(
                f".levelUpLearnset = {new_symbol}",
                block,
                count=1,
            )
        else:
            block = _replace_or_insert(
                block,
                r"(?!)",
                f"        .levelUpLearnset = {new_symbol},",
            )

        replacements.append((records[species], block))
        appended.append(clone)
        mapping[species] = new_symbol

    _rewrite_species_blocks(replacements)

    if appended:
        learnset_file.write_text(
            learnset_text.rstrip() + "\n\n" + "\n\n".join(appended) + "\n",
            encoding="utf-8",
        )
        print(f"Isolated {len(appended)} customised level-up learnsets.")

    return mapping


def customization_summary(entry):
    randomize = entry["randomize"]
    manual = entry["manual"]
    parts = []

    labels = (
        ("abilities", "random abilities"),
        ("learnset", "random learnset"),
        ("tm_compatibility", "random TMs"),
        ("evolutions", "random evolutions"),
        ("trade_evolutions", "trade-evo conversion"),
        ("evolution_moves", "evolution moves"),
        ("types", "random types"),
    )
    parts.extend(label for key, label in labels if randomize.get(key))
    if randomize.get("stats_mode"):
        parts.append(f"random stats ({randomize['stats_mode']})")
    parts.extend(
        f"manual {key}"
        for key in ("abilities", "types", "stats")
        if manual.get(key) is not None
    )
    return ", ".join(parts) if parts else "protected from all listed global options"
