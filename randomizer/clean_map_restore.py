#!/usr/bin/env python3

import re
from pathlib import Path

from runtime_paths import ROOT, BASELINE_ROOT
from berry_item_events import restore_berry_item_events


# Emerald's scripts refer to TMs by their original move-based aliases.  A
# selectable later-generation TM catalogue may not contain those moves, while
# the numbered ITEM_TM01 ... ITEM_TM50 slots always exist.  Normalising legacy
# references to their Emerald slot number preserves the location's TM number
# and lets the selected catalogue decide which move that TM teaches.
EMERALD_TM_SLOTS = {
    "FOCUS_PUNCH": 1,
    "DRAGON_CLAW": 2,
    "WATER_PULSE": 3,
    "CALM_MIND": 4,
    "ROAR": 5,
    "TOXIC": 6,
    "HAIL": 7,
    "BULK_UP": 8,
    "BULLET_SEED": 9,
    "HIDDEN_POWER": 10,
    "SUNNY_DAY": 11,
    "TAUNT": 12,
    "ICE_BEAM": 13,
    "BLIZZARD": 14,
    "HYPER_BEAM": 15,
    "LIGHT_SCREEN": 16,
    "PROTECT": 17,
    "RAIN_DANCE": 18,
    "GIGA_DRAIN": 19,
    "SAFEGUARD": 20,
    "FRUSTRATION": 21,
    "SOLAR_BEAM": 22,
    "IRON_TAIL": 23,
    "THUNDERBOLT": 24,
    "THUNDER": 25,
    "EARTHQUAKE": 26,
    "RETURN": 27,
    "DIG": 28,
    "PSYCHIC": 29,
    "SHADOW_BALL": 30,
    "BRICK_BREAK": 31,
    "DOUBLE_TEAM": 32,
    "REFLECT": 33,
    "SHOCK_WAVE": 34,
    "FLAMETHROWER": 35,
    "SLUDGE_BOMB": 36,
    "SANDSTORM": 37,
    "FIRE_BLAST": 38,
    "ROCK_TOMB": 39,
    "AERIAL_ACE": 40,
    "TORMENT": 41,
    "FACADE": 42,
    "SECRET_POWER": 43,
    "REST": 44,
    "ATTRACT": 45,
    "THIEF": 46,
    "STEEL_WING": 47,
    "SKILL_SWAP": 48,
    "SNATCH": 49,
    "OVERHEAT": 50,
}

LEGACY_TM_PATTERN = re.compile(
    r"\bITEM_TM_([A-Z0-9_]+)\b"
)


def _normalise_legacy_tm_references():
    """Replace Emerald move-based TM aliases in build inputs with TM numbers."""
    files = []

    for directory in (
        ROOT / "data/maps",
        ROOT / "data/scripts",
    ):
        if not directory.exists():
            continue

        files.extend(directory.rglob("*.inc"))
        files.extend(directory.rglob("*.json"))

    # This quiz reward is compiled C data rather than a map/script file.
    files.append(ROOT / "src/data/lilycove_lady.h")

    changed_occurrences = 0
    changed_files = 0

    def replace(match):
        nonlocal changed_occurrences
        slot = EMERALD_TM_SLOTS.get(match.group(1))

        if slot is None:
            return match.group(0)

        changed_occurrences += 1
        return f"ITEM_TM{slot:02d}"

    for filepath in sorted(set(files)):
        if not filepath.exists():
            continue

        text = filepath.read_text(
            encoding="utf-8",
            errors="replace",
        )
        before = changed_occurrences
        updated = LEGACY_TM_PATTERN.sub(replace, text)

        if changed_occurrences == before:
            continue

        filepath.write_text(
            updated,
            encoding="utf-8",
        )
        changed_files += 1

    print(
        f"Normalised {changed_occurrences} legacy TM reference(s) "
        f"across {changed_files} files."
    )

    return changed_occurrences, changed_files


# ============================================================
# GENERIC TOKEN RESTORATION
# ============================================================

