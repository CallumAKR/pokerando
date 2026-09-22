#!/usr/bin/env python3

import re
from pathlib import Path

from runtime_paths import (
    BASELINE_ROOT,
    RANDOMIZER_DIR,
    ROOT,
)


HEADER_PATH = (
    ROOT
    / "include"
    / "randomizer_game_options.h"
)

POKEMON_C = ROOT / "src/pokemon.c"
BATTLE_UTIL_C = ROOT / "src/battle_util.c"
ITEM_C = ROOT / "src/item.c"
FORM_CHANGE_TABLES_H = (
    ROOT
    / "src/data/pokemon/form_change_tables.h"
)
BATTLE_SCRIPT_COMMANDS_C = (
    ROOT / "src/battle_script_commands.c"
)
BATTLE_MAIN_C = ROOT / "src/battle_main.c"
ITEM_USE_C = ROOT / "src/item_use.c"
NEW_GAME_C = ROOT / "src/new_game.c"
LITTLEROOT_SCRIPTS = ROOT / "data/maps/LittlerootTown/scripts.inc"
SCRCMD_C = ROOT / "src/scrcmd.c"
WILD_ENCOUNTER_C = ROOT / "src/wild_encounter.c"
TIME_EVENTS_C = ROOT / "src/time_events.c"
FIELD_MOVE_H = ROOT / "include/field_move.h"
ITEMS_H = ROOT / "src/data/items.h"
ITEM_CONSTANTS_H = ROOT / "include/constants/items.h"
CAPS_CONFIG_H = ROOT / "include/config/caps.h"
URSARING_SPECIES_H = (
    ROOT
    / "src/data/pokemon/species_info/gen_2_families.h"
)

HM_FREE_TEMPLATE_ROOT = (
    RANDOMIZER_DIR
    / "game_options_templates"
    / "hm_free"
)

HM_FREE_SCRIPT_PATHS = (
    Path("data/scripts/field_move_scripts.inc"),
    Path("data/scripts/surf.inc"),
)


GAME_OPTION_NAMES = {
    "permadeath": "Permanent death",
    "hm_free_field_moves": "HM use without teaching moves and HM field tools",
    "hm_progression_bypass": "Disable progression requirements to use HMs",
    "perma_repel": "Perma Repel",
    "cap_candy": "Level to cap party action",
    "mom_bonus": "Mom's Ultra Balls and money",
    "party_heal": "Party Heal",
    "time_turner": "Time Turner",
    "weather_setter": "Weather Setter",
    "always_catch": "100% catch rate",
    "force_shiny": "Force all Pokémon shiny",
    "permanent_megas": "Permanent Mega Evolutions",
    "regional_evolution_postcards": "Regional evolution postcards",
    "level_caps": "Level caps",
    "always_mirage_island": "Mirage Island always present",
    "force_set_battle_style": "Force Set battle style",
    "disable_bag_in_trainer_battles": "Disable Bag items in trainer battles",
}


CUSTOM_FIELD_ITEMS = (
    "ITEM_PARTY_RESTORER",
    "ITEM_CAP_CANDY",
    "ITEM_PERMA_REPEL",
    "ITEM_TIME_TURNER",
    "ITEM_WEATHER_SETTER",
)

REGIONAL_POSTCARD_ITEMS = (
    "ITEM_ALOLA_POSTCARD",
    "ITEM_GALAR_POSTCARD",
    "ITEM_HISUI_POSTCARD",
)

URSARING_REGIONAL_START = (
    "RANDOMIZER REGIONAL EVOLUTIONS: URSALUNA START"
)
URSARING_REGIONAL_END = (
    "RANDOMIZER REGIONAL EVOLUTIONS: URSALUNA END"
)

URSARING_EVOLUTION_PATTERN = re.compile(
    r"(?m)^(?P<indent>[ \t]*)\.evolutions\s*=\s*EVOLUTION\("
    r"\{\s*EVO_ITEM\s*,\s*ITEM_PEAT_BLOCK\s*,\s*"
    r"SPECIES_URSALUNA\s*,\s*CONDITIONS\("
    r"\{\s*IF_REGION\s*,\s*REGION_HISUI\s*\}\s*,\s*"
    r"\{\s*IF_TIME\s*,\s*TIME_NIGHT\s*\}\s*\)\s*\}\s*,\s*\n"
    r"[ \t]*\{\s*EVO_NONE\s*,\s*0\s*,\s*"
    r"SPECIES_URSALUNA_BLOODMOON\s*\}\s*\)\s*,?"
)


INCLUDE_LINE = '#include "randomizer_game_options.h"'


class GameOptionPatchError(RuntimeError):
    pass


def _read(path):
    if not path.exists():
        raise GameOptionPatchError(
            f"Required game source file is missing:\n{path}"
        )

    return path.read_text(
        encoding="utf-8"
    )


def _write_if_changed(
    path,
    text,
):
    current = (
        path.read_text(encoding="utf-8")
        if path.exists()
        else None
    )

    if current == text:
        return False

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    return True


def _ensure_include(
    path,
):
    text = _read(
        path
    )

    if INCLUDE_LINE in text:
        return False

    global_include = '#include "global.h"'

    if global_include in text:
        text = text.replace(
            global_include,
            (
                global_include
                + "\n"
                + INCLUDE_LINE
            ),
            1,
        )
    else:
        first_include = re.search(
            r'(?m)^#include\s+"[^"]+"\s*$',
            text,
        )

        if first_include is None:
            raise GameOptionPatchError(
                f"Could not find an include insertion point in {path}."
            )

        pos = first_include.start()

        text = (
            text[:pos]
            + INCLUDE_LINE
            + "\n"
            + text[pos:]
        )

    return _write_if_changed(
        path,
        text,
    )


def _function_open_brace_end(
    text,
    function_name,
):
    pattern = re.compile(
        rf"(?m)^[A-Za-z_][A-Za-z0-9_ \t*]*\b"
        rf"{re.escape(function_name)}\s*\([^;]*?\)\s*\n?\{{"
    )

    match = pattern.search(
        text
    )

    if match is None:
        raise GameOptionPatchError(
            f"Could not find function {function_name}."
        )

    brace = text.find(
        "{",
        match.start(),
        match.end(),
    )

    return brace + 1


