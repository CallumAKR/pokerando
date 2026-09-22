#!/usr/bin/env python3

import re
from pathlib import Path

from manual_customization_runtime import species_is_enabled

ROOT = Path(__file__).resolve().parent.parent
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"

# Plain trade evolutions become this level.
TRADE_EVOLUTION_LEVEL = 37

species_header_pattern = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$"
)

trade_evo_pattern = re.compile(
    r"\{EVO_TRADE\s*,\s*0\s*,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
    r"(?:\s*,\s*CONDITIONS\(\{([^}]*)\}\))?"
    r"\}"
)

hold_item_pattern = re.compile(
    r"IF_HOLD_ITEM\s*,\s*(ITEM_[A-Z0-9_]+)"
)

trade_partner_pattern = re.compile(
    r"IF_TRADE_PARTNER_SPECIES\s*,\s*(SPECIES_[A-Z0-9_]+)"
)

changed = 0
item_evolutions = 0
level_evolutions = 0

for filepath in sorted(SPECIES_DIR.rglob("*.h")):

    text = filepath.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)

    current_species = None
    changed_file = False

    for index, line in enumerate(lines):

        species_match = species_header_pattern.match(
            line.rstrip("\r\n")
        )

        if species_match:
            current_species = species_match.group(1)

        if "EVO_TRADE" not in line:
            continue

        if current_species is None or not species_is_enabled(current_species):
            continue

        def replace_trade(match):
            global changed
            global item_evolutions
            global level_evolutions

            target_species = match.group(1)
            conditions = match.group(2) or ""

            # Trade while holding an item -> use that item directly.
            item_match = hold_item_pattern.search(conditions)

            if item_match:
                item = item_match.group(1)

                print(
                    f"{current_species} -> {target_species}: "
                    f"TRADE + {item} => ITEM evolution"
                )

                changed += 1
                item_evolutions += 1

                return (
                    f"{{EVO_ITEM, {item}, "
                    f"{target_species}}}"
                )

            # Trade with a specific species -> level evolution.
            partner_match = trade_partner_pattern.search(
                conditions
            )

            if partner_match:
                partner = partner_match.group(1)

                print(
                    f"{current_species} -> {target_species}: "
                    f"TRADE with {partner} => "
                    f"LEVEL {TRADE_EVOLUTION_LEVEL}"
                )

                changed += 1
                level_evolutions += 1

                return (
                    f"{{EVO_LEVEL, "
                    f"{TRADE_EVOLUTION_LEVEL}, "
                    f"{target_species}}}"
                )

            # Normal trade -> level evolution.
            print(
                f"{current_species} -> {target_species}: "
                f"TRADE => LEVEL {TRADE_EVOLUTION_LEVEL}"
            )

            changed += 1
            level_evolutions += 1

            return (
                f"{{EVO_LEVEL, "
                f"{TRADE_EVOLUTION_LEVEL}, "
                f"{target_species}}}"
            )

        new_line = trade_evo_pattern.sub(
            replace_trade,
            line
        )

        if new_line != line:
            lines[index] = new_line
            changed_file = True

    if changed_file:
        filepath.write_text(
            "".join(lines),
            encoding="utf-8"
        )

print()
print(f"Changed {changed} trade evolutions.")
print(f"  Item evolutions: {item_evolutions}")
print(f"  Level evolutions: {level_evolutions}")