def _restore_pattern_in_file(
    clean_file,
    working_file,
    pattern,
    description,
):
    """
    Restore only the regex capture group named 'value' from the
    packaged clean baseline into the corresponding occurrence in
    the working file.

    Everything else in the working file is preserved.
    """

    clean_text = clean_file.read_text(
        encoding="utf-8"
    )

    working_text = working_file.read_text(
        encoding="utf-8"
    )

    regex = re.compile(
        pattern,
        re.MULTILINE,
    )

    clean_matches = list(
        regex.finditer(clean_text)
    )

    if not clean_matches:
        return 0

    working_matches = list(
        regex.finditer(working_text)
    )

    # The optional Running Shoes gift is added after baseline restoration.
    # It must not shift the positional pairing of the ordinary script gifts
    # on the following run (or when item randomisation restores rewards).
    if working_file == ROOT / "data/maps/LittlerootTown/scripts.inc":
        bonus_start = working_text.find("@ RANDOMIZER MOM BONUS START")
        bonus_end = working_text.find("@ RANDOMIZER MOM BONUS END")
        if (bonus_start < 0) != (bonus_end < 0):
            raise RuntimeError("Incomplete Mom bonus in Littleroot script")
        if bonus_start >= 0:
            working_matches = [
                match for match in working_matches
                if not (bonus_start < match.start() < bonus_end)
            ]

    if len(clean_matches) != len(working_matches):
        raise RuntimeError(
            f"Cannot safely restore {description}:\n"
            f"{working_file.relative_to(ROOT)}\n\n"
            f"Baseline occurrences: {len(clean_matches)}\n"
            f"Working occurrences:  {len(working_matches)}\n\n"
            "The file structure differs from the packaged baseline, so "
            "the randomizer is stopping rather than overwrite unrelated "
            "permanent edits."
        )

    replacements = []

    for clean_match, working_match in zip(
        clean_matches,
        working_matches,
    ):
        clean_value = clean_match.group("value")
        working_value = working_match.group("value")

        if clean_value == working_value:
            continue

        replacements.append(
            (
                working_match.start("value"),
                working_match.end("value"),
                clean_value,
            )
        )

    # Work backwards so string offsets remain valid.
    for start, end, value in reversed(replacements):
        working_text = (
            working_text[:start]
            + value
            + working_text[end:]
        )

    if replacements:
        working_file.write_text(
            working_text,
            encoding="utf-8",
        )

    return len(replacements)


def _restore_directory_patterns(
    relative_directory,
    filename_pattern,
    patterns,
):
    """
    Compare packaged baseline files with working game files.

    Only regex capture group 'value' is restored.
    Whole map/script files are never copied into the game.
    """

    clean_dir = BASELINE_ROOT / relative_directory

    if not clean_dir.exists():
        raise RuntimeError(
            "Packaged baseline directory missing:\n"
            f"{clean_dir}\n\n"
            "Run randomizer/prepare_baseline.py once during development."
        )

    changed = 0
    changed_files = set()

    for clean_file in sorted(
        clean_dir.rglob(filename_pattern)
    ):
        relative_file = clean_file.relative_to(
            BASELINE_ROOT
        )

        working_file = ROOT / relative_file

        if not working_file.exists():
            continue

        file_changes = 0

        for pattern, description in patterns:
            file_changes += _restore_pattern_in_file(
                clean_file,
                working_file,
                pattern,
                description,
            )

        if file_changes:
            changed += file_changes
            changed_files.add(relative_file)

    return changed, changed_files


# ============================================================
# NPC-TRADE COMPONENT SCRIPT GIFTS
# ============================================================

