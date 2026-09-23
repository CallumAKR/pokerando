#!/usr/bin/env python3

import json
import random
import re
import sys
from pathlib import Path
from clean_map_restore import restore_found_items
from berry_item_events import TREE_SCRIPT, berry_flag_for_index
from fossil_options import CONFIG_FILE, FOSSILS

ROOT = Path(__file__).resolve().parent.parent

ITEMS_FILE = ROOT / "src/data/items.h"
ITEM_CONSTANTS_FILE = ROOT / "include/constants/items.h"
MAPS_DIR = ROOT / "data/maps"
SCRIPTS_DIR = ROOT / "data/scripts"

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

include_game_corner = "--include-game-corner" in sys.argv[2:]

fossil_options = {
    "enable_all_fossils": False,
}

if CONFIG_FILE.exists():
    try:
        loaded_fossil_options = json.loads(
            CONFIG_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Could not read randomizer/fossil_options.json. Run the GUI "
            "again so it can regenerate the fossil settings."
        ) from exc

    if isinstance(loaded_fossil_options, dict):
        for key in fossil_options:
            fossil_options[key] = bool(
                loaded_fossil_options.get(key, False)
            )

enable_all_fossils = fossil_options["enable_all_fossils"]

FOSSIL_ITEMS = {
    item
    for item, _, _ in FOSSILS
}

rng = random.Random(seed)

print(f"Item randomizer seed: {seed}")

restore_found_items()

# ============================================================
# READ ITEM DATABASE
# ============================================================

items_text = ITEMS_FILE.read_text(
    encoding="utf-8"
)

item_header_pattern = re.compile(
    r"^\s*\[(ITEM_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE
)

item_headers = list(
    item_header_pattern.finditer(items_text)
)

item_info = {}

for index, match in enumerate(item_headers):

    item = match.group(1)

    start = match.start()

    end = (
        item_headers[index + 1].start()
        if index + 1 < len(item_headers)
        else len(items_text)
    )

    block = items_text[start:end]

    pocket_match = re.search(
        r"\.pocket\s*=\s*"
        r"(POCKET_[A-Z0-9_]+)",
        block
    )

    pocket = (
        pocket_match.group(1)
        if pocket_match
        else None
    )

    item_info[item] = {
        "pocket": pocket,
        "block": block,
    }

# Map legacy/source aliases (for example ITEM_X_DEFEND) to the canonical item
# definition used by src/data/items.h.  Without this, aliased map pickups look
# undefined and are incorrectly protected from randomisation.
item_aliases = dict(
    re.findall(
        r"\b(ITEM_[A-Z0-9_]+)\s*=\s*(ITEM_[A-Z0-9_]+)\b",
        ITEM_CONSTANTS_FILE.read_text(encoding="utf-8"),
    )
)


def resolve_item_alias(item):
    seen = set()
    while item in item_aliases and item not in seen:
        seen.add(item)
        item = item_aliases[item]
    return item

print(
    f"Found {len(item_info)} "
    f"defined items."
)

# ============================================================
# BLACKLISTING
# ============================================================

def is_blacklisted(item):

    if item == "ITEM_NONE":
        return True

    # -------------------------
    # HMs
    # -------------------------

    if item.startswith("ITEM_HM_"):
        return True

    # Defensive support if this checkout ever uses
    # ITEM_HM01 style names.
    if re.match(r"ITEM_HM[0-9]", item):
        return True

    # clean_map_restore normalises Emerald's move-based TM aliases to stable
    # numbered slots so every selectable TM catalogue can compile. They are
    # still ordinary, randomisable TMs even though src/data/items.h defines the
    # active catalogue through move-based aliases.
    numbered_tm = re.fullmatch(
        r"ITEM_TM([0-9]{2,3})",
        item,
    )

    if numbered_tm:
        tm_number = int(numbered_tm.group(1))
        return not (1 <= tm_number <= 100)

    # -------------------------
    # BADGES
    # -------------------------

    if "BADGE" in item:
        return True

    # Fossils only enter the general item pool when Devon can revive every
    # possible result. This prevents ordinary item randomisation from creating
    # unusable fossil rewards while the all-fossils option is off.
    if item in FOSSIL_ITEMS:
        return not enable_all_fossils

    # -------------------------
    # KEY ITEMS
    # -------------------------

    info = item_info.get(resolve_item_alias(item))

    if info is None:
        return True

    if info["pocket"] == "POCKET_KEY_ITEMS":
        return True

    # Z-Crystals only work through the Z-Move battle mechanic and should not
    # consume random pickup/reward slots in an ordinary playthrough.
    if "ITEM_TYPE_Z_CRYSTAL" in info["block"]:
        return True

    # An item with no detected pocket is suspicious,
    # so don't put it into the random pool.
    if info["pocket"] is None:
        return True

    return False


