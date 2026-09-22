#!/usr/bin/env python3

import random
import re
import sys
from pathlib import Path
from clean_map_restore import restore_npc_trade_gifts
from config import PROTECTED_SPECIES

ROOT = Path(__file__).resolve().parent.parent

TRADE_FILE = ROOT / "src/data/trade.h"
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

rng = random.Random(seed)

print(f"In-game trade randomizer seed: {seed}")

# This makes the component safe when run directly as well as through the
# master randomiser. The master also performs the same token-level restoration
# before any selected components run.
restore_npc_trade_gifts()

# ------------------------------------------------------------
# BUILD SPECIES POOL
# ------------------------------------------------------------

species_header_pattern = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE
)

species_pool = set()

for filepath in sorted(SPECIES_DIR.rglob("*.h")):
    text = filepath.read_text(encoding="utf-8")

    species_pool.update(
        species_header_pattern.findall(text)
    )

# Remove things we've explicitly protected.
species_pool -= set(PROTECTED_SPECIES)

# Defensive exclusions.
species_pool.discard("SPECIES_NONE")
species_pool.discard("SPECIES_EGG")

species_pool = sorted(species_pool)

print(f"Found {len(species_pool)} usable species.")

if len(species_pool) < 100:
    raise RuntimeError(
        "Species parser found suspiciously few Pokémon."
    )

# ------------------------------------------------------------
# SCRIPTED NPC GIFTS OWNED BY THIS COMPONENT
# ------------------------------------------------------------

SCRIPTED_GIFTS = (
    {
        "name": "Weather Institute gift",
        "path": (
            ROOT
            / "data/maps/Route119_WeatherInstitute_2F/scripts.inc"
        ),
        "original": "SPECIES_CASTFORM_NORMAL",
        "expected_species_references": 3,
        "display_replacements": (
            (
                '"{PLAYER} received CASTFORM!$"',
                '"{PLAYER} received {STR_VAR_3}!$"',
            ),
            (
                (
                    '\t.string "That POKéMON changes shape according\\n"\n'
                    '\t.string "to the weather conditions.\\p"\n'
                    '\t.string "There\'re plenty of them in the\\n"\n'
                    '\t.string "INSTITUTE--go ahead and take it.$"'
                ),
                (
                    '\t.string "That {STR_VAR_3} is now yours.\\p"\n'
                    '\t.string "Please take good care of it.$"'
                ),
            ),
        ),
        "buffer_anchors": (
            "\tmessage "
            "Route119_WeatherInstitute_2F_Text_PlayerReceivedCastform",
            (
                "\tmsgbox "
                "Route119_WeatherInstitute_2F_"
                "Text_PokemonChangesWithWeather, MSGBOX_DEFAULT"
            ),
        ),
    },
    {
        "name": "Steven's Poké Ball gift",
        "path": (
            ROOT
            / "data/maps/MossdeepCity_StevensHouse/scripts.inc"
        ),
        "original": "SPECIES_BELDUM",
        "expected_species_references": 4,
        "display_replacements": (
            (
                '"BELDUM.\\p"',
                '"{STR_VAR_3}.\\p"',
            ),
            (
                '"{PLAYER} obtained a BELDUM.$"',
                '"{PLAYER} obtained a {STR_VAR_3}.$"',
            ),
            (
                '"Inside it is a BELDUM, my favorite\\n"',
                '"Inside it is a {STR_VAR_3}, my favorite\\n"',
            ),
        ),
        "buffer_anchors": (
            "\tmsgbox "
            "MossdeepCity_StevensHouse_Text_TakeBallContainingBeldum, "
            "MSGBOX_YESNO",
            "\tmessage MossdeepCity_StevensHouse_Text_ObtainedBeldum",
            "\tmsgbox MossdeepCity_StevensHouse_Text_LetterFromSteven, "
            "MSGBOX_DEFAULT",
        ),
    },
)

BUFFER_BEGIN = "@ RANDOMIZER_NPC_TRADE_GIFT_BUFFER_BEGIN"
BUFFER_END = "@ RANDOMIZER_NPC_TRADE_GIFT_BUFFER_END"


def _replace_exact_count(text, old, new, expected, description):
    count = text.count(old)

    if count != expected:
        raise RuntimeError(
            f"Could not safely randomise {description}.\n\n"
            f"Expected {expected} occurrence(s) of:\n  {old}\n"
            f"Found: {count}"
        )

    return text.replace(old, new)