NPC_TRADE_GIFT_FILES = {
    Path("data/maps/Route119_WeatherInstitute_2F/scripts.inc"): (
        (
            r"^\s*setvar\s+VAR_TEMP_TRANSFERRED_SPECIES\s*,\s*"
            r"(?P<value>SPECIES_[A-Z0-9_]+)",
            "Weather Institute gift transfer species",
        ),
        (
            r"^\s*givemon\s+"
            r"(?P<value>SPECIES_[A-Z0-9_]+)"
            r"\s*,\s*25\s*,\s*ITEM_MYSTIC_WATER",
            "Weather Institute gift species",
        ),
        (
            r"^\s*bufferspeciesname\s+STR_VAR_1\s*,\s*"
            r"(?P<value>SPECIES_[A-Z0-9_]+)",
            "Weather Institute gift display species",
        ),
        (
            r'^\s*\.string\s+"\{PLAYER\} received '
            r'(?P<value>[^!"\r\n]+)!\$"',
            "Weather Institute gift display name",
        ),
        (
            r"^(?:Route119_WeatherInstitute_2F_"
            r"Text_PokemonChangesWithWeather:)\r?\n"
            r"(?P<value>(?:^[ \t]*\.string[^\r\n]*\r?\n){1,4})",
            "Weather Institute post-gift explanation",
        ),
    ),
    Path("data/maps/MossdeepCity_StevensHouse/scripts.inc"): (
        (
            r"^\s*setvar\s+VAR_TEMP_TRANSFERRED_SPECIES\s*,\s*"
            r"(?P<value>SPECIES_[A-Z0-9_]+)",
            "Steven's gift transfer species",
        ),
        (
            r"^\s*givemon\s+"
            r"(?P<value>SPECIES_[A-Z0-9_]+)"
            r"\s*,\s*5\b",
            "Steven's gift species",
        ),
        (
            r"^\s*bufferspeciesname\s+STR_VAR_[12]\s*,\s*"
            r"(?P<value>SPECIES_[A-Z0-9_]+)",
            "Steven's gift display species",
        ),
        (
            r'^\s*\.string\s+"It contained the POKéMON\\n"\r?\n'
            r'^\s*\.string\s+"(?P<value>[^"\r\n]+)\.\\p"',
            "Steven's Poké Ball gift display name",
        ),
        (
            r'^\s*\.string\s+"\{PLAYER\} obtained a '
            r'(?P<value>[^\."\r\n]+)\.\$"',
            "Steven's obtained-gift display name",
        ),
        (
            r'^\s*\.string\s+"Inside it is a '
            r'(?P<value>[^,"\r\n]+), my favorite\\n"',
            "Steven's letter gift display name",
        ),
    ),
}

NPC_TRADE_GIFT_BUFFER_PATTERN = re.compile(
    r"^[ \t]*@ RANDOMIZER_NPC_TRADE_GIFT_BUFFER_BEGIN\r?\n"
    r"^[ \t]*bufferspeciesname\s+STR_VAR_3\s*,\s*"
    r"SPECIES_[A-Z0-9_]+\r?\n"
    r"^[ \t]*@ RANDOMIZER_NPC_TRADE_GIFT_BUFFER_END\r?\n",
    re.MULTILINE,
)


def restore_npc_trade_gifts():
    """Restore the two map gifts owned by NPC trade randomisation."""

    print("Restoring clean NPC trade gift values...")

    changed = 0
    changed_files = set()

    for relative_path, patterns in NPC_TRADE_GIFT_FILES.items():
        clean_file = BASELINE_ROOT / relative_path
        working_file = ROOT / relative_path

        if not clean_file.exists():
            raise RuntimeError(
                "Packaged NPC gift baseline missing:\n"
                f"{clean_file}"
            )

        if not working_file.exists():
            raise RuntimeError(
                "NPC gift source file missing:\n"
                f"{working_file}"
            )

        working_text = working_file.read_text(
            encoding="utf-8"
        )
        working_text, removed_buffers = (
            NPC_TRADE_GIFT_BUFFER_PATTERN.subn(
                "",
                working_text,
            )
        )

        if removed_buffers:
            working_file.write_text(
                working_text,
                encoding="utf-8",
            )

        file_changes = removed_buffers

        for pattern, description in patterns:
            file_changes += _restore_pattern_in_file(
                clean_file,
                working_file,
                pattern,
                description,
            )

        if file_changes:
            changed += file_changes
            changed_files.add(relative_path)

    print(
        f"Restored {changed} NPC trade gift value(s) "
        f"across {len(changed_files)} files."
    )

    return changed


# ============================================================
# STATIC ENCOUNTERS
# ============================================================