def _insert_function_prefix(
    path,
    function_name,
    marker,
    code,
):
    text = _read(
        path
    )

    if marker in text:
        return False

    insert_at = _function_open_brace_end(
        text,
        function_name,
    )

    block = (
        "\n"
        f"    // {marker}\n"
        + code.rstrip()
        + "\n"
    )

    text = (
        text[:insert_at]
        + block
        + text[insert_at:]
    )

    return _write_if_changed(
        path,
        text,
    )


def _write_header(
    *,
    permadeath,
    hm_free_field_moves,
    hm_progression_bypass,
    perma_repel,
    cap_candy,
    mom_bonus,
    party_heal,
    always_catch,
    force_shiny,
    permanent_megas,
    regional_evolution_postcards,
    level_caps,
    force_set_battle_style,
    disable_bag_in_trainer_battles,
    always_mirage_island=False,
    time_turner=False,
    weather_setter=False,
):
    values = {
        "RANDOMIZER_PERMADEATH": permadeath,
        "RANDOMIZER_HM_FREE_FIELD_MOVES": hm_free_field_moves,
        "RANDOMIZER_HM_PROGRESSION_BYPASS": hm_progression_bypass,
        "RANDOMIZER_PERMA_REPEL": perma_repel,
        "RANDOMIZER_CAP_CANDY": cap_candy,
        "RANDOMIZER_MOM_BONUS": mom_bonus,
        "RANDOMIZER_PARTY_HEAL": party_heal,
        "RANDOMIZER_TIME_TURNER": time_turner,
        "RANDOMIZER_WEATHER_SETTER": weather_setter,
        "RANDOMIZER_ALWAYS_CATCH": always_catch,
        "RANDOMIZER_FORCE_SHINY": force_shiny,
        "RANDOMIZER_PERMANENT_MEGAS": permanent_megas,
        "RANDOMIZER_REGIONAL_EVOLUTION_POSTCARDS": (
            regional_evolution_postcards
        ),
        "RANDOMIZER_LEVEL_CAPS": level_caps,
        "RANDOMIZER_ALWAYS_MIRAGE_ISLAND": always_mirage_island,
        "RANDOMIZER_FORCE_SET_BATTLE_STYLE": force_set_battle_style,
        "RANDOMIZER_DISABLE_TRAINER_BAG": disable_bag_in_trainer_battles,
    }

    lines = [
        "#ifndef GUARD_RANDOMIZER_GAME_OPTIONS_H",
        "#define GUARD_RANDOMIZER_GAME_OPTIONS_H",
        "",
        "/*",
        " * Generated by the standalone randomizer.",
        " *",
        " * Do not hand-edit this file. A new randomizer run rewrites it so",
        " * options from a previous ROM cannot leak into the next build.",
        " */",
        "",
    ]

    for macro, enabled in values.items():
        lines.append(
            f"#define {macro} "
            + ("1" if enabled else "0")
        )

    lines += [
        "",
        "#endif // GUARD_RANDOMIZER_GAME_OPTIONS_H",
        "",
    ]

    HEADER_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    changed = _write_if_changed(
        HEADER_PATH,
        "\n".join(lines),
    )

    return changed


def _instrument_level_caps_config():
    """Toggle the project's established hard level caps without redesigning them."""
    text = _read(CAPS_CONFIG_H)
    original = text

    guard_define = "#define GUARD_CONFIG_CAPS_H"
    include_line = '#include "randomizer_game_options.h"'

    if include_line not in text:
        if guard_define not in text:
            raise GameOptionPatchError(
                "Could not find the include guard in include/config/caps.h."
            )
        text = text.replace(
            guard_define,
            guard_define + "\n\n" + include_line,
            1,
        )

    if "#if RANDOMIZER_LEVEL_CAPS" not in text:
        section_pattern = re.compile(
            r"(?P<header>// Level Cap Configs\s*\n)"
            r"(?P<body>.*?)"
            r"(?=\n// EV Cap Constants)",
            re.DOTALL,
        )
        match = section_pattern.search(text)

        if match is None:
            raise GameOptionPatchError(
                "Could not find the Level Cap Configs section in "
                "include/config/caps.h."
            )

        body = match.group("body")

        def configured_value(macro, fallback):
            value_match = re.search(
                rf"(?m)^#define\s+{re.escape(macro)}\s+([^\s/]+)",
                body,
            )
            return value_match.group(1) if value_match else fallback

        enabled_exp_cap = configured_value(
            "B_EXP_CAP_TYPE",
            "EXP_CAP_HARD",
        )
        enabled_level_cap = configured_value(
            "B_LEVEL_CAP_TYPE",
            "LEVEL_CAP_FLAG_LIST",
        )
        enabled_rare_candy_cap = configured_value(
            "B_RARE_CANDY_CAP",
            "TRUE",
        )
        level_cap_variable = configured_value(
            "B_LEVEL_CAP_VARIABLE",
            "0",
        )
        level_cap_exp_up = configured_value(
            "B_LEVEL_CAP_EXP_UP",
            "FALSE",
        )

        replacement = (
            match.group("header")
            + "#if RANDOMIZER_LEVEL_CAPS\n"
            + f"#define B_EXP_CAP_TYPE                  {enabled_exp_cap}\n"
            + f"#define B_LEVEL_CAP_TYPE                {enabled_level_cap}\n"
            + f"#define B_RARE_CANDY_CAP                {enabled_rare_candy_cap}\n"
            + "#else\n"
            + "#define B_EXP_CAP_TYPE                  EXP_CAP_NONE\n"
            + "#define B_LEVEL_CAP_TYPE                LEVEL_CAP_NONE\n"
            + "#define B_RARE_CANDY_CAP                FALSE\n"
            + "#endif\n"
            + f"#define B_LEVEL_CAP_VARIABLE            {level_cap_variable}\n"
            + f"#define B_LEVEL_CAP_EXP_UP              {level_cap_exp_up}\n"
        )

        text = text[:match.start()] + replacement + text[match.end():]

    if text == original:
        return False

    return _write_if_changed(
        CAPS_CONFIG_H,
        text,
    )


