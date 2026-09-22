#!/usr/bin/env python3

"""Configure optional all-fossil revival support and item-pool rules."""

import json
import re
from pathlib import Path

from runtime_paths import RANDOMIZER_DIR, ROOT


DEVON_SCRIPT = (
    ROOT
    / "data"
    / "maps"
    / "RustboroCity_DevonCorp_2F"
    / "scripts.inc"
)
CONFIG_FILE = RANDOMIZER_DIR / "fossil_options.json"
ORIGINAL_SECTION_FILE = RANDOMIZER_DIR / "fossil_options_original.inc"

BEGIN_MARKER = "@ RANDOMIZER_ALL_FOSSILS_BEGIN"
END_MARKER = "@ RANDOMIZER_ALL_FOSSILS_END"
ORIGINAL_BEGIN = "RustboroCity_DevonCorp_2F_EventScript_FossilScientist::"
ORIGINAL_END = "RustboroCity_DevonCorp_2F_EventScript_MatchCallScientist::"

# Each Galar piece is deliberately sufficient by itself.  Every piece maps to
# one Pokémon for which it is part of the canonical two-piece combination.
FOSSILS = (
    ("ITEM_HELIX_FOSSIL", "SPECIES_OMANYTE", "Helix"),
    ("ITEM_DOME_FOSSIL", "SPECIES_KABUTO", "Dome"),
    ("ITEM_OLD_AMBER", "SPECIES_AERODACTYL", "OldAmber"),
    ("ITEM_ROOT_FOSSIL", "SPECIES_LILEEP", "Root"),
    ("ITEM_CLAW_FOSSIL", "SPECIES_ANORITH", "Claw"),
    ("ITEM_ARMOR_FOSSIL", "SPECIES_SHIELDON", "Armor"),
    ("ITEM_SKULL_FOSSIL", "SPECIES_CRANIDOS", "Skull"),
    ("ITEM_COVER_FOSSIL", "SPECIES_TIRTOUGA", "Cover"),
    ("ITEM_PLUME_FOSSIL", "SPECIES_ARCHEN", "Plume"),
    ("ITEM_JAW_FOSSIL", "SPECIES_TYRUNT", "Jaw"),
    ("ITEM_SAIL_FOSSIL", "SPECIES_AMAURA", "Sail"),
    ("ITEM_FOSSILIZED_BIRD", "SPECIES_DRACOZOLT", "Bird"),
    ("ITEM_FOSSILIZED_DINO", "SPECIES_ARCTOZOLT", "Dino"),
    ("ITEM_FOSSILIZED_DRAKE", "SPECIES_DRACOVISH", "Drake"),
    ("ITEM_FOSSILIZED_FISH", "SPECIES_ARCTOVISH", "Fish"),
)


class FossilOptionError(RuntimeError):
    """Raised when the Devon fossil script cannot be safely configured."""


def _newline(text):
    return "\r\n" if "\r\n" in text else "\n"


def _find_original_section(text):
    start = text.find(ORIGINAL_BEGIN)
    end = text.find(ORIGINAL_END)

    if start < 0 or end < 0 or end <= start:
        raise FossilOptionError(
            "Could not safely locate the Devon fossil-revival scripts in "
            "data/maps/RustboroCity_DevonCorp_2F/scripts.inc."
        )

    return start, end


def _find_owned_section(text):
    start = text.find(BEGIN_MARKER)
    end = text.find(END_MARKER)

    if start < 0 and end < 0:
        return None

    if start < 0 or end < 0 or end <= start:
        raise FossilOptionError(
            "The randomiser's all-fossil script markers are incomplete in "
            "data/maps/RustboroCity_DevonCorp_2F/scripts.inc."
        )

    end += len(END_MARKER)

    while end < len(text) and text[end] in "\r\n":
        end += 1

    return start, end


def _save_original_section(text):
    if ORIGINAL_SECTION_FILE.exists():
        return

    if _find_owned_section(text) is not None:
        raise FossilOptionError(
            "All-fossil support is installed, but its original Devon-script "
            "backup is missing:\n"
            f"{ORIGINAL_SECTION_FILE}"
        )

    start, end = _find_original_section(text)
    original_section = text[start:end]

    # A previous static-randomisation run may have replaced the two ordinary
    # Devon gifts before this module is installed for the first time. Preserve
    # the user's original script layout, but make the saved baseline species
    # canonical so disabling the option can never restore randomised fossils.
    for family, clean_species in (
        ("Lileep", "SPECIES_LILEEP"),
        ("Anorith", "SPECIES_ANORITH"),
    ):
        block_pattern = re.compile(
            rf"(?P<header>^"
            rf"RustboroCity_DevonCorp_2F_EventScript_"
            rf"[A-Za-z0-9_]*{family}[A-Za-z0-9_]*::\r?\n)"
            rf"(?P<body>.*?)"
            rf"(?=^[A-Za-z0-9_]+::|\Z)",
            re.MULTILINE | re.DOTALL,
        )

        original_section = block_pattern.sub(
            lambda match: (
                match.group("header")
                + re.sub(
                    r"SPECIES_[A-Z0-9_]+",
                    clean_species,
                    match.group("body"),
                )
            ),
            original_section,
        )

    ORIGINAL_SECTION_FILE.write_bytes(
        original_section.encode("utf-8")
    )