STATIC_PATTERNS = [
    (
        r"^\s*setwildbattle\s+"
        r"(?P<value>SPECIES_[A-Z0-9_]+)"
        r"\s*,",
        "static battle species",
    ),
    (
        r"^\s*seteventmon\s+"
        r"(?P<value>SPECIES_[A-Z0-9_]+)"
        r"\s*,",
        "fateful static battle species",
    ),
    (
        r"^\s*playmoncry\s+"
        r"(?P<value>SPECIES_[A-Z0-9_]+)"
        r"\s*,",
        "static encounter cry species",
    ),
    (
        r"^\s*setvar\s+VAR_0x8004\s*,\s*"
        r"(?P<value>SPECIES_[A-Z0-9_]+)",
        "static encounter species variable",
    ),
    (
        r"^\s*setvar\s+VAR_TEMP_4\s*,\s*"
        r"(?P<value>SPECIES_[A-Z0-9_]+)",
        "dynamic static encounter species variable",
    ),
]


TV_ROAMER_FILE = ROOT / "src/roamer.c"
FOSSIL_REVIVAL_FILE = (
    ROOT
    / "data/maps/RustboroCity_DevonCorp_2F/scripts.inc"
)

FOSSIL_REVIVAL_SPECIES = {
    "Helix": "SPECIES_OMANYTE",
    "Dome": "SPECIES_KABUTO",
    "OldAmber": "SPECIES_AERODACTYL",
    "Root": "SPECIES_LILEEP",
    "Claw": "SPECIES_ANORITH",
    "Armor": "SPECIES_SHIELDON",
    "Skull": "SPECIES_CRANIDOS",
    "Cover": "SPECIES_TIRTOUGA",
    "Plume": "SPECIES_ARCHEN",
    "Jaw": "SPECIES_TYRUNT",
    "Sail": "SPECIES_AMAURA",
    "Bird": "SPECIES_DRACOZOLT",
    "Dino": "SPECIES_ARCTOZOLT",
    "Drake": "SPECIES_DRACOVISH",
    "Fish": "SPECIES_ARCTOVISH",
}

TV_ROAMER_RED_PATTERN = re.compile(
    r"(?P<prefix>"
    r"if\s*\(gSpecialVar_0x8004\s*==\s*0\)"
    r"[^\r\n]*\r?\n\s*"
    r"TryAddRoamer\("
    r")"
    r"(?P<value>SPECIES_[A-Z0-9_]+)"
    r"(?P<suffix>\s*,\s*40\s*\);)"
)

TV_ROAMER_BLUE_PATTERN = re.compile(
    r"(?P<prefix>"
    r"\belse\s*\r?\n\s*"
    r"TryAddRoamer\("
    r")"
    r"(?P<value>SPECIES_[A-Z0-9_]+)"
    r"(?P<suffix>\s*,\s*40\s*\);)"
)


def _restore_tv_roamer_species():
    """Restore the two Hall-of-Fame television roamer choices."""

    if not TV_ROAMER_FILE.exists():
        raise RuntimeError(
            "Cannot restore television roamer species; missing:\n"
            f"{TV_ROAMER_FILE}"
        )

    text = TV_ROAMER_FILE.read_text(
        encoding="utf-8"
    )
    replacements = (
        (
            TV_ROAMER_RED_PATTERN,
            "SPECIES_LATIAS",
            "red television roamer",
        ),
        (
            TV_ROAMER_BLUE_PATTERN,
            "SPECIES_LATIOS",
            "blue television roamer",
        ),
    )
    changed = 0

    for pattern, clean_species, description in replacements:
        matches = list(pattern.finditer(text))

        if len(matches) != 1:
            raise RuntimeError(
                f"Cannot safely restore the {description} in "
                "src/roamer.c.\n\n"
                f"Expected exactly 1 matching InitRoamer branch; found "
                f"{len(matches)}."
            )

        match = matches[0]

        if match.group("value") == clean_species:
            continue

        text = (
            text[:match.start("value")]
            + clean_species
            + text[match.end("value"):]
        )
        changed += 1

    if changed:
        TV_ROAMER_FILE.write_text(
            text,
            encoding="utf-8",
        )

    return changed