def is_protected_source_item(item):
    """
    Return True when an existing reward must not be replaced.

    Fossil rewards themselves are safe randomisation locations even when
    fossils are excluded from the replacement pool. This lets Root/Claw
    rewards become ordinary items while all-fossil revival is disabled.
    """

    return (
        is_blacklisted(item)
        and item not in FOSSIL_ITEMS
    )


random_item_pool = sorted(
    item
    for item in item_info
    if not is_blacklisted(item)
)

fossil_item_pool = sorted(
    item
    for item in FOSSIL_ITEMS
    if item in item_info
)

if enable_all_fossils:
    missing_fossils = sorted(
        FOSSIL_ITEMS - set(fossil_item_pool)
    )

    if missing_fossils:
        raise RuntimeError(
            "All-fossil revival is enabled, but these fossil item "
            "definitions are missing:\n  "
            + "\n  ".join(missing_fossils)
        )

print(
    f"Eligible random item pool: "
    f"{len(random_item_pool)}"
)

if len(random_item_pool) < 100:
    raise RuntimeError(
        "Item pool is suspiciously small. "
        "Stopping before modifying maps."
    )

# ============================================================
# RANDOMIZATION
# ============================================================

changed_items = 0
skipped_protected_items = 0
changed_maps = 0
converted_berry_trees = 0



def choose_replacement(original):
    candidates = [
        item
        for item in random_item_pool
        if item != original
    ]

    if not candidates:
        candidates = random_item_pool

    return rng.choice(candidates)


# ============================================================
# NPC / SCRIPT REWARDS
# ============================================================
#
# The default item randomizer includes ordinary script gifts while protecting
# progression items through the same item database rules used for field items.
#
# `giveitem` is treated as a direct gift.
# `msgreceiveditem` + nearby matching `additem` are treated as one gift pair so
# both the displayed item and the actual received item stay consistent.
# Bare `additem` commands are NOT randomized by default because they are often
# internal story / transfer logic. The one deliberate exception is Game Corner
# prize scripts when --include-game-corner is supplied.
# ============================================================

GIVEITEM_PATTERN = re.compile(
    r"(?m)^(?P<prefix>\s*giveitem\s+)"
    r"(?P<item>ITEM_[A-Z0-9_]+)"
)

MSGRECEIVED_PATTERN = re.compile(
    r"(?m)^(?P<prefix>\s*msgreceiveditem\s+[^,\n]+,\s*)"
    r"(?P<item>ITEM_[A-Z0-9_]+)"
)

ADDITEM_PATTERN = re.compile(
    r"(?m)^(?P<prefix>\s*additem\s+)"
    r"(?P<item>ITEM_[A-Z0-9_]+)"
)

FLOWER_SHOP_GIFT = re.compile(
    r"(?m)^(?P<indent>[ \t]*)giverandomberry "
    r"BERRY_ID_CHERI, BERRY_ID_PERSIM$"
)


def is_game_corner_file(filepath):
    """Return True for map/script files belonging to a Game Corner."""
    normalized = filepath.as_posix().lower()
    return (
        "gamecorner" in normalized
        or "game_corner" in normalized
    )


def _replace_item_matches(text, replacements):
    """Apply (start, end, value) replacements from back to front."""
    for start, end, value in sorted(
        replacements,
        key=lambda entry: entry[0],
        reverse=True,
    ):
        text = text[:start] + value + text[end:]

    return text


