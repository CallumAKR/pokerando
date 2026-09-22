#!/usr/bin/env python3

import random
import tempfile
import unittest
from pathlib import Path

from difficulty_options import (
    _choose_moves,
    _role,
    _transform_section,
    apply_trainer_difficulty,
)


class DifficultyOptionTests(unittest.TestCase):
    def setUp(self):
        self.species = {
            "stats": {
                "hp": 80,
                "attack": 35,
                "defense": 70,
                "speed": 105,
                "sp_attack": 145,
                "sp_defense": 90,
            },
            "types": ("TYPE_ELECTRIC", "TYPE_ICE"),
            "abilities": ("ABILITY_STATIC", "ABILITY_LEVITATE"),
            "learnset": "sTestLevelUpLearnset",
        }
        self.moves = {
            "MOVE_THUNDERBOLT": {
                "type": "TYPE_ELECTRIC",
                "category": "DAMAGE_CATEGORY_SPECIAL",
                "power": 90,
                "accuracy": 100,
                "priority": 0,
                "effect": "EFFECT_HIT",
            },
            "MOVE_ICE_BEAM": {
                "type": "TYPE_ICE",
                "category": "DAMAGE_CATEGORY_SPECIAL",
                "power": 90,
                "accuracy": 100,
                "priority": 0,
                "effect": "EFFECT_HIT",
            },
            "MOVE_PSYCHIC": {
                "type": "TYPE_PSYCHIC",
                "category": "DAMAGE_CATEGORY_SPECIAL",
                "power": 90,
                "accuracy": 100,
                "priority": 0,
                "effect": "EFFECT_HIT",
            },
            "MOVE_TACKLE": {
                "type": "TYPE_NORMAL",
                "category": "DAMAGE_CATEGORY_PHYSICAL",
                "power": 40,
                "accuracy": 100,
                "priority": 0,
                "effect": "EFFECT_HIT",
            },
            "MOVE_CALM_MIND": {
                "type": "TYPE_PSYCHIC",
                "category": "DAMAGE_CATEGORY_STATUS",
                "power": 0,
                "accuracy": 0,
                "priority": 0,
                "effect": "EFFECT_CALM_MIND",
            },
        }

    def test_role_uses_finalized_randomized_stats(self):
        role = _role(self.species)
        self.assertEqual(role["attack_style"], "special")
        self.assertEqual(role["category"], "DAMAGE_CATEGORY_SPECIAL")
        self.assertIn(role["nature"], {"NATURE_MODEST", "NATURE_TIMID"})

    def test_moveset_uses_current_types_and_role(self):
        role = _role(self.species)
        result = _choose_moves(
            "SPECIES_TESTMON",
            self.species,
            40,
            role,
            self.moves,
            {
                "SPECIES_TESTMON": tuple(self.moves),
            },
            {
                "sTestLevelUpLearnset": (),
            },
            random.Random(7),
        )
        self.assertEqual(len(result), 4)
        self.assertIn("MOVE_THUNDERBOLT", result)
        self.assertIn("MOVE_ICE_BEAM", result)
        self.assertIn("MOVE_PSYCHIC", result)
        self.assertIn("MOVE_CALM_MIND", result)
        self.assertNotIn("MOVE_TACKLE", result)

    def test_major_trainer_build_is_generated_after_level_boost(self):
        section = """=== TRAINER_TEST ===
Name: TEST
Class: Leader
Pic: Leader
Gender: Female
Music: Female
Double Battle: No
AI: Check Bad Move

SPECIES_TESTMON
Level: 40
IVs: 0 HP / 0 Atk / 0 Def / 0 SpA / 0 SpD / 0 Spe
"""
        result, counters = _transform_section(
            section,
            rng=random.Random(11),
            species_data={"SPECIES_TESTMON": self.species},
            display_names={},
            ability_ratings={"ABILITY_STATIC": 4, "ABILITY_LEVITATE": 7},
            move_data=self.moves,
            learnables={"SPECIES_TESTMON": tuple(self.moves)},
            level_up_moves={"sTestLevelUpLearnset": ()},
            ai_mode="fair",
            level_boost=5,
            level_scope="major",
            iv_mode="perfect",
            competitive_builds=True,
            improved_movesets=True,
            held_items=True,
            trainer_items=True,
        )
        self.assertIn("Level: 45", result)
        self.assertIn("31 HP / 31 Atk / 31 Def / 31 SpA / 31 SpD / 31 Spe", result)
        self.assertIn("Ability: ABILITY_LEVITATE", result)
        self.assertIn("EVs: 252 SpA / 252 Spe / 4 HP", result)
        self.assertRegex(result, r"Nature: NATURE_(MODEST|TIMID)")
        self.assertIn(" @ ITEM_", result)
        self.assertIn("Items: ITEM_", result)
        self.assertEqual(counters["levels"], 1)
        self.assertEqual(counters["movesets"], 1)

    def test_all_disabled_does_not_require_or_touch_project_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertEqual(
                apply_trainer_difficulty(seed=1, root=root),
                {},
            )
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