def _restore_fossil_revival_species():
    """Restore species in Devon's normal or all-fossil revival scripts."""

    if not FOSSIL_REVIVAL_FILE.exists():
        return 0

    text = FOSSIL_REVIVAL_FILE.read_text(
        encoding="utf-8"
    )

    changed = 0

    if "@ RANDOMIZER_ALL_FOSSILS_BEGIN" not in text:
        family_species = {
            "Lileep": "SPECIES_LILEEP",
            "Anorith": "SPECIES_ANORITH",
        }

        for family, clean_species in family_species.items():
            block_pattern = re.compile(
                rf"(?P<header>^"
                rf"RustboroCity_DevonCorp_2F_EventScript_"
                rf"[A-Za-z0-9_]*{family}[A-Za-z0-9_]*::\r?\n)"
                rf"(?P<body>.*?)"
                rf"(?=^[A-Za-z0-9_]+::|\Z)",
                re.MULTILINE | re.DOTALL,
            )

            def restore_block(match):
                nonlocal changed
                body = match.group("body")

                def restore_species(species_match):
                    nonlocal changed

                    if species_match.group(0) != clean_species:
                        changed += 1

                    return clean_species

                body = re.sub(
                    r"SPECIES_[A-Z0-9_]+",
                    restore_species,
                    body,
                )
                return match.group("header") + body

            text = block_pattern.sub(restore_block, text)

        if changed:
            FOSSIL_REVIVAL_FILE.write_text(
                text,
                encoding="utf-8",
            )

        return changed

    for label, clean_species in FOSSIL_REVIVAL_SPECIES.items():
        pattern = re.compile(
            rf"(?P<prefix>"
            rf"Randomizer_Fossil_EventScript_SetSpecies{label}::"
            rf"\r?\n\s*setvar\s+VAR_TEMP_1\s*,\s*"
            rf")"
            rf"(?P<value>SPECIES_[A-Z0-9_]+)"
        )
        matches = list(pattern.finditer(text))

        if len(matches) != 1:
            raise RuntimeError(
                "Cannot safely restore the all-fossil revival mapping for "
                f"{label}. Expected 1 matching Devon script entry; found "
                f"{len(matches)}."
            )

        match = matches[0]

        if match.group("value") == clean_species:
            continue

        text = (
            text[:match.start("value")]
            + clean_species
            + text[match.end("value"):]
        )
        changed += 1

    if changed:
        FOSSIL_REVIVAL_FILE.write_text(
            text,
            encoding="utf-8",
        )

    return changed


def restore_static_encounters(
    include_npc_trade_gifts=True,
):
    print(
        "Restoring clean static encounter values..."
    )

    total = 0
    files = set()

    for directory in (
        Path("data/maps"),
        Path("data/scripts"),
    ):
        count, changed_files = (
            _restore_directory_patterns(
                directory,
                "*.inc",
                STATIC_PATTERNS,
            )
        )

        total += count
        files.update(changed_files)

    roamer_changes = _restore_tv_roamer_species()
    total += roamer_changes

    if roamer_changes:
        files.add(Path("src/roamer.c"))

    fossil_changes = _restore_fossil_revival_species()
    total += fossil_changes

    if fossil_changes:
        files.add(
            Path("data/maps/RustboroCity_DevonCorp_2F/scripts.inc")
        )

    print(
        f"Restored {total} static encounter values "
        f"across {len(files)} files."
    )

    # The master calls this function once during its universal clean restore.
    # The static component calls it again later, after NPC trades have already
    # run, so that second call must explicitly opt out rather than undoing the
    # newly randomised Castform and Beldum gifts.
    if include_npc_trade_gifts:
        print()
        restore_npc_trade_gifts()


# ============================================================
# EGG GIFTS
# ============================================================

EGG_PATTERNS = [
    (
        r"^\s*giveegg\s+"
        r"(?P<value>SPECIES_[A-Z0-9_]+)",
        "gift egg species",
    ),
]


def restore_egg_gifts():
    print(
        "Restoring clean gift egg values..."
    )

    total = 0
    files = set()

    for directory in (
        Path("data/maps"),
        Path("data/scripts"),
    ):
        count, changed_files = (
            _restore_directory_patterns(
                directory,
                "*.inc",
                EGG_PATTERNS,
            )
        )

        total += count
        files.update(changed_files)

    print(
        f"Restored {total} gift egg values "
        f"across {len(files)} files."
    )