def randomize_script_rewards(filepath):
    """
    Randomize safe NPC/script gifts in one .inc file.

    Returns (changed_occurrences, protected_occurrences, changed_file).
    """
    text = filepath.read_text(
        encoding="utf-8",
        errors="replace",
    )

    # Mom's optional running-shoes bonus is a fixed quantity of Ultra Balls,
    # even when ordinary NPC gifts are randomised. Protect only the marked
    # block so other Littleroot rewards remain eligible.
    mom_bonus_start = text.find("@ RANDOMIZER MOM BONUS START")
    mom_bonus_end = text.find("@ RANDOMIZER MOM BONUS END")
    if (mom_bonus_start < 0) != (mom_bonus_end < 0):
        raise RuntimeError(
            f"Incomplete Mom bonus markers in {filepath}"
        )

    replacements = []
    protected = 0
    paired_ranges = []

    # --------------------------------------------------------
    # msgreceiveditem + nearby additem pairs
    # --------------------------------------------------------
    # Some FRLG-style scripts display the reward with msgreceiveditem and then
    # actually add it with additem (or vice versa). Pair equal item constants
    # within a small line window and give both occurrences the same replacement.
    msg_matches = list(
        MSGRECEIVED_PATTERN.finditer(text)
    )
    add_matches = list(
        ADDITEM_PATTERN.finditer(text)
    )
    used_adds = set()

    for msg in msg_matches:
        original = msg.group("item")
        msg_line = text.count("\n", 0, msg.start()) + 1

        candidates = []

        for index, add in enumerate(add_matches):
            if index in used_adds:
                continue

            if add.group("item") != original:
                continue

            add_line = text.count("\n", 0, add.start()) + 1
            distance = abs(add_line - msg_line)

            if distance <= 4:
                candidates.append(
                    (distance, index, add)
                )

        if not candidates:
            continue

        _, index, add = min(candidates)
        used_adds.add(index)

        paired_ranges.extend(
            ((msg.start(), msg.end()), (add.start(), add.end()))
        )

        if is_protected_source_item(original):
            protected += 1
            continue

        replacement = choose_replacement(original)

        replacements.extend(
            (
                (msg.start("item"), msg.end("item"), replacement),
                (add.start("item"), add.end("item"), replacement),
            )
        )

    # --------------------------------------------------------
    # direct giveitem rewards
    # --------------------------------------------------------
    for match in GIVEITEM_PATTERN.finditer(text):
        original = match.group("item")

        if mom_bonus_start >= 0 and mom_bonus_start < match.start() < mom_bonus_end:
            protected += 1
            continue

        if is_protected_source_item(original):
            protected += 1
            continue

        replacement = choose_replacement(original)
        replacements.append(
            (
                match.start("item"),
                match.end("item"),
                replacement,
            )
        )

    # The flower-shop woman uses a native berry-only macro rather than a
    # normal giveitem command. Give her a seed-selected item instead while
    # preserving the daily flag and bag-full behavior of the original script.
    if filepath.parent.name == "Route104_PrettyPetalFlowerShop" and filepath.name == "scripts.inc":
        gifts = list(FLOWER_SHOP_GIFT.finditer(text))
        if len(gifts) != 1:
            raise RuntimeError(f"Expected one flower-shop berry gift: {filepath}")
        match = gifts[0]
        indent = match.group("indent")
        replacement = choose_replacement("ITEM_NONE")
        replacements.append((
            match.start(), match.end(),
            f"{indent}@ RANDOMIZER FLOWER SHOP GIFT\n"
            f"{indent}giveitem {replacement}",
        ))

    # --------------------------------------------------------
    # optional Game Corner bare additem prizes
    # --------------------------------------------------------
    if (
        include_game_corner
        and is_game_corner_file(filepath)
    ):
        paired_add_starts = {
            start
            for start, _ in paired_ranges
        }

        for match in add_matches:
            if match.start() in paired_add_starts:
                continue

            original = match.group("item")

            if is_protected_source_item(original):
                protected += 1
                continue

            replacement = choose_replacement(original)
            replacements.append(
                (
                    match.start("item"),
                    match.end("item"),
                    replacement,
                )
            )

    if not replacements:
        return 0, protected, False

    new_text = _replace_item_matches(
        text,
        replacements,
    )

    filepath.write_text(
        new_text,
        encoding="utf-8",
    )

    return (
        len(replacements),
        protected,
        True,
    )


# ============================================================
# PROCESS ALL MAP.JSON FILES
# ============================================================

