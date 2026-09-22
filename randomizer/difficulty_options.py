#!/usr/bin/env python3

"""Seeded, opt-in trainer difficulty generation.

This module deliberately runs after every Pokemon, move, manual-customisation
and trainer-species pass.  It therefore builds trainer sets from the data that
will actually be compiled into the ROM rather than from canonical Pokemon
roles.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from runtime_paths import ROOT


TRAINERS_RELATIVE = Path("src/data/trainers.party")
SPECIES_RELATIVE = Path("src/data/pokemon/species_info")
LEARNABLES_RELATIVE = Path("src/data/pokemon/all_learnables.json")
LEARNSETS_RELATIVE = Path("src/data/pokemon/level_up_learnsets/gen_9.h")
MOVES_RELATIVE = Path("src/data/moves_info.h")
MOVE_CONSTANTS_RELATIVE = Path("include/constants/moves.h")
ABILITIES_RELATIVE = Path("src/data/abilities.h")

MAJOR_TRAINER_CLASSES = {
    "Leader",
    "Elite Four",
    "Champion",
}

FAIR_AI_FLAGS = (
    "AI_FLAG_BASIC_TRAINER",
    "AI_FLAG_SMART_SWITCHING",
    "AI_FLAG_PP_STALL_PREVENTION",
    "AI_FLAG_ASSUMPTIONS",
    "AI_FLAG_RANDOMIZE_SWITCHIN",
)

OMNISCIENT_AI_FLAGS = (
    "AI_FLAG_SMART_TRAINER",
    "AI_FLAG_PREDICTION",
    "AI_FLAG_KNOW_OPPONENT_PARTY",
)

STAT_FIELDS = (
    ("baseHP", "hp"),
    ("baseAttack", "attack"),
    ("baseDefense", "defense"),
    ("baseSpeed", "speed"),
    ("baseSpAttack", "sp_attack"),
    ("baseSpDefense", "sp_defense"),
)

SETUP_MOVES = {
    "physical": (
        "MOVE_DRAGON_DANCE",
        "MOVE_SWORDS_DANCE",
        "MOVE_BULK_UP",
        "MOVE_COIL",
        "MOVE_HONE_CLAWS",
        "MOVE_VICTORY_DANCE",
        "MOVE_SHIFT_GEAR",
        "MOVE_HOWL",
    ),
    "special": (
        "MOVE_QUIVER_DANCE",
        "MOVE_NASTY_PLOT",
        "MOVE_CALM_MIND",
        "MOVE_TAIL_GLOW",
        "MOVE_GEOMANCY",
        "MOVE_TORCH_SONG",
        "MOVE_CHARGE_BEAM",
    ),
}

RECOVERY_MOVES = (
    "MOVE_RECOVER",
    "MOVE_ROOST",
    "MOVE_SOFT_BOILED",
    "MOVE_SLACK_OFF",
    "MOVE_MILK_DRINK",
    "MOVE_MOONLIGHT",
    "MOVE_MORNING_SUN",
    "MOVE_SYNTHESIS",
    "MOVE_SHORE_UP",
    "MOVE_STRENGTH_SAP",
    "MOVE_WISH",
)

UTILITY_MOVES = (
    "MOVE_SPORE",
    "MOVE_SLEEP_POWDER",
    "MOVE_THUNDER_WAVE",
    "MOVE_WILL_O_WISP",
    "MOVE_TOXIC",
    "MOVE_STEALTH_ROCK",
    "MOVE_STICKY_WEB",
    "MOVE_REFLECT",
    "MOVE_LIGHT_SCREEN",
    "MOVE_TAILWIND",
    "MOVE_TRICK_ROOM",
    "MOVE_TAUNT",
    "MOVE_ENCORE",
    "MOVE_PROTECT",
)

BANNED_MOVES = {
    "MOVE_NONE",
    "MOVE_UNAVAILABLE",
    "MOVE_STRUGGLE",
    "MOVE_SKETCH",
    "MOVE_CHATTER",
    "MOVE_SELF_DESTRUCT",
    "MOVE_EXPLOSION",
    "MOVE_MEMENTO",
    "MOVE_FINAL_GAMBIT",
    "MOVE_HEALING_WISH",
    "MOVE_LUNAR_DANCE",
    "MOVE_PIKA_PAPOW",
    "MOVE_VEEVEE_VOLLEY",
}

BANNED_MOVE_PREFIXES = (
    "MOVE_G_MAX_",
    "MOVE_MAX_",
)

PHYSICAL_ABILITIES = {
    "ABILITY_HUGE_POWER": 2.0,
    "ABILITY_PURE_POWER": 2.0,
    "ABILITY_GORILLA_TACTICS": 1.5,
    "ABILITY_HUSTLE": 1.35,
    "ABILITY_GUTS": 1.35,
    "ABILITY_TOXIC_BOOST": 1.35,
}

SPECIAL_ABILITIES = {
    "ABILITY_SOLAR_POWER": 1.5,
    "ABILITY_FLARE_BOOST": 1.35,
}


class DifficultyOptionError(RuntimeError):
    pass


def _read(path: Path) -> str:
    if not path.exists():
        raise DifficultyOptionError(
            f"Required difficulty source file is missing:\n{path}"
        )
    return path.read_text(encoding="utf-8")


def _write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def _constant_blocks(text: str, prefix: str) -> dict[str, str]:
    pattern = re.compile(
        rf"^\s*\[({re.escape(prefix)}[A-Z0-9_]+)\]\s*=\s*$",
        re.MULTILINE,
    )
    matches = list(pattern.finditer(text))
    return {
        match.group(1): text[
            match.start():
            matches[index + 1].start() if index + 1 < len(matches) else len(text)
        ]
        for index, match in enumerate(matches)
    }


def _load_species(root: Path) -> tuple[dict[str, dict], dict[str, str]]:
    blocks: dict[str, str] = {}
    header = re.compile(
        r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
        re.MULTILINE,
    )

    for path in sorted((root / SPECIES_RELATIVE).rglob("*.h")):
        if any(part.startswith(".") for part in path.parts):
            continue
        try:
            text = _read(path)
        except DifficultyOptionError:
            if not path.exists():
                continue
            raise
        matches = list(header.finditer(text))
        for index, match in enumerate(matches):
            blocks[match.group(1)] = text[
                match.start():
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            ]

    if len(blocks) < 500:
        raise DifficultyOptionError(
            f"Difficulty species parser found only {len(blocks)} species."
        )

    species_data: dict[str, dict] = {}
    display_names: dict[str, str] = {}

    for species, block in blocks.items():
        stats = {}
        for source_name, result_name in STAT_FIELDS:
            match = re.search(
                rf"\.{source_name}\s*=\s*([0-9]+)",
                block,
            )
            if match:
                stats[result_name] = int(match.group(1))

        types_match = re.search(
            r"\.types\s*=\s*MON_TYPES\(([^)]+)\)",
            block,
        )
        types = (
            tuple(re.findall(r"TYPE_[A-Z0-9_]+", types_match.group(1)))
            if types_match
            else ()
        )

        abilities_match = re.search(
            r"\.abilities\s*=\s*\{([^}]+)\}",
            block,
        )
        abilities = (
            tuple(
                ability
                for ability in re.findall(
                    r"ABILITY_[A-Z0-9_]+",
                    abilities_match.group(1),
                )
                if ability != "ABILITY_NONE"
            )
            if abilities_match
            else ()
        )

        learnset_match = re.search(
            r"\.levelUpLearnset\s*=\s*([A-Za-z0-9_]+)",
            block,
        )
        name_match = re.search(
            r'\.speciesName\s*=\s*_?\("([^"]+)"\)',
            block,
        )

        species_data[species] = {
            "stats": stats,
            "types": tuple(dict.fromkeys(types)),
            "abilities": tuple(dict.fromkeys(abilities)),
            "learnset": learnset_match.group(1) if learnset_match else None,
        }

        if name_match:
            display_names[name_match.group(1).casefold()] = species

    return species_data, display_names


def _load_ability_ratings(root: Path) -> dict[str, int]:
    blocks = _constant_blocks(_read(root / ABILITIES_RELATIVE), "ABILITY_")
    ratings = {}
    for ability, block in blocks.items():
        match = re.search(r"\.aiRating\s*=\s*(-?[0-9]+)", block)
        ratings[ability] = int(match.group(1)) if match else 0
    return ratings


def _load_move_data(root: Path) -> dict[str, dict]:
    blocks = _constant_blocks(_read(root / MOVES_RELATIVE), "MOVE_")
    constants_text = _read(root / MOVE_CONSTANTS_RELATIVE)
    special_section = re.search(
        r"// Z Moves(.*?)MOVES_COUNT_DYNAMAX",
        constants_text,
        re.DOTALL,
    )
    special_battle_moves = (
        set(re.findall(r"\bMOVE_[A-Z0-9_]+\b", special_section.group(1)))
        if special_section
        else set()
    )
    result = {}

    for move, block in blocks.items():
        if move in special_battle_moves:
            continue
        type_match = re.search(r"\.type\s*=\s*(?:[^,\n]*?)?(TYPE_[A-Z0-9_]+)", block)
        category_match = re.search(
            r"\.category\s*=\s*(DAMAGE_CATEGORY_[A-Z0-9_]+)",
            block,
        )
        power_match = re.search(r"\.power\s*=\s*([0-9]+)", block)
        accuracy_match = re.search(r"\.accuracy\s*=\s*([0-9]+)", block)
        priority_match = re.search(r"\.priority\s*=\s*(-?[0-9]+)", block)
        effect_match = re.search(r"\.effect\s*=\s*(EFFECT_[A-Z0-9_]+)", block)

        if type_match is None or category_match is None:
            continue

        result[move] = {
            "type": type_match.group(1),
            "category": category_match.group(1),
            "power": int(power_match.group(1)) if power_match else 0,
            "accuracy": int(accuracy_match.group(1)) if accuracy_match else 100,
            "priority": int(priority_match.group(1)) if priority_match else 0,
            "effect": effect_match.group(1) if effect_match else None,
        }

    if len(result) < 500:
        raise DifficultyOptionError(
            f"Difficulty move parser found only {len(result)} moves."
        )
    return result


def _load_level_up_moves(root: Path) -> dict[str, tuple[tuple[int, str], ...]]:
    text = _read(root / LEARNSETS_RELATIVE)
    pattern = re.compile(
        r"static const struct LevelUpMove\s+([A-Za-z0-9_]+)\[\]\s*=\s*\{(.*?)^\};",
        re.MULTILINE | re.DOTALL,
    )
    result = {}
    for match in pattern.finditer(text):
        entries = tuple(
            (int(level), move)
            for level, move in re.findall(
                r"LEVEL_UP_MOVE\(\s*([0-9]+)\s*,\s*(MOVE_[A-Z0-9_]+)\s*\)",
                match.group(2),
            )
        )
        result[match.group(1)] = entries
    return result


def _load_learnables(root: Path) -> dict[str, tuple[str, ...]]:
    try:
        raw = json.loads(_read(root / LEARNABLES_RELATIVE))
    except json.JSONDecodeError as exc:
        raise DifficultyOptionError(
            f"Could not parse {LEARNABLES_RELATIVE}: {exc}"
        ) from exc
    return {
        "SPECIES_" + name: tuple(moves)
        for name, moves in raw.items()
    }


def _species_from_header(
    paragraph: str,
    species_data: dict[str, dict],
    display_names: dict[str, str],
) -> str | None:
    first_line = paragraph.splitlines()[0].strip() if paragraph.splitlines() else ""
    first_part = first_line.split(" @ ", 1)[0].strip()

    if "(" in first_part:
        for candidate in reversed(re.findall(r"\(([^()]+)\)", first_part)):
            if candidate not in {"M", "F"}:
                first_part = candidate
                break

    if first_part.startswith("SPECIES_"):
        return first_part if first_part in species_data else None

    direct = (
        "SPECIES_"
        + first_part.upper()
        .replace("É", "E")
        .replace("’", "")
        .replace("'", "")
        .replace(".", "")
        .replace(":", "")
        .replace("-", "_")
        .replace(" ", "_")
    )
    if direct in species_data:
        return direct
    return display_names.get(first_part.casefold())


def _get_level(paragraph: str) -> int:
    match = re.search(r"^Level:\s*([0-9]+)\s*$", paragraph, re.MULTILINE)
    return int(match.group(1)) if match else 1


def _set_field(paragraph: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    replacement = f"{key}: {value}"
    if pattern.search(paragraph):
        return pattern.sub(replacement, paragraph, count=1)

    lines = paragraph.splitlines()
    move_index = next(
        (index for index, line in enumerate(lines) if re.match(r"^\s*-\s+", line)),
        len(lines),
    )
    lines.insert(move_index, replacement)
    return "\n".join(lines)


def _set_level(paragraph: str, level: int) -> str:
    return _set_field(paragraph, "Level", str(max(1, min(100, level))))


def _set_held_item(paragraph: str, item: str) -> str:
    lines = paragraph.splitlines()
    if not lines:
        return paragraph
    if " @ " in lines[0]:
        lines[0] = lines[0].split(" @ ", 1)[0] + " @ " + item
    else:
        lines[0] += " @ " + item
    return "\n".join(lines)


def _replace_moves(paragraph: str, moves: tuple[str, ...]) -> str:
    lines = [line for line in paragraph.splitlines() if not re.match(r"^\s*-\s+", line)]
    lines.extend(f"- {move}" for move in moves)
    return "\n".join(lines)


def _best_ability(
    abilities: tuple[str, ...],
    ratings: dict[str, int],
    rng: random.Random,
) -> str | None:
    if not abilities:
        return None
    highest = max(ratings.get(ability, 0) for ability in abilities)
    return rng.choice(
        [ability for ability in abilities if ratings.get(ability, 0) == highest]
    )


def _role(species: dict, ability: str | None = None) -> dict:
    stats = species.get("stats", {})
    attack = float(stats.get("attack", 1))
    sp_attack = float(stats.get("sp_attack", 1))

    attack *= PHYSICAL_ABILITIES.get(ability, 1.0)
    sp_attack *= SPECIAL_ABILITIES.get(ability, 1.0)

    physical = attack >= sp_attack
    offense = attack if physical else sp_attack
    defense = stats.get("defense", 1)
    sp_defense = stats.get("sp_defense", 1)
    speed = stats.get("speed", 1)
    hp = stats.get("hp", 1)
    bulky = hp + max(defense, sp_defense) >= offense * 2.05
    fast = speed >= (defense + sp_defense) / 2

    if bulky:
        if defense >= sp_defense:
            nature = "NATURE_IMPISH" if physical else "NATURE_BOLD"
            ev_stats = ("HP", "Def", "Atk" if physical else "SpA")
        else:
            nature = "NATURE_CAREFUL" if physical else "NATURE_CALM"
            ev_stats = ("HP", "SpD", "Atk" if physical else "SpA")
    elif physical:
        nature = "NATURE_JOLLY" if fast else "NATURE_ADAMANT"
        ev_stats = ("Atk", "Spe", "HP")
    else:
        nature = "NATURE_TIMID" if fast else "NATURE_MODEST"
        ev_stats = ("SpA", "Spe", "HP")

    return {
        "attack_style": "physical" if physical else "special",
        "category": (
            "DAMAGE_CATEGORY_PHYSICAL"
            if physical
            else "DAMAGE_CATEGORY_SPECIAL"
        ),
        "bulky": bulky,
        "nature": nature,
        "ev_stats": ev_stats,
    }


def _is_usable_move(move: str, data: dict | None) -> bool:
    if data is None or move in BANNED_MOVES:
        return False
    if any(move.startswith(prefix) for prefix in BANNED_MOVE_PREFIXES):
        return False
    if data.get("effect") in {
        "EFFECT_OHKO",
        "EFFECT_EXPLOSION",
        "EFFECT_RECHARGE",
        "EFFECT_TWO_TURNS_ATTACK",
        "EFFECT_SKY_ATTACK",
        "EFFECT_SOLAR_BEAM",
        "EFFECT_FOCUS_PUNCH",
        "EFFECT_BELCH",
        "EFFECT_LAST_RESORT",
    }:
        return False
    return True


def _move_score(move: str, data: dict, role: dict, types: tuple[str, ...]) -> float:
    power = data.get("power", 0)
    accuracy = data.get("accuracy", 100) or 100
    score = power + min(100, accuracy) * 0.18
    if data.get("category") == role["category"]:
        score += 28
    if data.get("type") in types:
        score += 42
    if data.get("priority", 0) > 0:
        score += 8
    if data.get("effect") in {
        "EFFECT_RECHARGE",
        "EFFECT_TWO_TURNS_ATTACK",
        "EFFECT_SKY_ATTACK",
        "EFFECT_SOLAR_BEAM",
    }:
        score -= 28
    return score


def _choose_moves(
    species_constant: str,
    species: dict,
    level: int,
    role: dict,
    move_data: dict[str, dict],
    learnables: dict[str, tuple[str, ...]],
    level_up_moves: dict[str, tuple[tuple[int, str], ...]],
    rng: random.Random,
) -> tuple[str, ...]:
    current_level_moves = {
        move
        for move_level, move in level_up_moves.get(species.get("learnset"), ())
        if move_level <= level
    }
    pool = set(learnables.get(species_constant, ())) | current_level_moves
    usable = {
        move
        for move in pool
        if _is_usable_move(move, move_data.get(move))
    }

    damaging = sorted(
        move
        for move in usable
        if move_data[move].get("power", 0) >= 30
        and move_data[move].get("category")
        in {"DAMAGE_CATEGORY_PHYSICAL", "DAMAGE_CATEGORY_SPECIAL"}
    )
    damaging.sort(
        key=lambda move: (
            _move_score(move, move_data[move], role, species.get("types", ())),
            rng.random(),
        ),
        reverse=True,
    )

    chosen: list[str] = []
    types = species.get("types", ())

    for type_name in types:
        match = next(
            (
                move
                for move in damaging
                if move_data[move].get("type") == type_name
                and move_data[move].get("category") == role["category"]
            ),
            None,
        )
        if match and match not in chosen:
            chosen.append(match)

    coverage = next(
        (
            move
            for move in damaging
            if move not in chosen
            and move_data[move].get("type") not in types
            and move_data[move].get("category") == role["category"]
        ),
        None,
    )
    if coverage:
        chosen.append(coverage)

    status_preferences = list(SETUP_MOVES[role["attack_style"]])
    if role["bulky"]:
        status_preferences = list(RECOVERY_MOVES) + status_preferences
    status_preferences += list(UTILITY_MOVES)
    status_move = next((move for move in status_preferences if move in usable), None)
    if status_move and len(chosen) < 4:
        chosen.append(status_move)

    for move in damaging:
        if len(chosen) >= 4:
            break
        if move not in chosen:
            chosen.append(move)

    if len(chosen) < 4:
        for move in sorted(usable):
            if len(chosen) >= 4:
                break
            if move not in chosen:
                chosen.append(move)

    return tuple(chosen[:4])


def _held_item(level: int, role: dict, ability: str | None, moves: tuple[str, ...]) -> str:
    if ability == "ABILITY_GUTS":
        return "ITEM_FLAME_ORB"
    if ability == "ABILITY_TOXIC_BOOST":
        return "ITEM_TOXIC_ORB"
    if level < 20:
        return "ITEM_ORAN_BERRY"
    if level < 35:
        return "ITEM_SITRUS_BERRY"
    if role["bulky"]:
        return "ITEM_LEFTOVERS"
    if any(move in SETUP_MOVES[role["attack_style"]] for move in moves):
        return "ITEM_SITRUS_BERRY"
    return "ITEM_LIFE_ORB"


def _scaled_iv(level: int, major: bool) -> int:
    if level <= 15:
        value = 5
    elif level <= 25:
        value = 10
    elif level <= 35:
        value = 15
    elif level <= 45:
        value = 20
    elif level <= 55:
        value = 25
    else:
        value = 31
    return max(value, 20) if major else value


def _iv_line(value: int) -> str:
    return (
        f"{value} HP / {value} Atk / {value} Def / "
        f"{value} SpA / {value} SpD / {value} Spe"
    )


def _ev_line(role: dict) -> str:
    first, second, third = role["ev_stats"]
    return f"252 {first} / 252 {second} / 4 {third}"


def _replace_metadata_field(metadata: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}:.*$", re.MULTILINE)
    line = f"{key}: {value}"
    if pattern.search(metadata):
        return pattern.sub(line, metadata, count=1)
    return metadata.rstrip() + "\n" + line


def _trainer_class(section: str) -> str:
    match = re.search(r"^Class:\s*(.+?)\s*$", section, re.MULTILINE)
    return match.group(1).strip() if match else "Unknown"


def _trainer_healing_items(section: str) -> str:
    levels = [
        int(level)
        for level in re.findall(r"^Level:\s*([0-9]+)\s*$", section, re.MULTILINE)
    ]
    highest = max(levels, default=1)
    trainer_class = _trainer_class(section)
    if highest < 25:
        item = "ITEM_SUPER_POTION"
    elif highest < 45:
        item = "ITEM_HYPER_POTION"
    else:
        item = "ITEM_FULL_RESTORE"
    count = 2 if trainer_class in {"Elite Four", "Champion"} else 1
    return " / ".join([item] * count)


def _transform_section(
    section: str,
    *,
    rng: random.Random,
    species_data: dict[str, dict],
    display_names: dict[str, str],
    ability_ratings: dict[str, int],
    move_data: dict[str, dict],
    learnables: dict[str, tuple[str, ...]],
    level_up_moves: dict[str, tuple[tuple[int, str], ...]],
    ai_mode: str | None,
    level_boost: int,
    level_scope: str,
    iv_mode: str | None,
    competitive_builds: bool,
    improved_movesets: bool,
    held_items: bool,
    trainer_items: bool,
) -> tuple[str, dict[str, int]]:
    paragraphs = re.split(r"\n[ \t]*\n", section.strip())
    if not paragraphs:
        return section, {}

    trainer_class = _trainer_class(section)
    major = trainer_class in MAJOR_TRAINER_CLASSES
    counters = {
        "trainers": 0,
        "mons": 0,
        "levels": 0,
        "abilities": 0,
        "movesets": 0,
        "items": 0,
    }

    if ai_mode:
        flags = FAIR_AI_FLAGS if ai_mode == "fair" else OMNISCIENT_AI_FLAGS
        paragraphs[0] = _replace_metadata_field(
            paragraphs[0],
            "AI",
            " / ".join(flags),
        )
        counters["trainers"] = 1

    if trainer_items and major:
        paragraphs[0] = _replace_metadata_field(
            paragraphs[0],
            "Items",
            _trainer_healing_items(section),
        )

    mon_indices = [
        index
        for index, paragraph in enumerate(paragraphs)
        if re.search(r"^Level:\s*[0-9]+\s*$", paragraph, re.MULTILINE)
    ]

    for index in mon_indices:
        paragraph = paragraphs[index]
        level = _get_level(paragraph)

        if level_boost and (level_scope == "all" or major):
            boosted = min(100, level + level_boost)
            if boosted != level:
                paragraph = _set_level(paragraph, boosted)
                counters["levels"] += 1
            level = boosted

        species_constant = _species_from_header(
            paragraph,
            species_data,
            display_names,
        )
        species = species_data.get(species_constant) if species_constant else None

        if iv_mode:
            iv = 31 if iv_mode == "perfect" else _scaled_iv(level, major)
            paragraph = _set_field(paragraph, "IVs", _iv_line(iv))

        if species is not None:
            optimize_major_ability = major and (
                competitive_builds or improved_movesets or held_items
            )
            ability = None
            if optimize_major_ability:
                ability = _best_ability(
                    species.get("abilities", ()),
                    ability_ratings,
                    rng,
                )
                if ability:
                    paragraph = _set_field(paragraph, "Ability", ability)
                    counters["abilities"] += 1

            role = _role(species, ability)
            moves: tuple[str, ...] = ()

            if improved_movesets:
                moves = _choose_moves(
                    species_constant,
                    species,
                    level,
                    role,
                    move_data,
                    learnables,
                    level_up_moves,
                    rng,
                )
                if moves:
                    paragraph = _replace_moves(paragraph, moves)
                    counters["movesets"] += 1

            if competitive_builds and major:
                paragraph = _set_field(paragraph, "EVs", _ev_line(role))
                paragraph = _set_field(paragraph, "Nature", role["nature"])

            if held_items and major:
                paragraph = _set_held_item(
                    paragraph,
                    _held_item(level, role, ability, moves),
                )
                counters["items"] += 1

        paragraphs[index] = paragraph
        counters["mons"] += 1

    return "\n\n".join(paragraphs), counters


def apply_trainer_difficulty(
    *,
    seed: int,
    ai_mode: str | None = None,
    level_boost: int = 0,
    level_scope: str = "all",
    iv_mode: str | None = None,
    competitive_builds: bool = False,
    improved_movesets: bool = False,
    held_items: bool = False,
    trainer_items: bool = False,
    root: Path = ROOT,
) -> dict[str, int]:
    """Apply selected trainer-data difficulty options to trainers.party."""

    if ai_mode not in {None, "fair", "omniscient"}:
        raise DifficultyOptionError(f"Unknown trainer AI mode: {ai_mode}")
    if level_scope not in {"all", "major"}:
        raise DifficultyOptionError(f"Unknown trainer-level scope: {level_scope}")
    if iv_mode not in {None, "scaled", "perfect"}:
        raise DifficultyOptionError(f"Unknown trainer IV mode: {iv_mode}")
    if not 0 <= int(level_boost) <= 20:
        raise DifficultyOptionError("Trainer level boost must be between 0 and 20.")

    enabled = any(
        (
            ai_mode,
            level_boost,
            iv_mode,
            competitive_builds,
            improved_movesets,
            held_items,
            trainer_items,
        )
    )
    if not enabled:
        return {}

    trainers_path = root / TRAINERS_RELATIVE
    trainer_text = _read(trainers_path)
    species_data, display_names = _load_species(root)
    ability_ratings = _load_ability_ratings(root)
    move_data = _load_move_data(root)
    learnables = _load_learnables(root)
    level_up_moves = _load_level_up_moves(root)
    rng = random.Random(seed)

    header = re.compile(
        r"^===\s*(TRAINER_[A-Z0-9_]+)\s*===\s*$",
        re.MULTILINE,
    )
    matches = list(header.finditer(trainer_text))
    if len(matches) < 100:
        raise DifficultyOptionError(
            f"Difficulty trainer parser found only {len(matches)} trainers."
        )

    prefix = trainer_text[:matches[0].start()].rstrip()
    sections = []
    totals = {
        "trainers": 0,
        "mons": 0,
        "levels": 0,
        "abilities": 0,
        "movesets": 0,
        "items": 0,
    }

    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(trainer_text)
        transformed, counters = _transform_section(
            trainer_text[match.start():end],
            rng=rng,
            species_data=species_data,
            display_names=display_names,
            ability_ratings=ability_ratings,
            move_data=move_data,
            learnables=learnables,
            level_up_moves=level_up_moves,
            ai_mode=ai_mode,
            level_boost=int(level_boost),
            level_scope=level_scope,
            iv_mode=iv_mode,
            competitive_builds=bool(competitive_builds),
            improved_movesets=bool(improved_movesets),
            held_items=bool(held_items),
            trainer_items=bool(trainer_items),
        )
        sections.append(transformed.strip())
        for key in totals:
            totals[key] += counters.get(key, 0)

    output = prefix + "\n\n" + "\n\n".join(sections) + "\n"
    _write_if_changed(trainers_path, output)

    print()
    print("Applying difficulty options...")
    print(f"  Trainer AI: {ai_mode or 'unchanged'}")
    print(
        "  Trainer level boost: "
        + (f"+{level_boost} ({level_scope})" if level_boost else "off")
    )
    print(f"  Trainer IVs: {iv_mode or 'unchanged'}")
    print(
        "  Major-trainer EVs/natures: "
        + ("ON" if competitive_builds else "off")
    )
    print(
        "  Improved movesets: "
        + ("ON" if improved_movesets else "off")
    )
    print(
        "  Major-trainer held items: "
        + ("ON" if held_items else "off")
    )
    print(
        "  Major-trainer healing items: "
        + ("ON" if trainer_items else "off")
    )
    print(
        "  Updated: "
        f"{totals['mons']} party entries, "
        f"{totals['levels']} levels, "
        f"{totals['movesets']} movesets, "
        f"{totals['abilities']} major-trainer abilities, "
        f"{totals['items']} held items"
    )
    return totals