def _instrument_pokemon_c(
    *,
    require_permadeath,
):
    changed = _ensure_include(
        POKEMON_C
    )

    text = _read(
        POKEMON_C
    )

    dead_supported = (
        "MON_DATA_IS_DEAD"
        in text
    )

    if (
        require_permadeath
        and not dead_supported
    ):
        raise GameOptionPatchError(
            "Permanent-death support was requested, but the existing "
            "MON_DATA_IS_DEAD implementation could not be found in "
            "src/pokemon.c."
        )

    marker = (
        "RANDOMIZER GAME OPTIONS: "
        "POKEMON DATA OVERRIDES"
    )

    if marker not in text:
        insert_at = _function_open_brace_end(
            text,
            "GetBoxMonData3",
        )

        lines = [
            "",
            f"    // {marker}",
            "#if RANDOMIZER_FORCE_SHINY",
            "    if (field == MON_DATA_IS_SHINY)",
            "        return TRUE;",
            "#endif",
        ]

        if dead_supported:
            lines += [
                "#if !RANDOMIZER_PERMADEATH",
                "    if (field == MON_DATA_IS_DEAD)",
                "        return FALSE;",
                "#endif",
            ]

        lines.append("")

        text = (
            text[:insert_at]
            + "\n".join(lines)
            + text[insert_at:]
        )

    permadeath_marker = (
        "RANDOMIZER GAME OPTIONS: "
        "PERMADEATH HP HANDLING"
    )

    if (
        dead_supported
        and permadeath_marker not in text
    ):
        declaration_pattern = re.compile(
            r"(?m)^(?P<indent>[ \t]*)u8 isDead;[ \t]*$"
        )

        declaration = declaration_pattern.search(
            text
        )

        if declaration is None:
            raise GameOptionPatchError(
                "Could not find the permanent-death state declaration "
                "in src/pokemon.c."
            )

        indent = declaration.group(
            "indent"
        )

        text = (
            text[:declaration.start()]
            + indent
            + "#if RANDOMIZER_PERMADEATH\n"
            + declaration.group(0)
            + "\n"
            + indent
            + "#endif"
            + text[declaration.end():]
        )

        hp_pattern = re.compile(
            r"(?m)^(?P<indent>[ \t]*)"
            r"// A non-Egg Pokémon that reaches 0 HP is permanently dead\.\n"
            r"(?P<body>.*?"
            r"if \(GetBoxMonData\(&mon->box, MON_DATA_IS_DEAD\)\)\n"
            r"[ \t]*mon->hp = 0;)",
            re.DOTALL,
        )

        hp_match = hp_pattern.search(
            text
        )

        if hp_match is None:
            raise GameOptionPatchError(
                "Could not find the existing permanent-death HP logic "
                "in src/pokemon.c."
            )

        indent = hp_match.group(
            "indent"
        )

        replacement = (
            indent
            + "// "
            + permadeath_marker
            + "\n"
            + indent
            + "#if RANDOMIZER_PERMADEATH\n"
            + hp_match.group(0)
            + "\n"
            + indent
            + "#endif"
        )

        text = (
            text[:hp_match.start()]
            + replacement
            + text[hp_match.end():]
        )

    if _write_if_changed(
        POKEMON_C,
        text,
    ):
        changed = True

    return changed


def _instrument_catch_rate():
    _ensure_include(
        BATTLE_SCRIPT_COMMANDS_C
    )

    return _insert_function_prefix(
        BATTLE_SCRIPT_COMMANDS_C,
        "ComputeCaptureOdds",
        (
            "RANDOMIZER GAME OPTIONS: "
            "GUARANTEED CAPTURE"
        ),
        """#if RANDOMIZER_ALWAYS_CATCH
    return CAPTURE_GUARANTEED;
#endif""",
    )


def _instrument_always_mirage_island():
    """Keep the established Mirage Island layout present while enabled."""

    _ensure_include(
        TIME_EVENTS_C
    )

    return _insert_function_prefix(
        TIME_EVENTS_C,
        "IsMirageIslandPresent",
        (
            "RANDOMIZER GAME OPTIONS: "
            "ALWAYS MIRAGE ISLAND"
        ),
        """#if RANDOMIZER_ALWAYS_MIRAGE_ISLAND
    return TRUE;
#endif""",
    )


def _instrument_force_set_battle_style():
    _ensure_include(
        BATTLE_MAIN_C
    )

    marker = (
        "RANDOMIZER DIFFICULTY OPTIONS: "
        "FORCE SET BATTLE STYLE"
    )
    text = _read(
        BATTLE_MAIN_C
    )

    if marker in text:
        return False

    anchor = (
        "    gBattleScripting.battleStyle = "
        "gSaveBlock2Ptr->optionsBattleStyle;"
    )

    if anchor not in text:
        raise GameOptionPatchError(
            "Could not find the battle-style initialization in "
            "src/battle_main.c."
        )

    block = f"""{anchor}
    // {marker}
#if RANDOMIZER_FORCE_SET_BATTLE_STYLE
    if (gBattleTypeFlags & BATTLE_TYPE_TRAINER)
        gBattleScripting.battleStyle = OPTIONS_BATTLE_STYLE_SET;
#endif"""

    return _write_if_changed(
        BATTLE_MAIN_C,
        text.replace(anchor, block, 1),
    )


def _instrument_disable_trainer_bag():
    _ensure_include(
        BATTLE_UTIL_C
    )

    return _insert_function_prefix(
        BATTLE_UTIL_C,
        "IsAllowedToUseBag",
        (
            "RANDOMIZER DIFFICULTY OPTIONS: "
            "DISABLE BAG IN TRAINER BATTLES"
        ),
        """#if RANDOMIZER_DISABLE_TRAINER_BAG
    if (gBattleTypeFlags & BATTLE_TYPE_TRAINER)
        return FALSE;
#endif""",
    )


