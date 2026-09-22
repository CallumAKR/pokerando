#!/usr/bin/env python3
"""
Optional Lilycove Department Store inventory configuration.

Store options supported here include:

- The active generation's valid TMs -> Lilycove Department Store 4F
- Evolution items / regional postcards / Mega Stones -> Lilycove 2F

The master reset phase restores both affected floors from the packaged baseline
before every run, so either option can be enabled for one seed and disabled for
the next without leaking shop state.

Nothing is changed merely by importing this module.
"""

import re

from runtime_paths import ROOT


ITEMS_FILE = ROOT / "src/data/items.h"
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
TMHM_CONSTANTS_FILE = ROOT / "include/constants/tms_hms.h"

REGIONAL_POSTCARDS = (
    "ITEM_ALOLA_POSTCARD",
    "ITEM_GALAR_POSTCARD",
    "ITEM_HISUI_POSTCARD",
)

TM_SHOP_FILE = (
    ROOT
    / "data/maps"
    / "LilycoveCity_DepartmentStore_4F"
    / "scripts.inc"
)

TM_SHOP_LABELS = (
    "LilycoveCity_DepartmentStore_4F_Pokemart_AttackTMs",
    "LilycoveCity_DepartmentStore_4F_Pokemart_DefenseTMs",
)

EVOLUTION_SHOP_FILE = (
    ROOT
    / "data/maps"
    / "LilycoveCity_DepartmentStore_2F"
    / "scripts.inc"
)

EVOLUTION_SHOP_LABELS = (
    "LilycoveCity_DepartmentStore_2F_Pokemart1",
    "LilycoveCity_DepartmentStore_2F_Pokemart2",
)

