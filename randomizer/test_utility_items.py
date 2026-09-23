#!/usr/bin/env python3

import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import game_options


ROOT = Path(__file__).resolve().parent.parent


class UtilityItemTests(unittest.TestCase):
    def test_item_constants_and_definitions_exist(self):
        constants = (ROOT / "include/constants/items.h").read_text(
            encoding="utf-8"
        )
        items = (ROOT / "src/data/items.h").read_text(encoding="utf-8")

        self.assertIn("ITEM_TIME_TURNER", constants)
        self.assertIn("ITEM_WEATHER_SETTER", constants)
        self.assertIn("[ITEM_TIME_TURNER]", items)
        self.assertIn("ItemUseOutOfBattle_TimeTurner", items)
        self.assertIn("[ITEM_WEATHER_SETTER]", items)
        self.assertIn("ItemUseOutOfBattle_WeatherSetter", items)

    def test_time_turner_supports_every_used_time_period(self):
        item_use = (ROOT / "src/item_use.c").read_text(encoding="utf-8")
        overworld = (ROOT / "src/overworld.c").read_text(encoding="utf-8")

        self.assertIn("UTILITY_TIME_DAY = 12", item_use)
        self.assertIn("UTILITY_TIME_EVENING = 19", item_use)
        self.assertIn("UTILITY_TIME_NIGHT = 22", item_use)
        self.assertIn("SetTimeOfDay(input);", item_use)
        self.assertIn("UpdateTimeOfDay(TRUE);", item_use)
        self.assertIn("#if !RANDOMIZER_TIME_TURNER", overworld)
        self.assertIn("sHoursOverride = 0;", overworld)

    def test_weather_setter_includes_evolution_weather(self):
        item_use = (ROOT / "src/item_use.c").read_text(encoding="utf-8")
        species_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted(
                (ROOT / "src/data/pokemon/species_info").rglob("*.h")
            )
        )

        self.assertIn("{COMPOUND_STRING(\"Rain\"), WEATHER_RAIN}", item_use)
        self.assertIn(
            "{COMPOUND_STRING(\"Fog\"), WEATHER_FOG_HORIZONTAL}",
            item_use,
        )
        self.assertIn(
            "{COMPOUND_STRING(\"Diagonal Fog\"), WEATHER_FOG_DIAGONAL}",
            item_use,
        )
        self.assertNotIn("IF_WEATHER, WEATHER_SNOW", species_text)
        self.assertEqual(species_text.count("IF_WEATHER, WEATHER_RAIN"), 2)
        self.assertEqual(species_text.count("IF_WEATHER, WEATHER_FOG"), 2)
        self.assertIn("SetWeather(input);", item_use)

    def test_generated_header_resets_items_independently(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            header = Path(temp_dir) / "randomizer_game_options.h"

            with mock.patch.object(game_options, "HEADER_PATH", header):
                game_options._write_header(
                    permadeath=False,
                    hm_free_field_moves=False,
                    hm_progression_bypass=False,
                    perma_repel=False,
                    cap_candy=False,
                    party_heal=False,
                    always_catch=False,
                    force_shiny=False,
                    permanent_megas=False,
                    regional_evolution_postcards=False,
                    level_caps=False,
                    force_set_battle_style=False,
                    disable_bag_in_trainer_battles=False,
                    time_turner=True,
                    weather_setter=False,
                )

            text = header.read_text(encoding="utf-8")

        self.assertIn("#define RANDOMIZER_TIME_TURNER 1", text)
        self.assertIn("#define RANDOMIZER_WEATHER_SETTER 0", text)

    def test_starting_grants_are_independently_guarded(self):
        new_game = (ROOT / "src/new_game.c").read_text(encoding="utf-8")

        self.assertIn("#if RANDOMIZER_TIME_TURNER", new_game)
        self.assertIn("AddBagItem(ITEM_TIME_TURNER, 1);", new_game)
        self.assertIn("#if RANDOMIZER_WEATHER_SETTER", new_game)
        self.assertIn("AddBagItem(ITEM_WEATHER_SETTER, 1);", new_game)

    def test_master_randomizer_accepts_both_options(self):
        tree = ast.parse(
            (ROOT / "randomizer/master_randomizer.py").read_text(
                encoding="utf-8"
            )
        )
        randomize = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "randomize"
        )
        arguments = [argument.arg for argument in randomize.args.args]
        defaults = [None] * (
            len(arguments) - len(randomize.args.defaults)
        ) + list(randomize.args.defaults)
        parameters = dict(zip(arguments, defaults))

        for name in ("game_time_turner", "game_weather_setter"):
            self.assertIn(name, parameters)
            self.assertIsInstance(parameters[name], ast.Constant)
            self.assertFalse(parameters[name].value)

    def test_mom_bonus_uses_a_fixed_non_randomized_grant(self):
        options = (ROOT / "randomizer/game_options.py").read_text(
            encoding="utf-8"
        )
        script = (
            ROOT / "data/maps/LittlerootTown/scripts.inc"
        ).read_text(encoding="utf-8")
        item_source = (ROOT / "src/item.c").read_text(encoding="utf-8")

        native_call = (
            "callnative GiveMomBonusUltraBalls, requests_effects=1"
        )
        self.assertIn(native_call, options)
        self.assertIn(native_call, script)
        self.assertIn("AddBagItem(ITEM_ULTRA_BALL, 99);", item_source)

    def test_expanded_bag_uses_saveblock3_and_migrates_old_saves(self):
        constants = (ROOT / "include/constants/global.h").read_text(
            encoding="utf-8"
        )
        globals_source = (ROOT / "include/global.h").read_text(
            encoding="utf-8"
        )
        item_source = (ROOT / "src/item.c").read_text(encoding="utf-8")
        save_source = (ROOT / "src/save.c").read_text(encoding="utf-8")

        self.assertIn("#define BAG_ITEMS_COUNT 160", constants)
        self.assertIn("#define BAG_KEYITEMS_COUNT 50", constants)
        self.assertIn("#define BAG_POKEBALLS_COUNT 32", constants)
        self.assertIn("struct LegacyBag legacyBag;", globals_source)
        self.assertIn("struct Bag bag;", globals_source)
        self.assertIn("MigrateBagSaveData", item_source)
        self.assertIn("MigrateBagSaveData();", save_source)


if __name__ == "__main__":
    unittest.main()
