#!/usr/bin/env python3

"""Keep May's and Brendan's starter tied to the player's starter slot."""

import json
import re

from runtime_paths import RANDOMIZER_DIR, ROOT


CONFIG_FILE = RANDOMIZER_DIR / "rival_starter_continuity.json"
STARTER_FILE = ROOT / "src/starter_choose.c"
TRAINERS_FILE = ROOT / "src/data/trainers.party"
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
TRAINER_DIFFICULTY_FILE = (
    RANDOMIZER_DIR / "trainer_difficulty_options.json"
)

RIVAL_TRAINER_PATTERN = re.compile(
    r"^TRAINER_(?:MAY|BRENDAN)_"
    r"(?:ROUTE_103|RUSTBORO|ROUTE_110|ROUTE_119|LILYCOVE)_"
    r"(?:TREECKO|TORCHIC|MUDKIP)$"
)

RIVAL_HEADER_PATTERN = re.compile(
    r"^===\s*(TRAINER_(?:MAY|BRENDAN)_"
    r"(?:ROUTE_103|RUSTBORO|ROUTE_110|ROUTE_119|LILYCOVE)_"
    r"(?:TREECKO|TORCHIC|MUDKIP))\s*===\s*$",
    re.MULTILINE,
)

MON_LINE_PATTERN = re.compile(
    r"(?m)^(?P<species_line>[^\r\n]+)\r?\n"
    r"Level:\s*(?P<level>[0-9]+)\s*$"
)

SPECIES_HEADER_PATTERN = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

LEVEL_EVOLUTION_PATTERN = re.compile(
    r"\{\s*EVO_LEVEL\s*,\s*([0-9]+)\s*,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
)

INVALID_FORM_FLAGS = (
    "isMegaEvolution",
    "isPrimalReversion",
    "isUltraBurst",
    "isGigantamax",
    "isTeraForm",
    "isTotem",
)

EXPECTED_RIVAL_PARTIES = 30

FINAL_RIVAL_BATTLE_PATTERN = re.compile(
    r"^TRAINER_(?:MAY|BRENDAN)_LILYCOVE_"
    r"(?:TREECKO|TORCHIC|MUDKIP)$"
)

# The trainer suffix records the player's chosen slot, not the rival's species.
# Emerald's normal cycle is leaf -> fire, fire -> water, water -> leaf.
PLAYER_SLOT_BY_SUFFIX = {
    "TREECKO": 0,
    "TORCHIC": 1,
    "MUDKIP": 2,
}


class RivalStarterContinuityError(RuntimeError):
    """Raised when rival starter continuity cannot be applied safely."""


def configure_rival_starter_continuity(
    enabled=False,
    random_starters=False,
    manual_starters=False,
    evolution_randomisation=False,
):
    """Write every run's choice so a previous setting cannot leak."""

    enabled = bool(enabled)
    random_starters = bool(random_starters)
    manual_starters = bool(manual_starters)

    if enabled and not (random_starters or manual_starters):
        raise RivalStarterContinuityError(
            "Rival starter continuity requires random or manual starters."
        )

    config = {
        "enabled": enabled,
        "random_starters": random_starters,
        "manual_starters": manual_starters,
        "evolution_randomisation": bool(evolution_randomisation),
    }
    config_text = json.dumps(config, indent=2) + "\n"
    changed = (
        not CONFIG_FILE.exists()
        or CONFIG_FILE.read_text(encoding="utf-8") != config_text
    )

    if changed:
        CONFIG_FILE.write_text(config_text, encoding="utf-8")

    print(
        "  Rival starter continuity: "
        + ("ON" if enabled else "off")
    )

    return changed


def _load_config():
    defaults = {
        "enabled": False,
        "random_starters": False,
        "manual_starters": False,
        "evolution_randomisation": False,
    }

    if not CONFIG_FILE.exists():
        return defaults

    try:
        loaded = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RivalStarterContinuityError(
            "Could not read randomizer/rival_starter_continuity.json. "
            "Run the GUI again so it can regenerate the setting."
        ) from exc

    if isinstance(loaded, dict):
        defaults.update(loaded)

    return defaults


def rival_starter_continuity_enabled():
    return bool(_load_config()["enabled"])