# ============================================================
# LILYCOVE TM SHOP
# ============================================================
#
# The optional TM-shop feature owns only the two Pokémart inventory blocks
# below. Restoring those blocks on every run means:
#
#   Run 1: Add all TMs = enabled
#   Run 2: Add all TMs = disabled
#
# correctly returns the shop to the packaged baseline without replacing the
# rest of Lilycove's scripts.inc (which may contain permanent game changes).
# ============================================================

LILYCOVE_SHOP_RELATIVE_PATH = Path(
    "data/maps/LilycoveCity_DepartmentStore_4F/scripts.inc"
)

LILYCOVE_TM_SHOP_LABELS = (
    "LilycoveCity_DepartmentStore_4F_Pokemart_AttackTMs",
    "LilycoveCity_DepartmentStore_4F_Pokemart_DefenseTMs",
)

LILYCOVE_EVOLUTION_SHOP_RELATIVE_PATH = Path(
    "data/maps/LilycoveCity_DepartmentStore_2F/scripts.inc"
)

LILYCOVE_EVOLUTION_SHOP_LABELS = (
    "LilycoveCity_DepartmentStore_2F_Pokemart1",
    "LilycoveCity_DepartmentStore_2F_Pokemart2",
)

SCRIPT_LABEL_PATTERN = re.compile(
    r"(?m)^([A-Za-z0-9_]+):{1,2}\s*$"
)


def _get_script_label_block(text, label):
    """Return the content range for one single-colon script label."""
    match = re.search(
        rf"(?m)^{re.escape(label)}:\s*$",
        text,
    )

    if not match:
        raise RuntimeError(
            f"Could not find Lilycove TM shop label: {label}"
        )

    start = match.end()
    next_label = SCRIPT_LABEL_PATTERN.search(
        text,
        start,
    )
    end = (
        next_label.start()
        if next_label
        else len(text)
    )

    return start, end, text[start:end]


def _restore_shop_inventory_blocks(
    relative_path,
    labels,
    description,
):
    """Restore selected Pokémart inventory blocks from packaged baseline."""
    clean_file = (
        BASELINE_ROOT
        / relative_path
    )
    working_file = (
        ROOT
        / relative_path
    )

    if not clean_file.exists():
        raise RuntimeError(
            f"Packaged {description} reference is missing:\n"
            f"{clean_file}"
        )

    if not working_file.exists():
        raise RuntimeError(
            f"Working {description} script is missing:\n"
            f"{working_file}"
        )

    clean_text = clean_file.read_text(
        encoding="utf-8"
    )
    working_text = working_file.read_text(
        encoding="utf-8"
    )

    replacements = []

    for label in labels:
        _, _, clean_block = _get_script_label_block(
            clean_text,
            label,
        )

        start, end, working_block = (
            _get_script_label_block(
                working_text,
                label,
            )
        )

        if working_block != clean_block:
            replacements.append(
                (
                    start,
                    end,
                    clean_block,
                )
            )

    for start, end, clean_block in sorted(
        replacements,
        key=lambda item: item[0],
        reverse=True,
    ):
        working_text = (
            working_text[:start]
            + clean_block
            + working_text[end:]
        )

    if replacements:
        working_file.write_text(
            working_text,
            encoding="utf-8",
        )

    print(
        f"Restored {len(replacements)} {description} inventory block(s)."
    )


def restore_lilycove_tm_shop():
    """Restore Lilycove 4F's two TM inventories."""
    _restore_shop_inventory_blocks(
        LILYCOVE_SHOP_RELATIVE_PATH,
        LILYCOVE_TM_SHOP_LABELS,
        "Lilycove TM shop",
    )


def restore_lilycove_evolution_shop():
    """Restore Lilycove 2F's two inventories used by the evolution-item option."""
    _restore_shop_inventory_blocks(
        LILYCOVE_EVOLUTION_SHOP_RELATIVE_PATH,
        LILYCOVE_EVOLUTION_SHOP_LABELS,
        "Lilycove evolution shop",
    )


# ============================================================
# FOUND ITEMS - MAP JSON
# ============================================================

MAP_ITEM_PATTERNS = [
    (
        r'"trainer_sight_or_berry_tree_id"\s*:\s*"'
        r'(?P<value>ITEM_[A-Z0-9_]+)"',
        "map item ball",
    ),
    (
        r'"hidden_item"\s*:\s*"'
        r'(?P<value>ITEM_[A-Z0-9_]+)"',
        "hidden map item",
    ),
    (
        r'"item"\s*:\s*"'
        r'(?P<value>ITEM_[A-Z0-9_]+)"',
        "map item",
    ),
]


