#!/usr/bin/env python3
"""Configure the project's active TM list from a canonical game profile."""

import argparse
import base64
import hashlib
import re
import zlib

from runtime_paths import ROOT
from tm_catalog_data import (
    DEFAULT_TM_CATALOG,
    ORIGINAL_GEN3_TM_ITEMS_B64,
    ORIGINAL_GEN3_TM_ITEMS_SHA256,
    TM_CATALOGS,
    TM_CATALOG_KEYS,
)


TMHM_CONSTANTS_FILE = ROOT / "include/constants/tms_hms.h"
ITEMS_FILE = ROOT / "src/data/items.h"
MOVES_INFO_FILE = ROOT / "src/data/moves_info.h"

TM_SECTION_MARKER = (
    "// TMs/HMs. They don't have a set flingPower, as that's handled by "
    "GetFlingPowerFromItemId."
)
FIRST_HM_PATTERN = re.compile(r"(?m)^\s*\[ITEM_HM_CUT\]\s*=\s*$")


def _tm_macro(moves):
    lines = ["#define FOREACH_TM(F) \\"]

    for index, move in enumerate(moves):
        suffix = " \\" if index + 1 < len(moves) else ""
        lines.append(f"    F({move}){suffix}")

    return "\n".join(lines)


def _replace_tm_macro(source, moves):
    start = source.find("#define FOREACH_TM(F)")
    end = source.find("\n#define FOREACH_HM(F)", start)

    if start < 0 or end < 0:
        raise RuntimeError(
            "Could not find the FOREACH_TM section in include/constants/tms_hms.h."
        )

    return source[:start] + _tm_macro(moves) + "\n" + source[end:]


def _move_names(source, moves):
    names = {}

    for move in moves:
        block_match = re.search(
            rf"(?ms)^\s*\[MOVE_{re.escape(move)}\]\s*=\s*\{{"
            rf"(?P<body>.*?)(?=^\s*\[MOVE_|^\}};)",
            source,
        )

        if not block_match:
            raise RuntimeError(f"Could not find MOVE_{move} in moves_info.h.")

        name_match = re.search(
            r'\.name\s*=\s*COMPOUND_STRING\("([^"\\]*(?:\\.[^"\\]*)*)"\)',
            block_match.group("body"),
        )

        if not name_match:
            raise RuntimeError(f"Could not read the display name for MOVE_{move}.")

        names[move] = name_match.group(1)

    return names


def _active_tm_block(slot, move, move_name):
    number = f"{slot:02d}"

    return f'''    [ITEM_TM_{move}] =
    {{
        .name = ITEM_NAME("TM{number}"),
        .price = 3000,
        .description = COMPOUND_STRING(
            "Teaches the move\\n"
            "{move_name} to\\n"
            "a compatible {{PKMN}}."),
        .importance = I_REUSABLE_TMS,
        .pocket = POCKET_TM_HM,
        .type = ITEM_USE_PARTY_MENU,
        .fieldUseFunc = ItemUseOutOfBattle_TMHM,
    }},
'''


def _placeholder_tm_block(slot):
    return f'''    [ITEM_TM{slot:02d}] =
    {{
        .name = ITEM_NAME("TM{slot:02d}"),
        .price = 3000,
        .description = sQuestionMarksDesc, // Unused by the active catalogue
        .importance = I_REUSABLE_TMS,
        .pocket = POCKET_TM_HM,
        .type = ITEM_USE_PARTY_MENU,
        .fieldUseFunc = ItemUseOutOfBattle_TMHM,
    }},
'''


def _original_gen3_tm_items():
    section = zlib.decompress(
        base64.b64decode(ORIGINAL_GEN3_TM_ITEMS_B64)
    ).decode("utf-8")

    digest = hashlib.sha256(section.encode("utf-8")).hexdigest()

    if digest != ORIGINAL_GEN3_TM_ITEMS_SHA256:
        raise RuntimeError("The embedded Emerald TM baseline is corrupt.")

    return section


def _replace_tm_item_section(source, moves, names, original_section=None):
    marker = source.find(TM_SECTION_MARKER)

    if marker < 0:
        raise RuntimeError("Could not find the TM/HM section in src/data/items.h.")

    content_start = marker + len(TM_SECTION_MARKER)
    hm_match = FIRST_HM_PATTERN.search(source, content_start)

    if not hm_match:
        raise RuntimeError("Could not find ITEM_HM_CUT in src/data/items.h.")

    if original_section is not None:
        replacement = original_section
    else:
        total = len(moves)
        blocks = [
            _active_tm_block(slot, move, names[move])
            for slot, move in enumerate(moves, 1)
        ]
        blocks.extend(
            _placeholder_tm_block(slot)
            for slot in range(total + 1, 101)
        )
        replacement = "\n\n" + "\n".join(blocks) + "\n"

    return source[:content_start] + replacement + source[hm_match.start():]


def configure_tm_catalog(
    catalog_key=DEFAULT_TM_CATALOG,
    tmhm_constants_file=TMHM_CONSTANTS_FILE,
    items_file=ITEMS_FILE,
    moves_info_file=MOVES_INFO_FILE,
):
    """Write one catalogue and return its key, label, count and move order."""
    if catalog_key not in TM_CATALOGS:
        raise RuntimeError(
            f"Unknown TM catalogue {catalog_key!r}. Choose: "
            + ", ".join(TM_CATALOG_KEYS)
        )

    profile = TM_CATALOGS[catalog_key]
    moves = profile["moves"]

    if not 1 <= len(moves) <= 100 or len(set(moves)) != len(moves):
        raise RuntimeError(f"TM catalogue {catalog_key!r} is invalid.")

    constants_source = tmhm_constants_file.read_text(encoding="utf-8")
    items_source = items_file.read_text(encoding="utf-8")
    moves_source = moves_info_file.read_text(encoding="utf-8")

    original_section = (
        _original_gen3_tm_items()
        if catalog_key == DEFAULT_TM_CATALOG
        else None
    )
    names = (
        {}
        if original_section is not None
        else _move_names(moves_source, moves)
    )
    new_constants = _replace_tm_macro(constants_source, moves)
    new_items = _replace_tm_item_section(
        items_source,
        moves,
        names,
        original_section=original_section,
    )

    # Both outputs are fully validated before either file is changed.
    tmhm_constants_file.write_text(new_constants, encoding="utf-8")
    items_file.write_text(new_items, encoding="utf-8")

    result = {
        "key": catalog_key,
        "label": profile["label"],
        "count": len(moves),
        "moves": moves,
    }
    print(f"Configured {profile['label']}.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "catalog",
        choices=TM_CATALOG_KEYS,
        nargs="?",
        default=DEFAULT_TM_CATALOG,
    )
    args = parser.parse_args()
    configure_tm_catalog(args.catalog)


if __name__ == "__main__":
    main()