def _build_all_fossils_section(nl):
    lines = [
        BEGIN_MARKER,
        "RustboroCity_DevonCorp_2F_EventScript_FossilScientist::",
        "\tlock",
        "\tfaceplayer",
        (
            "\tgoto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 2, "
            "Randomizer_Fossil_EventScript_MonReady"
        ),
        (
            "\tgoto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, "
            "RustboroCity_DevonCorp_2F_EventScript_StillRegenerating"
        ),
        (
            "\tmsgbox "
            "RustboroCity_DevonCorp_2F_Text_DevelopDeviceToResurrectFossils, "
            "MSGBOX_DEFAULT"
        ),
    ]

    for index, (item, _, label) in enumerate(FOSSILS, start=1):
        lines.extend(
            (
                f"\tcheckitem {item}",
                (
                    "\tcall_if_eq VAR_RESULT, TRUE, "
                    f"Randomizer_Fossil_EventScript_Offer{label}"
                ),
                (
                    "\tgoto_if_eq VAR_FOSSIL_RESURRECTION_STATE, 1, "
                    "Randomizer_Fossil_EventScript_Submitted"
                ),
            )
        )

    lines.extend(
        (
            "\trelease",
            "\tend",
            "",
            "Randomizer_Fossil_EventScript_Submitted::",
            "\trelease",
            "\tend",
            "",
            # The original fossil section defines this destination inside the
            # range replaced by the all-fossil block. Recreate it here because
            # FossilScientist still branches to it while a revival is running.
            "RustboroCity_DevonCorp_2F_EventScript_StillRegenerating::",
            (
                "\tmsgbox "
                "RustboroCity_DevonCorp_2F_Text_FossilRegeneratorTakesTime, "
                "MSGBOX_DEFAULT"
            ),
            "\trelease",
            "\tend",
            "",
        )
    )

    for index, (item, _, label) in enumerate(FOSSILS, start=1):
        lines.extend(
            (
                f"Randomizer_Fossil_EventScript_Offer{label}::",
                f"\tbufferitemname STR_VAR_1, {item}",
                (
                    "\tmsgbox Randomizer_Fossil_Text_OfferFossil, "
                    "MSGBOX_YESNO"
                ),
                "\tgoto_if_eq VAR_RESULT, NO, Common_EventScript_NopReturn",
                (
                    "\tmsgbox "
                    "RustboroCity_DevonCorp_2F_Text_HandedFossilToResearcher, "
                    "MSGBOX_DEFAULT"
                ),
                f"\tremoveitem {item}",
                "\tsetvar VAR_FOSSIL_RESURRECTION_STATE, 1",
                f"\tsetvar VAR_WHICH_FOSSIL_REVIVED, {index}",
                "\treturn",
                "",
            )
        )

    lines.extend(
        (
            "Randomizer_Fossil_EventScript_MonReady::",
            "\tcall Randomizer_Fossil_EventScript_SetRevivedSpecies",
            "\tbufferspeciesname STR_VAR_2, VAR_TEMP_1",
            (
                "\tmsgbox "
                "RustboroCity_DevonCorp_2F_Text_FossilizedMonBroughtBackToLife, "
                "MSGBOX_DEFAULT"
            ),
            "\tcopyvar VAR_TEMP_TRANSFERRED_SPECIES, VAR_TEMP_1",
            "\tgivemon VAR_TEMP_1, 20",
            (
                "\tgoto_if_eq VAR_RESULT, MON_GIVEN_TO_PARTY, "
                "Randomizer_Fossil_EventScript_ReceiveParty"
            ),
            (
                "\tgoto_if_eq VAR_RESULT, MON_GIVEN_TO_PC, "
                "Randomizer_Fossil_EventScript_ReceivePC"
            ),
            "\tgoto Common_EventScript_NoMoreRoomForPokemon",
            "\tend",
            "",
            "Randomizer_Fossil_EventScript_ReceiveParty::",
            "\tcall Randomizer_Fossil_EventScript_ReceivedFanfare",
            "\tmsgbox gText_NicknameThisPokemon, MSGBOX_YESNO",
            (
                "\tgoto_if_eq VAR_RESULT, NO, "
                "Randomizer_Fossil_EventScript_FinishReceiving"
            ),
            "\tcall Common_EventScript_GetGiftMonPartySlot",
            "\tcall Common_EventScript_NameReceivedPartyMon",
            "\tgoto Randomizer_Fossil_EventScript_FinishReceiving",
            "\tend",
            "",
            "Randomizer_Fossil_EventScript_ReceivePC::",
            "\tcall Randomizer_Fossil_EventScript_ReceivedFanfare",
            "\tmsgbox gText_NicknameThisPokemon, MSGBOX_YESNO",
            (
                "\tgoto_if_eq VAR_RESULT, NO, "
                "Randomizer_Fossil_EventScript_TransferToPC"
            ),
            "\tcall Common_EventScript_NameReceivedBoxMon",
            "",
            "Randomizer_Fossil_EventScript_TransferToPC::",
            "\tcall Common_EventScript_TransferredToPC",
            "",
            "Randomizer_Fossil_EventScript_FinishReceiving::",
            "\tsetvar VAR_FOSSIL_RESURRECTION_STATE, 0",
            "\tsetflag FLAG_RECEIVED_REVIVED_FOSSIL_MON",
            "\trelease",
            "\tend",
            "",
            "Randomizer_Fossil_EventScript_ReceivedFanfare::",
            "\tbufferspeciesname STR_VAR_2, VAR_TEMP_1",
            "\tplayfanfare MUS_OBTAIN_ITEM",
            (
                "\tmessage "
                "RustboroCity_DevonCorp_2F_Text_ReceivedMonFromResearcher"
            ),
            "\twaitmessage",
            "\twaitfanfare",
            "\tbufferspeciesname STR_VAR_1, VAR_TEMP_1",
            "\treturn",
            "",
            "Randomizer_Fossil_EventScript_SetRevivedSpecies::",
            "\tswitch VAR_WHICH_FOSSIL_REVIVED",
        )
    )

    for index, (_, _, label) in enumerate(FOSSILS, start=1):
        lines.append(
            f"\tcase {index}, Randomizer_Fossil_EventScript_SetSpecies{label}"
        )

    lines.extend(("\treturn", ""))

    for _, species, label in FOSSILS:
        lines.extend(
            (
                f"Randomizer_Fossil_EventScript_SetSpecies{label}::",
                f"\tsetvar VAR_TEMP_1, {species}",
                "\treturn",
                "",
            )
        )

    lines.extend(
        (
            "Randomizer_Fossil_Text_OfferFossil:",
            "\t.string \"I found your {STR_VAR_1}!\\p\"",
            "\t.string \"Would you like me to bring its\\n\"",
            "\t.string \"ancient POKéMON back to life?$\"",
            END_MARKER,
            "",
            "",
        )
    )

    return nl.join(lines)