def randomize_scripted_gifts():
    changed = []
    replacements_used = set()

    for gift in SCRIPTED_GIFTS:
        filepath = gift["path"]

        if not filepath.exists():
            raise RuntimeError(
                "NPC gift source file missing:\n"
                f"{filepath}"
            )

        original = gift["original"]
        candidates = [
            species
            for species in species_pool
            if (
                species != original
                and species not in replacements_used
            )
        ]

        if not candidates:
            candidates = [
                species
                for species in species_pool
                if species != original
            ]

        replacement = rng.choice(candidates)
        replacements_used.add(replacement)
        text = filepath.read_text(encoding="utf-8")
        text = _replace_exact_count(
            text,
            original,
            replacement,
            gift["expected_species_references"],
            gift["name"] + " species references",
        )

        for old, new in gift["display_replacements"]:
            text = _replace_exact_count(
                text,
                old,
                new,
                1,
                gift["name"] + " display text",
            )

        newline = "\r\n" if "\r\n" in text else "\n"
        buffer_block = newline.join(
            (
                BUFFER_BEGIN,
                f"\tbufferspeciesname STR_VAR_3, {replacement}",
                BUFFER_END,
                "",
            )
        )

        for anchor in gift["buffer_anchors"]:
            text = _replace_exact_count(
                text,
                anchor,
                buffer_block + anchor,
                1,
                gift["name"] + " name-buffer anchor",
            )

        filepath.write_text(text, encoding="utf-8")
        changed.append(
            (
                gift["name"],
                original,
                replacement,
            )
        )

    return changed

# ------------------------------------------------------------
# READ TRADE TABLE
# ------------------------------------------------------------

text = TRADE_FILE.read_text(encoding="utf-8")

# Match each individual trade entry.
trade_block_pattern = re.compile(
    r"(\[(INGAME_TRADE_[A-Z0-9_]+)\]\s*=\s*\n\s*\{\s*\n)"
    r"(.*?)"
    r"(^\s*\},?)",
    re.MULTILINE | re.DOTALL
)

given_pattern = re.compile(
    r"(\.species\s*=\s*)"
    r"(SPECIES_[A-Z0-9_]+)"
)

requested_pattern = re.compile(
    r"(\.requestedSpecies\s*=\s*)"
    r"(SPECIES_[A-Z0-9_]+)"
)

changed_trades = 0
spoiler_entries = []


def replace_trade(match):
    global changed_trades

    header = match.group(1)
    trade_name = match.group(2)
    body = match.group(3)
    footer = match.group(4)

    given_match = given_pattern.search(body)
    requested_match = requested_pattern.search(body)

    if given_match is None or requested_match is None:
        return match.group(0)

    old_given = given_match.group(2)
    old_requested = requested_match.group(2)

    # --------------------------------------------------------
    # Choose requested Pokémon
    # --------------------------------------------------------

    new_requested = rng.choice(species_pool)

    # --------------------------------------------------------
    # Choose received Pokémon
    # --------------------------------------------------------

    # Don't make the trade "X for X".
    received_candidates = [
        species
        for species in species_pool
        if species != new_requested
    ]

    new_given = rng.choice(received_candidates)

    # --------------------------------------------------------
    # Replace the two species
    # --------------------------------------------------------

    new_body = requested_pattern.sub(
        lambda m: m.group(1) + new_requested,
        body,
        count=1
    )

    new_body = given_pattern.sub(
        lambda m: m.group(1) + new_given,
        new_body,
        count=1
    )

    changed_trades += 1

    spoiler_entries.append({
        "trade": trade_name,
        "old_requested": old_requested,
        "old_given": old_given,
        "new_requested": new_requested,
        "new_given": new_given,
    })

    print(
        f"{trade_name}: "
        f"{old_requested} -> {old_given} "
        f"became "
        f"{new_requested} -> {new_given}"
    )

    return header + new_body + footer


new_text = trade_block_pattern.sub(
    replace_trade,
    text
)

TRADE_FILE.write_text(
    new_text,
    encoding="utf-8"
)

scripted_gift_changes = randomize_scripted_gifts()

for gift_name, original, replacement in scripted_gift_changes:
    print(
        f"{gift_name}: {original} -> {replacement}"
    )

print()
print(
    f"Randomized {changed_trades} "
    f"in-game trades."
)

print(
    f"Randomized {len(scripted_gift_changes)} "
    f"NPC gifts."
)

print(f"Seed: {seed}")