for filepath in sorted(
    MAPS_DIR.rglob("map.json")
):

    with filepath.open(
        "r",
        encoding="utf-8"
    ) as fp:

        data = json.load(fp)

    map_name = data.get(
        "name",
        filepath.parent.name
    )

    changed_map = False

    # --------------------------------------------------------
    # VISIBLE ITEM BALLS
    # --------------------------------------------------------

    for event in data.get(
        "object_events",
        []
    ):

        if (
            event.get("script")
            != "Common_EventScript_FindItem"
        ):
            continue

        original = event.get(
            "trainer_sight_or_berry_tree_id"
        )

        if (
            not isinstance(original, str)
            or not original.startswith("ITEM_")
        ):
            continue

        # Never randomize an existing Key Item / HM / Badge.
        #
        # This is what protects things such as the Scanner.
        if is_protected_source_item(original):

            print(
                f"Protected pickup: "
                f"{map_name}: {original}"
            )

            skipped_protected_items += 1
            continue

        replacement = choose_replacement(
            original
        )

        event[
            "trainer_sight_or_berry_tree_id"
        ] = replacement

        changed_items += 1
        changed_map = True

    # Convert every berry plant and bare-soil plot into an item ball. This
    # runs after the ordinary-ball loop so each new pickup gets one roll.
    for event in data.get("object_events", []):
        if event.get("script") != TREE_SCRIPT:
            continue
        event["graphics_id"] = "OBJ_EVENT_GFX_ITEM_BALL"
        event["movement_type"] = "MOVEMENT_TYPE_LOOK_AROUND"
        event["trainer_sight_or_berry_tree_id"] = choose_replacement("ITEM_NONE")
        event["script"] = "Common_EventScript_FindItem"
        event["flag"] = berry_flag_for_index(converted_berry_trees)
        converted_berry_trees += 1
        changed_items += 1
        changed_map = True

    # --------------------------------------------------------
    # HIDDEN ITEMS
    # --------------------------------------------------------

    for event in data.get(
        "bg_events",
        []
    ):

        if (
            event.get("type")
            != "hidden_item"
        ):
            continue

        original = event.get("item")

        if (
            not isinstance(original, str)
            or not original.startswith("ITEM_")
        ):
            continue

        if is_protected_source_item(original):

            print(
                f"Protected hidden item: "
                f"{map_name}: {original}"
            )

            skipped_protected_items += 1
            continue

        replacement = choose_replacement(
            original
        )

        event["item"] = replacement

        changed_items += 1
        changed_map = True

    # --------------------------------------------------------
    # WRITE MAP
    # --------------------------------------------------------

    if changed_map:

        with filepath.open(
            "w",
            encoding="utf-8"
        ) as fp:

            json.dump(
                data,
                fp,
                indent=2
            )

            fp.write("\n")

        changed_maps += 1

# ============================================================
# PROCESS NPC / SCRIPT REWARDS
# ============================================================

changed_script_items = 0
changed_script_files = 0
protected_script_items = 0

for directory in (
    MAPS_DIR,
    SCRIPTS_DIR,
):
    for filepath in sorted(
        directory.rglob("*.inc")
    ):
        (
            item_changes,
            protected_changes,
            file_changed,
        ) = randomize_script_rewards(
            filepath
        )

        changed_script_items += item_changes
        protected_script_items += protected_changes

        if file_changed:
            changed_script_files += 1


# ============================================================
# SUMMARY
# ============================================================

print()
print(
    f"Randomized field/hidden items: "
    f"{changed_items}"
)

print(f"Berry plots converted into item balls: {converted_berry_trees}")

print(
    f"Randomized NPC/script reward occurrences: "
    f"{changed_script_items}"
)

print(
    f"Changed NPC/script files: "
    f"{changed_script_files}"
)

print(
    f"Protected field progression/HM items skipped: "
    f"{skipped_protected_items}"
)

print(
    f"Protected script progression/HM rewards skipped: "
    f"{protected_script_items}"
)

print(
    "Game Corner rewards: "
    + ("included" if include_game_corner else "not included")
)

print(
    "All fossils in item pool: "
    + ("yes" if enable_all_fossils else "no")
)

print(
    f"Changed maps: "
    f"{changed_maps}"
)


print(
    f"Seed: {seed}"
)