ITEM_HEADER_PATTERN = re.compile(
    r"^\s*\[(ITEM_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

ANY_LABEL_PATTERN = re.compile(
    r"(?m)^([A-Za-z0-9_]+):{1,2}\s*$"
)

MART_ITEM_PATTERN = re.compile(
    r"(?m)^\s*(\.[A-Za-z0-9]+)\s+"
    r"(ITEM_[A-Z0-9_]+)\s*$"
)

TRADE_HOLD_ITEM_PATTERN = re.compile(
    r"IF_HOLD_ITEM\s*,\s*"
    r"(ITEM_[A-Z0-9_]+)"
)


def _get_label_block(source, label):
    """Return the content range belonging to one Pokémart inventory label."""
    label_match = re.search(
        rf"(?m)^{re.escape(label)}:\s*$",
        source,
    )

    if not label_match:
        raise RuntimeError(
            f"Could not find shop label: {label}"
        )

    start = label_match.end()

    next_label = ANY_LABEL_PATTERN.search(
        source,
        start,
    )

    end = (
        next_label.start()
        if next_label
        else len(source)
    )

    return (
        start,
        end,
        source[start:end],
    )


def _read_item_blocks():
    """Return ITEM_* -> complete item definition block from items.h."""
    text = ITEMS_FILE.read_text(
        encoding="utf-8",
    )

    headers = list(
        ITEM_HEADER_PATTERN.finditer(
            text
        )
    )

    blocks = {}

    for index, match in enumerate(headers):
        end = (
            headers[index + 1].start()
            if index + 1 < len(headers)
            else len(text)
        )

        blocks[match.group(1)] = (
            text[match.start():end]
        )

    return blocks


def _discover_all_tms(item_blocks):
    """Return active, usable TM items in the compiled catalogue order."""
    source = TMHM_CONSTANTS_FILE.read_text(encoding="utf-8")
    start = source.find("#define FOREACH_TM(F)")
    end = source.find("\n#define FOREACH_HM(F)", start)

    if start < 0 or end < 0:
        raise RuntimeError("Could not read the active FOREACH_TM catalogue.")

    moves = re.findall(r"F\(([A-Z0-9_]+)\)", source[start:end])

    if not moves or len(moves) != len(set(moves)):
        raise RuntimeError("The active TM catalogue is empty or contains duplicates.")

    items = []

    for move in moves:
        item = f"ITEM_TM_{move}"
        block = item_blocks.get(item)

        if block is None:
            raise RuntimeError(f"Active TM has no item definition: {item}")

        if ".pocket = POCKET_TM_HM" not in block:
            raise RuntimeError(f"Active TM is not in the TM/HM pocket: {item}")

        if (
            "sQuestionMarksDesc" in block
            or "gQuestionMarksItemName" in block
            or 'ITEM_NAME("?????")' in block
        ):
            raise RuntimeError(f"Active TM is still a placeholder: {item}")

        items.append(item)

    return items


def _discover_trade_hold_items():
    """
    Return items explicitly used by trade evolutions in species_info.

    This catches held trade items even when their item sort category is simply
    ITEM_TYPE_HELD_ITEM.
    """
    items = set()

    for filepath in sorted(
        SPECIES_DIR.rglob("*.h")
    ):
        text = filepath.read_text(
            encoding="utf-8",
        )

        if "EVO_TRADE" not in text:
            continue

        items.update(
            TRADE_HOLD_ITEM_PATTERN.findall(
                text
            )
        )

    return items


def _discover_evolution_items(
    item_blocks,
):
    """
    Discover non-Mega items required to evolve Pokémon.

    Includes ordinary evolution stones/items, held/use evolution items, and
    held items explicitly referenced by trade evolutions. This covers items
    such as Metal Coat, King's Rock, Electirizer, Magmarizer, Razor Claw,
    Reaper Cloth, and similar evolution requirements.

    Mega Stones and key items are deliberately excluded.
    """
    items = set(
        _discover_trade_hold_items()
    )

    for item, block in item_blocks.items():
        if item == "ITEM_NONE":
            continue

        if item.startswith(
            ("ITEM_TM_", "ITEM_HM_")
        ):
            continue

        if re.search(
            r"\.importance\s*=\s*1",
            block,
        ):
            continue

        if "ITEM_TYPE_MEGA_STONE" in block:
            continue

        if (
            "ITEM_TYPE_EVOLUTION_ITEM"
            in block
            or "gItemEffect_EvoItem"
            in block
            or "EVO_HELD_ITEM_FIELD_FUNC"
            in block
        ):
            items.add(item)

    return sorted(
        item
        for item in items
        if (
            item in item_blocks
            and "ITEM_TYPE_MEGA_STONE"
            not in item_blocks[item]
            and not re.search(
                r"\.importance\s*=\s*1",
                item_blocks[item],
            )
        )
    )


def _discover_mega_stones(
    item_blocks,
):
    """Return all non-key Mega Stones currently defined by the project."""
    return sorted(
        item
        for item, block in item_blocks.items()
        if (
            "ITEM_TYPE_MEGA_STONE"
            in block
            and not re.search(
                r"\.importance\s*=\s*1",
                block,
            )
        )
    )

def _detect_directive(block):
    """Return (indent, inventory directive) from an existing mart block."""
    match = re.search(
        r"(?m)^(\s*)(\.[A-Za-z0-9]+)\s+ITEM_",
        block,
    )

    if not match:
        raise RuntimeError(
            "Could not detect Pokémart item directive."
        )

    return (
        match.group(1),
        match.group(2),
    )


def _read_inventory(block):
    """Return all non-terminator items currently in a mart block."""
    return [
        item
        for _, item
        in MART_ITEM_PATTERN.findall(block)
        if item != "ITEM_NONE"
    ]


def _build_inventory(
    items,
    indent,
    directive,
):
    lines = [
        f"{indent}{directive} {item}"
        for item in items
    ]

    lines.append(
        f"{indent}{directive} ITEM_NONE"
    )

    return (
        "\n"
        + "\n".join(lines)
        + "\n"
    )


def _replace_inventory(
    source,
    label,
    items,
    indent,
    directive,
):
    start, end, _ = (
        _get_label_block(
            source,
            label,
        )
    )

    return (
        source[:start]
        + _build_inventory(
            items,
            indent,
            directive,
        )
        + source[end:]
    )


def _append_split_inventory(
    shop_file,
    labels,
    additions,
    required_event_labels,
    preserve_baseline=True,
):
    """
    Preserve both shops' baseline stock, append new unique stock, then split the
    complete ordered inventory approximately evenly across the two clerks.
    """
    text = shop_file.read_text(
        encoding="utf-8",
    )

    _, _, first_block = (
        _get_label_block(
            text,
            labels[0],
        )
    )

    _, _, second_block = (
        _get_label_block(
            text,
            labels[1],
        )
    )

    baseline_items = (
        _read_inventory(first_block)
        + _read_inventory(second_block)
    )

    ordered_items = (
        list(dict.fromkeys(baseline_items))
        if preserve_baseline
        else []
    )

    existing = set(
        ordered_items
    )

    for item in additions:
        if item not in existing:
            ordered_items.append(item)
            existing.add(item)

    if not ordered_items:
        raise RuntimeError(
            "Shop configuration produced an empty inventory."
        )

    indent, directive = (
        _detect_directive(
            first_block
        )
    )

    split = (
        len(ordered_items) + 1
    ) // 2

    first_shop = ordered_items[:split]
    second_shop = ordered_items[split:]

    # Replace the later label first so offsets are irrelevant.
    text = _replace_inventory(
        text,
        labels[1],
        second_shop,
        indent,
        directive,
    )

    text = _replace_inventory(
        text,
        labels[0],
        first_shop,
        indent,
        directive,
    )

    for required in (
        tuple(required_event_labels)
        + (
            labels[0] + ":",
            labels[1] + ":",
        )
    ):
        if required not in text:
            raise RuntimeError(
                "Shop safety check failed. "
                f"Missing label: {required}"
            )

    shop_file.write_text(
        text,
        encoding="utf-8",
    )

    return len(ordered_items)


def add_all_tms_to_lilycove_shop():
    """Set the two Lilycove 4F clerks to the active valid TM catalogue."""
    item_blocks = _read_item_blocks()
    tm_items = _discover_all_tms(
        item_blocks
    )

    if len(tm_items) < 50:
        raise RuntimeError(
            "Found suspiciously few TMs. "
            "Stopping before modifying Lilycove 4F."
        )

    total = _append_split_inventory(
        TM_SHOP_FILE,
        TM_SHOP_LABELS,
        tm_items,
        (
            "LilycoveCity_DepartmentStore_4F_EventScript_ClerkLeft::",
            "LilycoveCity_DepartmentStore_4F_EventScript_ClerkRight::",
        ),
        preserve_baseline=False,
    )

    print(
        f"Added all {len(tm_items)} TMs to Lilycove 4F "
        f"({total} total unique shop items)."
    )

    return len(tm_items)


def configure_lilycove_evolution_shop(
    add_evolution_items=False,
    add_regional_postcards=False,
    add_mega_stones=False,
):
    """
    Add selected evolution-related stock to Lilycove 2F.

    All three groups are independent options. Existing baseline 2F stock is
    preserved.
    """
    if not (
        add_evolution_items
        or add_regional_postcards
        or add_mega_stones
    ):
        return {
            "evolution_items": 0,
            "regional_postcards": 0,
            "mega_stones": 0,
            "total_shop_items": 0,
        }

    item_blocks = _read_item_blocks()

    evolution_items = []
    regional_postcards = []
    mega_stones = []
    additions = []

    if add_evolution_items:
        evolution_items = _discover_evolution_items(
            item_blocks
        )

        if len(evolution_items) < 10:
            raise RuntimeError(
                "Found suspiciously few evolution items. "
                "Stopping before modifying Lilycove 2F."
            )

        additions.extend(
            evolution_items
        )

    if add_regional_postcards:
        missing = [
            item
            for item in REGIONAL_POSTCARDS
            if item not in item_blocks
        ]

        if missing:
            raise RuntimeError(
                "Missing regional postcard item definitions: "
                + ", ".join(missing)
            )

        regional_postcards = list(REGIONAL_POSTCARDS)
        additions.extend(regional_postcards)

    if add_mega_stones:
        mega_stones = _discover_mega_stones(
            item_blocks
        )

        if len(mega_stones) < 5:
            raise RuntimeError(
                "Found suspiciously few Mega Stones. "
                "Stopping before modifying Lilycove 2F."
            )

        additions.extend(
            mega_stones
        )

    additions = list(
        dict.fromkeys(
            additions
        )
    )

    total = _append_split_inventory(
        EVOLUTION_SHOP_FILE,
        EVOLUTION_SHOP_LABELS,
        additions,
        (
            "LilycoveCity_DepartmentStore_2F_EventScript_ClerkLeft::",
            "LilycoveCity_DepartmentStore_2F_EventScript_ClerkRight::",
        ),
    )

    if add_evolution_items:
        print(
            f"Added {len(evolution_items)} evolution items "
            "to Lilycove 2F."
        )

    if add_regional_postcards:
        print(
            f"Added {len(regional_postcards)} regional postcards "
            "to Lilycove 2F."
        )

    if add_mega_stones:
        print(
            f"Added {len(mega_stones)} Mega Stones "
            "to Lilycove 2F."
        )

    print(
        f"Lilycove 2F now has {total} unique shop items."
    )

    return {
        "evolution_items": len(
            evolution_items
        ),
        "regional_postcards": len(regional_postcards),
        "mega_stones": len(
            mega_stones
        ),
        "total_shop_items": total,
    }


def add_evolution_items_to_lilycove_shop():
    """Compatibility wrapper: evolution items only, no Mega Stones."""
    return configure_lilycove_evolution_shop(
        add_evolution_items=True,
        add_regional_postcards=False,
        add_mega_stones=False,
    )


def add_mega_stones_to_lilycove_shop():
    """Compatibility wrapper: Mega Stones only."""
    return configure_lilycove_evolution_shop(
        add_evolution_items=False,
        add_regional_postcards=False,
        add_mega_stones=True,
    )


if __name__ == "__main__":
    add_all_tms_to_lilycove_shop()
    configure_lilycove_evolution_shop(
        add_evolution_items=True,
        add_regional_postcards=True,
        add_mega_stones=True,
    )