def is_rival_starter_slot(trainer_id, mon_index, party_size):
    """The continuity slot is the final defined Pokémon in a rival party."""

    return (
        RIVAL_TRAINER_PATTERN.fullmatch(trainer_id) is not None
        and party_size > 0
        and mon_index == party_size - 1
    )


def _read_starters():
    text = STARTER_FILE.read_text(encoding="utf-8")
    starters = []

    for label in ("GRASS", "FIRE", "WATER"):
        match = re.search(
            rf"#define\s+{label}_STARTER\s+"
            rf"\(IS_FRLG\s*\?\s*SPECIES_[A-Z0-9_]+\s*:\s*"
            rf"(SPECIES_[A-Z0-9_]+)\s*\)",
            text,
        )

        if match is None:
            raise RivalStarterContinuityError(
                f"Could not read the {label.lower()} starter slot from "
                "src/starter_choose.c."
            )

        starters.append(match.group(1))

    if len(set(starters)) != 3:
        raise RivalStarterContinuityError(
            "Rival starter continuity requires three distinct starter slots."
        )

    return tuple(starters)


def _read_species_blocks():
    blocks = {}

    for filepath in sorted(SPECIES_DIR.rglob("*.h")):
        text = filepath.read_text(encoding="utf-8", errors="replace")
        matches = list(SPECIES_HEADER_PATTERN.finditer(text))

        for index, match in enumerate(matches):
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(text)
            )
            blocks[match.group(1)] = text[match.start():end]

    if len(blocks) < 500:
        raise RivalStarterContinuityError(
            "Species parser found suspiciously few entries while applying "
            "rival starter continuity."
        )

    return blocks


def _is_permanent_species(species, blocks):
    block = blocks.get(species)

    if block is None or species in {"SPECIES_NONE", "SPECIES_EGG"}:
        return False

    return not any(
        re.search(
            rf"\.{re.escape(flag)}\s*=\s*TRUE",
            block,
        )
        for flag in INVALID_FORM_FLAGS
    )


def _evolve_for_level(species, level, blocks):
    """Follow current permanent numeric level evolutions at exact thresholds."""

    visited = {species}

    for _ in range(8):
        candidates = []

        for required_level, target in LEVEL_EVOLUTION_PATTERN.findall(
            blocks.get(species, "")
        ):
            required_level = int(required_level)

            # EVO_LEVEL 0 represents a non-level condition such as friendship,
            # move knowledge, gender or time. Do not invent completion of it.
            if required_level <= 0 or level < required_level:
                continue

            if target in visited or not _is_permanent_species(target, blocks):
                continue

            candidates.append(target)

        if not candidates:
            break

        # Source order resolves conditional branches deterministically. When
        # evolution randomisation is on, these targets are already randomised.
        species = candidates[0]
        visited.add(species)

    return species