def _instrument_field_item_use():
    _ensure_include(
        ITEM_USE_C
    )

    changed = False

    for function_name, macro in (
        (
            "ItemUseOutOfBattle_PartyRestorer",
            "RANDOMIZER_PARTY_HEAL",
        ),
        (
            "ItemUseOutOfBattle_CapCandy",
            "RANDOMIZER_CAP_CANDY",
        ),
        (
            "ItemUseOutOfBattle_TimeTurner",
            "RANDOMIZER_TIME_TURNER",
        ),
        (
            "ItemUseOutOfBattle_WeatherSetter",
            "RANDOMIZER_WEATHER_SETTER",
        ),
    ):
        marker = (
            "RANDOMIZER GAME OPTIONS: "
            "CUSTOM FIELD ITEMS: "
            + function_name
        )
        text = _read(
            ITEM_USE_C
        )

        if marker in text:
            old_guard = (
                f"    // {marker}\n"
                "#if !RANDOMIZER_FIELD_ITEMS\n"
            )
            new_guard = (
                f"    // {marker}\n"
                f"#if !{macro}\n"
            )
            text = text.replace(
                old_guard,
                new_guard,
                1,
            )
            did_change = _write_if_changed(
                ITEM_USE_C,
                text,
            )
        else:
            did_change = _insert_function_prefix(
                ITEM_USE_C,
                function_name,
                marker,
                f"""#if !{macro}
    DisplayDadsAdviceCannotUseItemMessage(
        taskId,
        gTasks[taskId].tUsingRegisteredKeyItem
    );
    return;
#endif""",
            )

        changed = (
            changed
            or did_change
        )

    return changed


def _instrument_perma_repel_use():
    _ensure_include(
        ITEM_USE_C
    )

    function_name = (
        "ItemUseOutOfBattle_PermaRepel"
    )
    marker = (
        "RANDOMIZER GAME OPTIONS: "
        "CUSTOM FIELD ITEMS: "
        + function_name
    )

    text = _read(
        ITEM_USE_C
    )

    # Migrate the first Game Options version, where Perma Repel shared the
    # general custom-field-item switch.
    if marker in text:
        old_guard = (
            f"    // {marker}\n"
            "#if !RANDOMIZER_FIELD_ITEMS\n"
        )
        new_guard = (
            f"    // {marker}\n"
            "#if !RANDOMIZER_PERMA_REPEL\n"
        )
        text = text.replace(
            old_guard,
            new_guard,
            1,
        )

        return _write_if_changed(
            ITEM_USE_C,
            text,
        )

    return _insert_function_prefix(
        ITEM_USE_C,
        function_name,
        marker,
        """#if !RANDOMIZER_PERMA_REPEL
    DisplayDadsAdviceCannotUseItemMessage(
        taskId,
        gTasks[taskId].tUsingRegisteredKeyItem
    );
    return;
#endif""",
    )


def _instrument_hm_tool_use():
    _ensure_include(
        ITEM_USE_C
    )

    changed = False

    for function_name in (
        "ItemUseOutOfBattle_FlashTool",
        "ItemUseOutOfBattle_DigTool",
        "ItemUseOutOfBattle_TeleportTool",
        "ItemUseOutOfBattle_FlyTool",
    ):
        did_change = _insert_function_prefix(
            ITEM_USE_C,
            function_name,
            (
                "RANDOMIZER GAME OPTIONS: "
                "HM-FREE FIELD TOOLS: "
                + function_name
            ),
            """#if !RANDOMIZER_HM_FREE_FIELD_MOVES
    DisplayDadsAdviceCannotUseItemMessage(
        taskId,
        gTasks[taskId].tUsingRegisteredKeyItem
    );
    return;
#endif""",
        )

        changed = (
            changed
            or did_change
        )

    return changed