# ============================================================
# FOUND ITEMS - SCRIPT COMMANDS
# ============================================================
#
# Shops are deliberately not included.
# ============================================================

SCRIPT_ITEM_PATTERNS = [
    (
        r"^\s*giveitem\s+"
        r"(?P<value>ITEM_[A-Z0-9_]+)",
        "script giveitem",
    ),
    (
        r"^\s*msgreceiveditem\s+[^,\n]+,\s*"
        r"(?P<value>ITEM_[A-Z0-9_]+)",
        "script received item message",
    ),
    (
        r"^\s*additem\s+"
        r"(?P<value>ITEM_[A-Z0-9_]+)",
        "script additem",
    ),
    (
        r"^\s*itemball\s+"
        r"(?P<value>ITEM_[A-Z0-9_]+)",
        "script item ball",
    ),
    (
        r"^\s*hiddenitem\s+"
        r"(?P<value>ITEM_[A-Z0-9_]+)",
        "script hidden item",
    ),
]


FLOWER_SHOP_SCRIPT = Path(
    "data/maps/Route104_PrettyPetalFlowerShop/scripts.inc"
)
FLOWER_GIFT_MARKER = "@ RANDOMIZER FLOWER SHOP GIFT"


def _restore_flower_shop_berry_gift():
    """Restore the woman's special berry command before ordinary gift checks."""
    path = ROOT / FLOWER_SHOP_SCRIPT
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    if FLOWER_GIFT_MARKER not in text:
        return
    baseline = BASELINE_ROOT / FLOWER_SHOP_SCRIPT
    if not baseline.exists():
        raise RuntimeError(f"Missing flower-shop baseline: {baseline}")
    original = baseline.read_text(encoding="utf-8")
    original_gifts = re.findall(
        r"(?m)^[ \t]*giverandomberry BERRY_ID_CHERI, BERRY_ID_PERSIM$",
        original,
    )
    pattern = re.compile(
        r"(?m)^[ \t]*" + re.escape(FLOWER_GIFT_MARKER)
        + r"\n[ \t]*giveitem ITEM_[A-Z0-9_]+$"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1 or len(original_gifts) != 1:
        raise RuntimeError(f"Cannot safely restore flower-shop gift: {path}")
    path.write_text(
        pattern.sub(lambda _: original_gifts[0], text, count=1),
        encoding="utf-8",
    )


def restore_found_items():
    print(
        "Restoring clean found-item values..."
    )

    # A transformed berry tree is an extra item-ball match. Restore its
    # original object before matching the baseline item-ball occurrences.
    restore_berry_item_events()
    _restore_flower_shop_berry_gift()

    total = 0
    files = set()

    count, changed_files = (
        _restore_directory_patterns(
            Path("data/maps"),
            "map.json",
            MAP_ITEM_PATTERNS,
        )
    )

    total += count
    files.update(changed_files)

    for directory in (
        Path("data/maps"),
        Path("data/scripts"),
    ):
        count, changed_files = (
            _restore_directory_patterns(
                directory,
                "*.inc",
                SCRIPT_ITEM_PATTERNS,
            )
        )

        total += count
        files.update(changed_files)

    print(
        f"Restored {total} found-item values "
        f"across {len(files)} files."
    )

    # Always run this after baseline restoration.  randomize_items.py invokes
    # restore_found_items() again in-process, so keeping the compatibility pass
    # here also prevents that second restore from reintroducing invalid aliases.
    _normalise_legacy_tm_references()


# ============================================================
# MANUAL TEST
# ============================================================

if __name__ == "__main__":
    if not BASELINE_ROOT.exists():
        raise RuntimeError(
            "Packaged baseline does not exist:\n"
            f"{BASELINE_ROOT}\n\n"
            "Run randomizer/prepare_baseline.py first."
        )

    restore_static_encounters()
    restore_egg_gifts()
    restore_found_items()

    print()
    print(
        "Packaged map-data restoration complete."
    )