def _configure_devon_script(enabled):
    if not DEVON_SCRIPT.is_file():
        raise FossilOptionError(
            "Could not find the Devon fossil-revival script at:\n"
            f"{DEVON_SCRIPT}"
        )

    raw = DEVON_SCRIPT.read_bytes()
    text = raw.decode("utf-8")
    owned = _find_owned_section(text)

    if enabled:
        _save_original_section(text)
        start, end = owned or _find_original_section(text)
        replacement = _build_all_fossils_section(_newline(text))
        text = text[:start] + replacement + text[end:]
    else:
        _save_original_section(text)
        start, end = owned or _find_original_section(text)
        original_section = ORIGINAL_SECTION_FILE.read_bytes().decode("utf-8")
        text = text[:start] + original_section + text[end:]

    encoded = text.encode("utf-8")
    changed = encoded != raw

    if changed:
        DEVON_SCRIPT.write_bytes(encoded)

    return changed


def configure_fossil_options(
    enable_all_fossils=False,
    fossil_only_replacements=False,
):
    """Write run-scoped fossil settings and configure Devon revival support."""

    enable_all_fossils = bool(enable_all_fossils)
    fossil_only_replacements = bool(fossil_only_replacements)

    source_changed = _configure_devon_script(enable_all_fossils)
    config = {
        "enable_all_fossils": enable_all_fossils,
        "fossil_only_replacements": fossil_only_replacements,
    }
    config_text = json.dumps(config, indent=2) + "\n"
    config_changed = (
        not CONFIG_FILE.exists()
        or CONFIG_FILE.read_text(encoding="utf-8") != config_text
    )

    if config_changed:
        CONFIG_FILE.write_text(config_text, encoding="utf-8")

    print(
        "  All fossil revivals: "
        + ("ON" if enable_all_fossils else "off")
        + (" (source updated)" if source_changed else "")
    )
    print(
        "  Fossil-only Pokémon for randomised revivals: "
        + ("ON" if fossil_only_replacements else "off")
    )

    return source_changed or config_changed