def _instrument_field_item_grant():
    _ensure_include(
        NEW_GAME_C
    )

    text = _read(
        NEW_GAME_C
    )

    # Remove the legacy patcher's duplicate grant block. The established
    # items are already granted earlier in this function and must be gated
    # in place instead of added a second time.
    legacy_pattern = re.compile(
        r"\n    // RANDOMIZER GAME OPTIONS: STARTING FIELD ITEMS\n"
        r"#if RANDOMIZER_FIELD_ITEMS\n"
        r"    AddBagItem\(ITEM_PARTY_RESTORER, 1\);\n"
        r"    AddBagItem\(ITEM_CAP_CANDY, 1\);\n"
        r"    AddBagItem\(ITEM_PERMA_REPEL, 1\);\n"
        r"#endif"
    )

    text = legacy_pattern.sub(
        "",
        text,
        count=1,
    )

    # Level to cap now lives in the Pokémon party menu. Remove the old
    # key-item grant from an already-instrumented game as well as from a
    # fresh game source, regardless of whether the option is enabled.
    old_candy_grant = (
        "    // RANDOMIZER GAME OPTIONS: STARTING CAP CANDY\n"
        "#if RANDOMIZER_CAP_CANDY\n"
        "    AddBagItem(ITEM_CAP_CANDY, 1);\n"
        "#endif\n"
    )
    text = text.replace(old_candy_grant, "", 1)

    party_marker = (
        "RANDOMIZER GAME OPTIONS: STARTING PARTY HEAL"
    )
    repel_marker = (
        "RANDOMIZER GAME OPTIONS: STARTING PERMA REPEL"
    )
    time_marker = (
        "RANDOMIZER GAME OPTIONS: STARTING TIME TURNER"
    )
    weather_marker = (
        "RANDOMIZER GAME OPTIONS: STARTING WEATHER SETTER"
    )

    replacement = f"""    // {party_marker}
#if RANDOMIZER_PARTY_HEAL
    AddBagItem(ITEM_PARTY_RESTORER, 1);
#endif
    // {repel_marker}
#if RANDOMIZER_PERMA_REPEL
    AddBagItem(ITEM_PERMA_REPEL, 1);
#endif
    // {time_marker}
#if RANDOMIZER_TIME_TURNER
    AddBagItem(ITEM_TIME_TURNER, 1);
#endif
    // {weather_marker}
#if RANDOMIZER_WEATHER_SETTER
    AddBagItem(ITEM_WEATHER_SETTER, 1);
#endif"""

    if party_marker not in text:
        field_block = """    /*
     * Randomizer utility Key Items.
     */
    AddBagItem(ITEM_PARTY_RESTORER, 1);
    AddBagItem(ITEM_CAP_CANDY, 1);
    AddBagItem(ITEM_PERMA_REPEL, 1);"""

        migrated_patterns = (
            re.compile(
                r"    // RANDOMIZER GAME OPTIONS: "
                r"STARTING SUPPORT FIELD ITEMS\n"
                r"#if RANDOMIZER_FIELD_ITEMS\n.*?#endif\n"
                r"    // RANDOMIZER GAME OPTIONS: "
                r"STARTING PERMA REPEL\n"
                r"#if RANDOMIZER_PERMA_REPEL\n.*?#endif",
                re.DOTALL,
            ),
            re.compile(
                r"    // RANDOMIZER GAME OPTIONS: "
                r"STARTING CUSTOM FIELD ITEMS\n"
                r"#if RANDOMIZER_FIELD_ITEMS\n.*?#endif",
                re.DOTALL,
            ),
        )

        migrated = False

        for pattern in migrated_patterns:
            if pattern.search(text):
                text = pattern.sub(
                    replacement,
                    text,
                    count=1,
                )
                migrated = True
                break

        if not migrated and field_block in text:
            text = text.replace(
                field_block,
                replacement,
                1,
            )
            migrated = True

        if not migrated:
            raise GameOptionPatchError(
                "Could not find the existing custom field-item grants "
                "in src/new_game.c."
            )

    # Upgrade an already-instrumented build from the original three
    # independently gated utility items without disturbing their settings.
    if time_marker not in text:
        repel_block = f"""    // {repel_marker}
#if RANDOMIZER_PERMA_REPEL
    AddBagItem(ITEM_PERMA_REPEL, 1);
#endif"""
        time_block = f"""{repel_block}
    // {time_marker}
#if RANDOMIZER_TIME_TURNER
    AddBagItem(ITEM_TIME_TURNER, 1);
#endif"""

        if repel_block not in text:
            raise GameOptionPatchError(
                "Could not place the Time Turner grant in src/new_game.c."
            )

        text = text.replace(repel_block, time_block, 1)

    if weather_marker not in text:
        time_block = f"""    // {time_marker}
#if RANDOMIZER_TIME_TURNER
    AddBagItem(ITEM_TIME_TURNER, 1);
#endif"""
        weather_block = f"""{time_block}
    // {weather_marker}
#if RANDOMIZER_WEATHER_SETTER
    AddBagItem(ITEM_WEATHER_SETTER, 1);
#endif"""

        if time_block not in text:
            raise GameOptionPatchError(
                "Could not place the Weather Setter grant in src/new_game.c."
            )

        text = text.replace(time_block, weather_block, 1)

    hm_marker = (
        "RANDOMIZER GAME OPTIONS: "
        "STARTING HM-FREE FIELD TOOLS"
    )

    if hm_marker not in text:
        hm_block = """    /*
     * Randomizer utility HM tools
     */
    AddBagItem(ITEM_FLY_TOOL, 1);
    AddBagItem(ITEM_FLASH_TOOL, 1);
    AddBagItem(ITEM_DIG_TOOL, 1);
    AddBagItem(ITEM_TELEPORT_TOOL, 1);"""

        if hm_block not in text:
            raise GameOptionPatchError(
                "Could not find the existing HM-free field-tool grants "
                "in src/new_game.c."
            )

        hm_replacement = (
            f"    // {hm_marker}\n"
            + "#if RANDOMIZER_HM_FREE_FIELD_MOVES\n"
            + hm_block
            + "\n#endif"
        )

        text = text.replace(
            hm_block,
            hm_replacement,
            1,
        )

    return _write_if_changed(
        NEW_GAME_C,
        text,
    )


def _configure_mom_running_shoes_bonus(enabled):
    """Grant the fixed bonus in Mom's shared running-shoes scene.

    Both gender-specific triggers call this routine. Replace only our own
    marked sections, preserving all other changes to Littleroot's map script.
    """
    text = _read(LITTLEROOT_SCRIPTS)
    bonus_start = "\t@ RANDOMIZER MOM BONUS START\n"
    bonus_end = "\t@ RANDOMIZER MOM BONUS END\n"
    text_start = "\n@ RANDOMIZER MOM BONUS TEXT START\n"
    text_end = "@ RANDOMIZER MOM BONUS TEXT END\n"

    for start, end in ((bonus_start, bonus_end), (text_start, text_end)):
        if text.count(start) != text.count(end) or text.count(start) > 1:
            raise GameOptionPatchError(
                "Incomplete Mom bonus section in "
                "data/maps/LittlerootTown/scripts.inc."
            )
        if start in text:
            before, remainder = text.split(start, 1)
            _, after = remainder.split(end, 1)
            text = before + after

    if enabled:
        anchor = (
            "LittlerootTown_EventScript_GiveRunningShoes::"
        )
        if text.count(anchor) != 1:
            raise GameOptionPatchError(
                "Could not identify Mom's running-shoes scene."
            )
        before, scene = text.split(anchor, 1)
        flag_line = "\tsetflag FLAG_RECEIVED_RUNNING_SHOES\n"
        if scene.count(flag_line) != 1:
            raise GameOptionPatchError(
                "Could not identify the running-shoes gift in Littleroot."
            )
        gift = (
            bonus_start
            + "\tmsgbox LittlerootTown_Text_MomBonusBalls, MSGBOX_DEFAULT\n"
            + "\tgiveitem ITEM_ULTRA_BALL, 99\n"
            + "\taddmoney 999999\n"
            + "\tmsgbox LittlerootTown_Text_MomBonusMoney, MSGBOX_DEFAULT\n"
            + bonus_end
        )
        scene = scene.replace(flag_line, flag_line + gift, 1)
        text = before + anchor + scene
        text += (
            text_start
            + "LittlerootTown_Text_MomBonusBalls:\n"
            + '\t.string "MOM: Take these ULTRA BALLS, too!$"\n\n'
            + "LittlerootTown_Text_MomBonusMoney:\n"
            + '\t.string "MOM: And here is some spending money!$"\n'
            + text_end
        )

    return _write_if_changed(LITTLEROOT_SCRIPTS, text)


