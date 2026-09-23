#!/usr/bin/env python3

import ast
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import game_options


ROOT = Path(__file__).resolve().parent.parent


class SkipIntroTests(unittest.TestCase):
    def test_generated_header_controls_skip_intro_independently(self):
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
                    skip_intro=True,
                )

            text = header.read_text(encoding="utf-8")

        self.assertIn("#define RANDOMIZER_SKIP_INTRO 1", text)
        self.assertIn("#define RANDOMIZER_MOM_BONUS 0", text)

    def test_littleroot_bypass_preserves_required_story_state(self):
        event_scripts = (ROOT / "data/event_scripts.s").read_text(
            encoding="utf-8"
        )
        littleroot = (
            ROOT / "data/maps/LittlerootTown/scripts.inc"
        ).read_text(encoding="utf-8")
        skip_block = littleroot.split(
            "LittlerootTown_EventScript_SkipIntro::", 1
        )[1].split("#endif", 1)[0]

        self.assertIn('#include "randomizer_game_options.h"', event_scripts)
        self.assertIn("#if RANDOMIZER_SKIP_INTRO", littleroot)
        self.assertIn("VAR_LITTLEROOT_INTRO_STATE, 7", skip_block)
        self.assertIn("VAR_LITTLEROOT_TOWN_STATE, 2", skip_block)
        self.assertIn("VAR_LITTLEROOT_RIVAL_STATE, 3", skip_block)
        self.assertIn("VAR_ROUTE101_STATE, 2", skip_block)
        self.assertIn("FLAG_SET_WALL_CLOCK", skip_block)
        self.assertIn("FLAG_MET_RIVAL_MOM", skip_block)
        self.assertIn("FLAG_HIDE_MAP_NAME_POPUP", skip_block)

    def test_new_game_initializes_time_without_clock_scene(self):
        new_game = (ROOT / "src/new_game.c").read_text(encoding="utf-8")

        guarded = new_game.split("#if RANDOMIZER_SKIP_INTRO", 1)[1].split(
            "#endif", 1
        )[0]
        self.assertIn("FlagSet(FLAG_SET_WALL_CLOCK);", guarded)
        self.assertIn("InitTimeBasedEvents();", guarded)

    def test_master_randomizer_exposes_disabled_by_default_option(self):
        source = (ROOT / "randomizer/master_randomizer.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(source)
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

        self.assertIn("game_skip_intro", parameters)
        self.assertIsInstance(parameters["game_skip_intro"], ast.Constant)
        self.assertFalse(parameters["game_skip_intro"].value)
        self.assertIn('"--skip-intro"', source)
        self.assertIn("skip_intro=game_skip_intro", source)

    def test_gui_labels_and_forwards_skip_intro(self):
        gui = (ROOT / "randomizer/gui.py").read_text(encoding="utf-8")

        self.assertIn('text="Skip intro"', gui)
        self.assertIn("self.game_skip_intro_var", gui)
        self.assertIn("game_skip_intro=game_skip_intro", gui)


if __name__ == "__main__":
    unittest.main()