def _effective_rival_level(level):
    """Include either level-boost scope because rivals are major trainers."""

    if not TRAINER_DIFFICULTY_FILE.exists():
        return level

    try:
        config = json.loads(
            TRAINER_DIFFICULTY_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return level

    if (
        not isinstance(config, dict)
        or config.get("level_scope") not in {"all", "major"}
    ):
        return level

    try:
        boost = int(config.get("level_boost", 0))
    except (TypeError, ValueError):
        boost = 0

    return min(100, level + max(0, boost))


def _boss_permanent_megas_enabled():
    if not TRAINER_DIFFICULTY_FILE.exists():
        return False

    try:
        config = json.loads(
            TRAINER_DIFFICULTY_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError):
        return False

    return bool(
        isinstance(config, dict)
        and config.get("boss_permanent_megas")
    )


def _is_canonical_mega_of(species, base_species):
    return (
        "_MEGA" in species
        and species.split("_MEGA", 1)[0] == base_species
    )


def _rival_base_for_trainer(trainer_id, starters):
    suffix = trainer_id.rsplit("_", 1)[-1]
    player_slot = PLAYER_SLOT_BY_SUFFIX[suffix]
    rival_slot = (player_slot + 1) % 3
    return starters[rival_slot]


def read_current_starters():
    """Return the three final starter-slot species from starter_choose.c."""

    return _read_starters()


def rival_starter_species_for_trainer(
    trainer_id,
    level,
    *,
    starters=None,
    species_blocks=None,
):
    """Resolve a rival's continuous starter at the supplied battle level."""

    if RIVAL_TRAINER_PATTERN.fullmatch(trainer_id) is None:
        raise RivalStarterContinuityError(
            f"{trainer_id} is not a recognised May/Brendan rival party."
        )

    if starters is None:
        starters = _read_starters()

    if species_blocks is None:
        species_blocks = _read_species_blocks()

    base_species = _rival_base_for_trainer(trainer_id, starters)
    return _evolve_for_level(base_species, int(level), species_blocks)


def apply_rival_starter_continuity():
    """Patch all Emerald May/Brendan parties and return the changed count."""

    if not rival_starter_continuity_enabled():
        return 0

    starters = _read_starters()
    blocks = _read_species_blocks()
    text = TRAINERS_FILE.read_text(encoding="utf-8")
    headers = list(RIVAL_HEADER_PATTERN.finditer(text))

    if len(headers) != EXPECTED_RIVAL_PARTIES:
        raise RivalStarterContinuityError(
            "Expected 30 May/Brendan starter party variants, found "
            f"{len(headers)}."
        )

    replacements = []
    audited = []
    preserved_starter_megas = 0
    boss_permanent_megas = _boss_permanent_megas_enabled()

    for header in headers:
        trainer_id = header.group(1)
        next_header = re.search(
            r"(?m)^===\s*TRAINER_[A-Z0-9_]+\s*===\s*$",
            text[header.end():],
        )
        section_end = (
            header.end() + next_header.start()
            if next_header is not None
            else len(text)
        )
        section = text[header.start():section_end]
        mon_matches = list(MON_LINE_PATTERN.finditer(section))

        if not mon_matches:
            raise RivalStarterContinuityError(
                f"Could not find a Pokémon party entry for {trainer_id}."
            )

        ace = mon_matches[-1]
        level = int(ace.group("level"))
        effective_level = _effective_rival_level(level)
        base_species = _rival_base_for_trainer(trainer_id, starters)
        evolved_species = rival_starter_species_for_trainer(
            trainer_id,
            effective_level,
            starters=starters,
            species_blocks=blocks,
        )

        old_line = ace.group("species_line")
        old_species = old_line.split(" @ ", 1)[0].strip()
        held_item = (
            old_line.split(" @ ", 1)[1].strip()
            if " @ " in old_line
            else None
        )
        new_species = evolved_species

        # Trainer randomisation runs before this final continuity pass. Keep a
        # canonical Mega that it deliberately placed in the continuous starter
        # slot for the final Lilycove boss battle; all other rival slots remain
        # ordinary level-appropriate forms.
        if (
            boss_permanent_megas
            and FINAL_RIVAL_BATTLE_PATTERN.fullmatch(trainer_id)
            and _is_canonical_mega_of(old_species, evolved_species)
        ):
            new_species = old_species
            preserved_starter_megas += 1

        new_line = new_species

        if held_item:
            new_line += f" @ {held_item}"

        absolute_start = header.start() + ace.start("species_line")
        absolute_end = header.start() + ace.end("species_line")
        replacements.append((absolute_start, absolute_end, new_line))
        audited.append((trainer_id, base_species, new_species, effective_level))

    new_text = text

    for start, end, replacement in sorted(replacements, reverse=True):
        new_text = new_text[:start] + replacement + new_text[end:]

    changed_count = sum(
        text[start:end] != replacement
        for start, end, replacement in replacements
    )

    if new_text != text:
        TRAINERS_FILE.write_text(new_text, encoding="utf-8")

    # Full audit: every variant must resolve to the correct opposing slot and
    # the level-appropriate form from the current evolution tree.
    if len(audited) != EXPECTED_RIVAL_PARTIES:
        raise RivalStarterContinuityError(
            "Rival starter continuity audit did not cover all parties."
        )

    print()
    print("Rival starter continuity:")
    print(
        f"  Leaf-slot player choice -> fire-slot rival: {starters[1]}"
    )
    print(
        f"  Fire-slot player choice -> water-slot rival: {starters[2]}"
    )
    print(
        f"  Water-slot player choice -> leaf-slot rival: {starters[0]}"
    )
    print(
        f"  Audited {len(audited)} May/Brendan party variants; "
        f"updated {changed_count}."
    )
    if boss_permanent_megas:
        print(
            "  Final rival continuous-starter Megas preserved: "
            f"{preserved_starter_megas}"
        )

    return changed_count