def _instrument_hm_free_checkfieldmove():
    _ensure_include(
        SCRCMD_C
    )

    marker = (
        "RANDOMIZER GAME OPTIONS: "
        "HM-FREE SCRIPT INTERACTIONS"
    )
    text = _read(
        SCRCMD_C
    )

    if marker in text:
        return False

    anchor = "    move = FieldMove_GetMoveId(fieldMove);"

    if anchor not in text:
        raise GameOptionPatchError(
            "Could not find the learned-move scan in src/scrcmd.c."
        )

    block = f"""    // {marker}
#if RANDOMIZER_HM_FREE_FIELD_MOVES
    if (fieldMove == FIELD_MOVE_CUT
     || fieldMove == FIELD_MOVE_FLASH
     || fieldMove == FIELD_MOVE_ROCK_SMASH
     || fieldMove == FIELD_MOVE_STRENGTH
     || fieldMove == FIELD_MOVE_SURF
     || fieldMove == FIELD_MOVE_FLY
     || fieldMove == FIELD_MOVE_DIVE
     || fieldMove == FIELD_MOVE_WATERFALL
     || fieldMove == FIELD_MOVE_ROCK_CLIMB
     || fieldMove == FIELD_MOVE_DEFOG)
    {{
        gSpecialVar_Result = 0;
        gSpecialVar_0x8004 = GetMonData(
            &gParties[B_TRAINER_PLAYER][0],
            MON_DATA_SPECIES
        );
        return FALSE;
    }}
#endif

"""

    text = text.replace(
        anchor,
        block + anchor,
        1,
    )

    return _write_if_changed(
        SCRCMD_C,
        text,
    )


def _instrument_hm_progression_bypass():
    _ensure_include(
        FIELD_MOVE_H
    )

    return _insert_function_prefix(
        FIELD_MOVE_H,
        "IsFieldMoveUnlocked",
        (
            "RANDOMIZER GAME OPTIONS: "
            "HM PROGRESSION BYPASS"
        ),
        """#if RANDOMIZER_HM_FREE_FIELD_MOVES
    // Rock Climb is disabled by Expansion's normal feature config rather
    // than a Hoenn badge. The combined HM-free option explicitly enables it.
    if (fieldMove == FIELD_MOVE_ROCK_CLIMB)
        return TRUE;
#endif

#if RANDOMIZER_HM_PROGRESSION_BYPASS
    switch (fieldMove)
    {
    case FIELD_MOVE_CUT:
    case FIELD_MOVE_FLASH:
    case FIELD_MOVE_ROCK_SMASH:
    case FIELD_MOVE_STRENGTH:
    case FIELD_MOVE_SURF:
    case FIELD_MOVE_FLY:
    case FIELD_MOVE_DIVE:
    case FIELD_MOVE_WATERFALL:
    case FIELD_MOVE_ROCK_CLIMB:
    case FIELD_MOVE_DEFOG:
        return TRUE;
    default:
        break;
    }
#endif""",
    )


def _instrument_perma_repel_encounters():
    _ensure_include(
        WILD_ENCOUNTER_C
    )

    marker = (
        "RANDOMIZER GAME OPTIONS: "
        "PERMA REPEL ENCOUNTER CHECK"
    )
    text = _read(
        WILD_ENCOUNTER_C
    )

    if marker in text:
        return False

    anchor = "    if (FlagGet(FLAG_SYS_PERMA_REPEL))"

    if anchor not in text:
        raise GameOptionPatchError(
            "Could not find the existing Perma Repel encounter check "
            "in src/wild_encounter.c."
        )

    text = text.replace(
        anchor,
        (
            f"    // {marker}\n"
            "    if (RANDOMIZER_PERMA_REPEL "
            "&& FlagGet(FLAG_SYS_PERMA_REPEL))"
        ),
        1,
    )

    return _write_if_changed(
        WILD_ENCOUNTER_C,
        text,
    )


def _configure_hm_free_field_moves(
    *,
    enabled,
):
    """
    Select the already-established field-move script implementation.

    The clean packaged baseline contains the normal move requirements. The
    enabled templates contain this project's existing HM-free scripts. Copying
    one complete version on every run makes the option deterministic and keeps
    state from leaking between builds.
    """
    source_root = (
        HM_FREE_TEMPLATE_ROOT
        if enabled
        else BASELINE_ROOT
    )

    changed = False

    for relative_path in HM_FREE_SCRIPT_PATHS:
        source = (
            source_root
            / relative_path
        )
        destination = (
            ROOT
            / relative_path
        )

        if not source.exists():
            raise GameOptionPatchError(
                "Required HM field-move template is missing:\n"
                f"{source}"
            )

        if _write_if_changed(
            destination,
            _read(source),
        ):
            changed = True

    return changed


def _validate_custom_field_items():
    text = _read(
        ITEMS_H
    )

    missing = [
        item
        for item in CUSTOM_FIELD_ITEMS
        if f"[{item}]" not in text
    ]

    if missing:
        raise GameOptionPatchError(
            "Custom field item definitions are missing from "
            "src/data/items.h:\n  "
            + "\n  ".join(missing)
        )


