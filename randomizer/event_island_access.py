#!/usr/bin/env python3

"""Toggle post-game access to Emerald's four event islands."""

import re

from runtime_paths import ROOT

FERRY_SCRIPT = (
    ROOT
    / "data"
    / "maps"
    / "LilycoveCity_Harbor"
    / "scripts.inc"
)

CALL_BEGIN = "@ RANDOMIZER_EVENT_ISLAND_ACCESS_CALL_BEGIN"
CALL_END = "@ RANDOMIZER_EVENT_ISLAND_ACCESS_CALL_END"
SCRIPT_BEGIN = "@ RANDOMIZER_EVENT_ISLAND_ACCESS_SCRIPT_BEGIN"
SCRIPT_END = "@ RANDOMIZER_EVENT_ISLAND_ACCESS_SCRIPT_END"

FERRY_CLEAR_ANCHOR = (
    "\tgoto_if_unset FLAG_SYS_GAME_CLEAR, "
    "LilycoveCity_Harbor_EventScript_FerryUnavailable"
)
STATE_SCRIPT_ANCHOR = (
    "LilycoveCity_Harbor_EventScript_GetEonTicketState::"
)


class EventIslandAccessError(RuntimeError):
    """Raised when the expected Lilycove ferry source cannot be patched."""


def _newline(text):
    return "\r\n" if "\r\n" in text else "\n"


def _strip_owned_blocks(text):
    """Remove only blocks previously installed by this module."""

    for begin, end in (
        (CALL_BEGIN, CALL_END),
        (SCRIPT_BEGIN, SCRIPT_END),
    ):
        pattern = re.compile(
            rf"(?m)^[ \t]*{re.escape(begin)}\r?\n"
            rf".*?"
            rf"^[ \t]*{re.escape(end)}\r?\n"
            rf"(?:\r?\n)?",
            re.DOTALL,
        )
        text = pattern.sub("", text)

    return text


def _call_block(nl):
    return nl.join(
        (
            f"\t{CALL_BEGIN}",
            "\tcall Randomizer_EventScript_UnlockEventIslands",
            f"\t{CALL_END}",
            "",
        )
    )


def _script_block(nl):
    lines = (
        SCRIPT_BEGIN,
        "Randomizer_EventScript_UnlockEventIslands::",
        "\tcheckitem ITEM_EON_TICKET",
        (
            "\tgoto_if_eq VAR_RESULT, TRUE, "
            "Randomizer_EventScript_EnableSouthernIsland"
        ),
        "\tgiveitem ITEM_EON_TICKET",
        "\tcheckitem ITEM_EON_TICKET",
        (
            "\tgoto_if_eq VAR_RESULT, FALSE, "
            "Randomizer_EventScript_CheckAuroraTicket"
        ),
        "Randomizer_EventScript_EnableSouthernIsland::",
        "\tsetflag FLAG_ENABLE_SHIP_SOUTHERN_ISLAND",
        "",
        "Randomizer_EventScript_CheckAuroraTicket::",
        "\tcheckitem ITEM_AURORA_TICKET",
        (
            "\tgoto_if_eq VAR_RESULT, TRUE, "
            "Randomizer_EventScript_EnableBirthIsland"
        ),
        "\tgiveitem ITEM_AURORA_TICKET",
        "\tcheckitem ITEM_AURORA_TICKET",
        (
            "\tgoto_if_eq VAR_RESULT, FALSE, "
            "Randomizer_EventScript_CheckMysticTicket"
        ),
        "Randomizer_EventScript_EnableBirthIsland::",
        "\tsetflag FLAG_ENABLE_SHIP_BIRTH_ISLAND",
        "",
        "Randomizer_EventScript_CheckMysticTicket::",
        "\tcheckitem ITEM_MYSTIC_TICKET",
        (
            "\tgoto_if_eq VAR_RESULT, TRUE, "
            "Randomizer_EventScript_EnableNavelRock"
        ),
        "\tgiveitem ITEM_MYSTIC_TICKET",
        "\tcheckitem ITEM_MYSTIC_TICKET",
        (
            "\tgoto_if_eq VAR_RESULT, FALSE, "
            "Randomizer_EventScript_CheckOldSeaMap"
        ),
        "Randomizer_EventScript_EnableNavelRock::",
        "\tsetflag FLAG_ENABLE_SHIP_NAVEL_ROCK",
        "",
        "Randomizer_EventScript_CheckOldSeaMap::",
        "\tcheckitem ITEM_OLD_SEA_MAP",
        (
            "\tgoto_if_eq VAR_RESULT, TRUE, "
            "Randomizer_EventScript_EnableFarawayIsland"
        ),
        "\tgiveitem ITEM_OLD_SEA_MAP",
        "\tcheckitem ITEM_OLD_SEA_MAP",
        (
            "\tgoto_if_eq VAR_RESULT, FALSE, "
            "Randomizer_EventScript_EventIslandAccessDone"
        ),
        "Randomizer_EventScript_EnableFarawayIsland::",
        "\tsetflag FLAG_ENABLE_SHIP_FARAWAY_ISLAND",
        "",
        "Randomizer_EventScript_EventIslandAccessDone::",
        "\treturn",
        SCRIPT_END,
        "",
        "",
    )
    return nl.join(lines)


def configure_event_island_access(enabled=False):
    """
    Enable or disable the post-game Lilycove event-island unlock.

    When enabled, the attendant gives each missing event pass after the Hall
    of Fame and enables its ferry destination. Existing passes are never
    duplicated. No encounter, defeated, or caught flag is changed.
    """

    if not FERRY_SCRIPT.is_file():
        raise EventIslandAccessError(
            "Could not find the Lilycove ferry script at "
            f"{FERRY_SCRIPT}."
        )

    raw = FERRY_SCRIPT.read_bytes()
    try:
        original = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise EventIslandAccessError(
            f"Could not decode {FERRY_SCRIPT} as UTF-8."
        ) from exc

    nl = _newline(original)
    text = _strip_owned_blocks(original)

    if enabled:
        ferry_anchor = FERRY_CLEAR_ANCHOR + nl
        if text.count(ferry_anchor) != 1:
            raise EventIslandAccessError(
                "Could not uniquely locate the post-game check in "
                "data/maps/LilycoveCity_Harbor/scripts.inc."
            )

        state_anchor = STATE_SCRIPT_ANCHOR
        if text.count(state_anchor) != 1:
            raise EventIslandAccessError(
                "Could not uniquely locate the ferry ticket-state scripts in "
                "data/maps/LilycoveCity_Harbor/scripts.inc."
            )

        text = text.replace(
            ferry_anchor,
            ferry_anchor + _call_block(nl),
            1,
        )
        text = text.replace(
            state_anchor,
            _script_block(nl) + state_anchor,
            1,
        )

    encoded = text.encode("utf-8")
    changed = encoded != raw

    if changed:
        FERRY_SCRIPT.write_bytes(encoded)

    print(
        "  Event-island access: "
        + ("ON" if enabled else "off")
        + (" (source updated)" if changed else "")
    )

    return changed


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Toggle post-game event-island access."
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable event-island passes at the post-game Lilycove ferry.",
    )
    arguments = parser.parse_args()
    configure_event_island_access(arguments.enable)