def _validate_permanent_mega_support():
    form_change_text = _read(
        FORM_CHANGE_TABLES_H
    )

    mapping_count = len(
        re.findall(
            r"\{\s*FORM_CHANGE_BATTLE_MEGA_EVOLUTION_ITEM\s*,",
            form_change_text,
        )
    )

    if mapping_count == 0:
        raise GameOptionPatchError(
            "No Mega Stone form-change mappings were found in "
            "src/data/pokemon/form_change_tables.h."
        )

    required_source_markers = {
        ITEM_C: (
            "RANDOMIZER_PERMANENT_MEGAS",
            "IsPermanentMegaStone",
            "ItemUseOutOfBattle_EvolutionStone",
        ),
        POKEMON_C: (
            "GetPermanentMegaEvolutionTarget",
            "FORM_CHANGE_BATTLE_MEGA_EVOLUTION_ITEM",
        ),
        BATTLE_UTIL_C: (
            "RANDOMIZER_PERMANENT_MEGAS",
            "Permanent Mega Stones are party-menu evolution items",
        ),
    }

    for path, markers in required_source_markers.items():
        text = _read(path)
        missing = [
            marker
            for marker in markers
            if marker not in text
        ]
        if missing:
            raise GameOptionPatchError(
                "Permanent Mega Evolution support is incomplete in "
                f"{path.relative_to(ROOT)}:\n  "
                + "\n  ".join(missing)
            )

    return mapping_count


def _validate_regional_evolution_support():
    item_data = _read(
        ITEMS_H
    )
    item_constants = _read(
        ITEM_CONSTANTS_H
    )
    pokemon_source = _read(
        POKEMON_C
    )

    missing_definitions = [
        item
        for item in REGIONAL_POSTCARD_ITEMS
        if f"[{item}]" not in item_data
    ]
    missing_constants = [
        item
        for item in REGIONAL_POSTCARD_ITEMS
        if item not in item_constants
    ]

    if missing_definitions or missing_constants:
        missing = sorted(
            set(missing_definitions + missing_constants)
        )
        raise GameOptionPatchError(
            "Regional postcard item support is incomplete:\n  "
            + "\n  ".join(missing)
        )

    required_source_markers = (
        "RANDOMIZER_REGIONAL_EVOLUTION_POSTCARDS",
        "ITEM_ALOLA_POSTCARD",
        "ITEM_GALAR_POSTCARD",
        "ITEM_HISUI_POSTCARD",
    )
    missing_markers = [
        marker
        for marker in required_source_markers
        if marker not in pokemon_source
    ]

    if missing_markers:
        raise GameOptionPatchError(
            "Regional evolution support is incomplete in src/pokemon.c:\n  "
            + "\n  ".join(missing_markers)
        )


def _configure_ursaring_regional_evolutions(enabled):
    """Make both Ursaluna forms reachable with a directly used Peat Block."""
    text = _read(
        URSARING_SPECIES_H
    )
    original = text

    active_pattern = re.compile(
        rf"(?ms)^[ \t]*// {re.escape(URSARING_REGIONAL_START)}\n"
        rf".*?"
        rf"^[ \t]*// {re.escape(URSARING_REGIONAL_END)}"
    )
    active_match = active_pattern.search(
        text
    )

    if not enabled:
        if active_match is None:
            return False

        indent_match = re.match(
            r"[ \t]*",
            active_match.group(0),
        )
        indent = indent_match.group(0)
        replacement = (
            f"{indent}.evolutions = EVOLUTION("
            "{EVO_ITEM, ITEM_PEAT_BLOCK, SPECIES_URSALUNA, "
            "CONDITIONS({IF_REGION, REGION_HISUI}, "
            "{IF_TIME, TIME_NIGHT})},\n"
            f"{indent}                        "
            "{EVO_NONE, 0, SPECIES_URSALUNA_BLOODMOON}),"
        )
        text = active_pattern.sub(
            replacement,
            text,
            count=1,
        )
        return _write_if_changed(
            URSARING_SPECIES_H,
            text,
        )

    if active_match is not None:
        return False

    clean_match = URSARING_EVOLUTION_PATTERN.search(
        text
    )
    if clean_match is None:
        raise GameOptionPatchError(
            "Could not find Ursaring's clean Peat Block evolution entries in "
            "src/data/pokemon/species_info/gen_2_families.h."
        )

    indent = clean_match.group("indent")
    replacement = (
        f"{indent}// {URSARING_REGIONAL_START}\n"
        f"{indent}.evolutions = EVOLUTION("
        "{EVO_ITEM, ITEM_PEAT_BLOCK, SPECIES_URSALUNA_BLOODMOON, "
        "CONDITIONS({IF_REGION, REGION_HISUI}, "
        "{IF_TIME, TIME_NIGHT})},\n"
        f"{indent}                        "
        "{EVO_ITEM, ITEM_PEAT_BLOCK, SPECIES_URSALUNA, "
        "CONDITIONS({IF_REGION, REGION_HISUI})}),\n"
        f"{indent}// {URSARING_REGIONAL_END}"
    )
    text = (
        text[:clean_match.start()]
        + replacement
        + text[clean_match.end():]
    )

    if text == original:
        return False

    return _write_if_changed(
        URSARING_SPECIES_H,
        text,
    )


def apply_game_options(
    *,
    permadeath=False,
    # Compatibility alias for the first Game Options build. It enables all
    # three optional received items, but does not enable HM-free field moves.
    field_items=False,
    hm_free_field_moves=False,
    hm_progression_bypass=False,
    perma_repel=False,
    cap_candy=False,
    mom_bonus=False,
    party_heal=False,
    time_turner=False,
    weather_setter=False,
    always_catch=False,
    force_shiny=False,
    permanent_megas=False,
    regional_evolution_postcards=False,
    level_caps=False,
    always_mirage_island=False,
    force_set_battle_style=False,
    disable_bag_in_trainer_battles=False,
):
    """
    Apply the selected game-rule toggles.

    C source instrumentation is permanent and idempotent. Every run rewrites
    randomizer_game_options.h, and the HM script pair is refreshed from either
    the clean baseline or the established enabled templates. This prevents a
    selection from leaking into the next build.
    """

    legacy_field_items = bool(
        field_items
    )

    options = {
        "permadeath": bool(
            permadeath
        ),
        "hm_free_field_moves": bool(
            hm_free_field_moves
        ),
        "hm_progression_bypass": bool(
            hm_progression_bypass
        ),
        "perma_repel": bool(
            perma_repel
            or legacy_field_items
        ),
        "cap_candy": bool(
            cap_candy
            or legacy_field_items
        ),
        "mom_bonus": bool(mom_bonus),
        "party_heal": bool(
            party_heal
            or legacy_field_items
        ),
        "time_turner": bool(
            time_turner
        ),
        "weather_setter": bool(
            weather_setter
        ),
        "always_catch": bool(
            always_catch
        ),
        "force_shiny": bool(
            force_shiny
        ),
        "permanent_megas": bool(
            permanent_megas
        ),
        "regional_evolution_postcards": bool(
            regional_evolution_postcards
        ),
        "level_caps": bool(
            level_caps
        ),
        "always_mirage_island": bool(
            always_mirage_island
        ),
        "force_set_battle_style": bool(
            force_set_battle_style
        ),
        "disable_bag_in_trainer_battles": bool(
            disable_bag_in_trainer_battles
        ),
    }

    if (
        options["perma_repel"]
        or options["cap_candy"]
        or options["party_heal"]
        or options["time_turner"]
        or options["weather_setter"]
    ):
        _validate_custom_field_items()

    permanent_mega_mapping_count = 0
    if options["permanent_megas"]:
        permanent_mega_mapping_count = (
            _validate_permanent_mega_support()
        )

    if options["regional_evolution_postcards"]:
        _validate_regional_evolution_support()

    print()
    print(
        "Configuring game options..."
    )

    header_changed = _write_header(
        **options
    )

    source_changes = []

    if _configure_mom_running_shoes_bonus(options["mom_bonus"]):
        source_changes.append("data/maps/LittlerootTown/scripts.inc")

    if _configure_ursaring_regional_evolutions(
        options["regional_evolution_postcards"]
    ):
        source_changes.append(
            "src/data/pokemon/species_info/gen_2_families.h"
        )

    if _instrument_level_caps_config():
        source_changes.append(
            "include/config/caps.h"
        )

    if _instrument_pokemon_c(
        require_permadeath=options[
            "permadeath"
        ],
    ):
        source_changes.append(
            "src/pokemon.c"
        )

    if _instrument_catch_rate():
        source_changes.append(
            "src/battle_script_commands.c"
        )

    if _instrument_always_mirage_island():
        source_changes.append(
            "src/time_events.c"
        )

    if _instrument_force_set_battle_style():
        source_changes.append(
            "src/battle_main.c"
        )

    if _instrument_disable_trainer_bag():
        source_changes.append(
            "src/battle_util.c"
        )

    if _configure_hm_free_field_moves(
        enabled=options[
            "hm_free_field_moves"
        ],
    ):
        source_changes.append(
            "data/scripts/field moves"
        )

    if _instrument_hm_free_checkfieldmove():
        source_changes.append(
            "src/scrcmd.c"
        )

    if _instrument_hm_progression_bypass():
        source_changes.append(
            "include/field_move.h"
        )

    if _instrument_perma_repel_encounters():
        source_changes.append(
            "src/wild_encounter.c"
        )

    field_item_use_changed = (
        _instrument_field_item_use()
    )

    perma_repel_use_changed = (
        _instrument_perma_repel_use()
    )

    hm_tool_use_changed = (
        _instrument_hm_tool_use()
    )

    if (
        field_item_use_changed
        or perma_repel_use_changed
        or hm_tool_use_changed
    ):
        source_changes.append(
            "src/item_use.c"
        )

    if _instrument_field_item_grant():
        source_changes.append(
            "src/new_game.c"
        )

    print(
        "  generated header: "
        + (
            "updated"
            if header_changed
            else "unchanged"
        )
    )

    if source_changes:
        print(
            "  game-option source updates: "
            + ", ".join(
                source_changes
            )
        )
    else:
        print(
            "  source instrumentation: already installed"
        )

    print(
        "  Permanent death: "
        + (
            "ON"
            if options["permadeath"]
            else "off"
        )
    )
    print(
        "  HMs without learning them and field items: "
        + (
            "ON"
            if options["hm_free_field_moves"]
            else "off"
        )
    )
    print(
        "  Remove HM progression requirements: "
        + (
            "ON"
            if options[
                "hm_progression_bypass"
            ]
            else "off"
        )
    )
    print(
        "  Perma Repel: "
        + (
            "ON"
            if options["perma_repel"]
            else "off"
        )
    )
    print(
        "  Level to cap menu action: "
        + (
            "ON"
            if options["cap_candy"]
            else "off"
        )
    )
    print(
        "  Mom's running-shoes bonus: "
        + ("ON" if options["mom_bonus"] else "off")
    )
    print(
        "  Party Heal: "
        + (
            "ON"
            if options["party_heal"]
            else "off"
        )
    )
    print(
        "  Time Turner: "
        + (
            "ON"
            if options["time_turner"]
            else "off"
        )
    )
    print(
        "  Weather Setter: "
        + (
            "ON"
            if options["weather_setter"]
            else "off"
        )
    )
    print(
        "  100% catch rate: "
        + (
            "ON"
            if options["always_catch"]
            else "off"
        )
    )
    print(
        "  Force all Pokémon shiny: "
        + (
            "ON"
            if options["force_shiny"]
            else "off"
        )
    )
    print(
        "  Permanent Mega Evolutions: "
        + (
            "ON ("
            + str(permanent_mega_mapping_count)
            + " stone-driven transformations)"
            if options["permanent_megas"]
            else "off"
        )
    )
    print(
        "  Regional evolution postcards: "
        + (
            "ON (13 regional branches plus Bloodmoon Ursaluna)"
            if options["regional_evolution_postcards"]
            else "off"
        )
    )
    print(
        "  Level caps: "
        + (
            "ON (existing hard badge/story caps)"
            if options["level_caps"]
            else "off"
        )
    )
    print(
        "  Mirage Island always present: "
        + (
            "ON"
            if options["always_mirage_island"]
            else "off"
        )
    )
    print(
        "  Force Set battle style: "
        + (
            "ON"
            if options["force_set_battle_style"]
            else "off"
        )
    )
    print(
        "  Disable Bag items in trainer battles: "
        + (
            "ON"
            if options["disable_bag_in_trainer_battles"]
            else "off"
        )
    )

    return options
