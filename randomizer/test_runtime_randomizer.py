#!/usr/bin/env python3

import tempfile
import unittest
from pathlib import Path
from unittest import mock
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "randomizer"))

import runtime_randomizer_config


class RuntimeRandomizerTests(unittest.TestCase):
    def test_generated_header_records_rom_rules(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            header = Path(temp_dir) / "randomizer_runtime_config.h"

            with mock.patch.object(
                runtime_randomizer_config,
                "HEADER_PATH",
                header,
            ):
                runtime_randomizer_config.configure_runtime_randomizer(
                    seed=0x12345678,
                    selected_components={
                        "starters",
                        "wild",
                        "abilities",
                        "trainers",
                    },
                    starter_three_stage_base=True,
                    wild_allow_special=True,
                    wild_similar_bst=True,
                    wild_mode="runtime",
                    enable_all_fossils=True,
                    fossil_only_replacements=True,
                    trainer_allow_special=False,
                    trainer_similar_bst=True,
                    trainer_mode="full",
                    trainer_type_themes=True,
                    rival_starter_continuity=True,
                )

            text = header.read_text(encoding="utf-8")

        self.assertIn(
            "#define RANDOMIZER_RUNTIME_ROM_SALT 305419896u",
            text,
        )
        self.assertIn("#define RANDOMIZER_RUNTIME_STARTERS 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_WILD 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_ABILITIES 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_TRAINERS 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_WILD_MODE 2", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_TRAINER_MODE 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_ALL_FOSSILS 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_FOSSIL_ONLY 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_RIVAL_CONTINUITY 1", text)
        self.assertIn("#define RANDOMIZER_RUNTIME_ITEMS 0", text)
        self.assertIn("RANDOMIZER_RUNTIME_STATIC_SOURCES(F)", text)
        self.assertRegex(text, r"F\(0x[0-9A-F]{4}, SPECIES_[A-Z0-9_]+\)")
        self.assertIn("RANDOMIZER_RUNTIME_TRAINER_THEME_GROUPS(F)", text)
        self.assertRegex(text, r"F\(TRAINER_[A-Z0-9_]+, [0-9]+\)")

    def test_manual_species_fields_are_protected_at_runtime(self):
        customizations = {
            "SPECIES_PIKACHU": {
                "manual": {
                    "types": ["TYPE_ELECTRIC"],
                    "stats": None,
                    "abilities": ["ABILITY_STATIC"],
                }
            },
            "SPECIES_EEVEE": {
                "manual": {
                    "types": None,
                    "stats": [55, 55, 50, 55, 45, 65],
                    "abilities": None,
                }
            },
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            header = Path(temp_dir) / "randomizer_runtime_config.h"

            with mock.patch.object(
                runtime_randomizer_config,
                "HEADER_PATH",
                header,
            ):
                runtime_randomizer_config.configure_runtime_randomizer(
                    seed=1,
                    selected_components={
                        "pokemon_types",
                        "pokemon_bst",
                        "abilities",
                    },
                    pokemon_bst_mode="same",
                    manual_customizations=customizations,
                )

            text = header.read_text(encoding="utf-8")

        self.assertIn("((species) == SPECIES_PIKACHU)", text)
        self.assertIn("((species) == SPECIES_EEVEE)", text)
        self.assertIn("RANDOMIZER_RUNTIME_PROTECT_EVOLUTIONS", text)
        self.assertIn("RANDOMIZER_RUNTIME_PROTECT_MOVES", text)
        self.assertIn("RANDOMIZER_RUNTIME_PROTECT_EVOLUTION_MOVES", text)
        self.assertIn("RANDOMIZER_RUNTIME_PROTECT_TMS", text)

    def test_unsupported_ability_mechanics_are_not_in_the_pool(self):
        source = (ROOT / "src/runtime_randomizer.c").read_text(
            encoding="utf-8"
        )

        for ability in (
            "ABILITY_SCHOOLING",
            "ABILITY_FORECAST",
            "ABILITY_STANCE_CHANGE",
            "ABILITY_SHIELDS_DOWN",
            "ABILITY_ZEN_MODE",
            "ABILITY_BATTLE_BOND",
            "ABILITY_POWER_CONSTRUCT",
            "ABILITY_HUNGER_SWITCH",
            "ABILITY_ZERO_TO_HERO",
            "ABILITY_MULTITYPE",
            "ABILITY_RKS_SYSTEM",
            "ABILITY_DISGUISE",
            "ABILITY_ICE_FACE",
            "ABILITY_GULP_MISSILE",
            "ABILITY_COMMANDER",
            "ABILITY_TERA_SHIFT",
            "ABILITY_TERA_SHELL",
            "ABILITY_TERAFORM_ZERO",
        ):
            self.assertIn(f"case {ability}:", source)

    def test_signature_moves_have_no_species_lock(self):
        resolution = (ROOT / "src/battle_move_resolution.c").read_text(
            encoding="utf-8"
        )
        ai = (ROOT / "src/battle_ai_main.c").read_text(encoding="utf-8")

        for effect in (
            "EFFECT_DARK_VOID",
            "EFFECT_AURA_WHEEL",
            "EFFECT_HYPERSPACE_FURY",
        ):
            self.assertNotIn(f"case {effect}:", resolution)
            self.assertNotIn(f"case {effect}:", ai)

    def test_new_game_seed_is_save_specific_and_deterministic(self):
        source = (ROOT / "src/runtime_randomizer.c").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "GetTrainerId(gSaveBlock2Ptr->playerTrainerId)",
            source,
        )
        self.assertIn("RANDOMIZER_RUNTIME_ROM_SALT", source)
        self.assertNotIn("Random() % (NUM_SPECIES", source)

    def test_permanent_trainer_megas_reroll_only_to_valid_megas(self):
        source = (ROOT / "src/runtime_randomizer.c").read_text(
            encoding="utf-8"
        )

        self.assertIn("GetRuntimeTrainerMegaSpecies", source)
        self.assertIn("gSpeciesInfo[candidate].isMegaEvolution", source)
        self.assertIn("candidate != originalSpecies", source)
        self.assertIn("RANDOMIZER_RUNTIME_TRAINER_ALLOW_SPECIAL", source)
        self.assertIn("RANDOMIZER_RUNTIME_TRAINER_SIMILAR_BST", source)
        self.assertIn("GetSpeciesType(candidate, 0) != theme", source)
        self.assertNotIn(
            "if (gSpeciesInfo[originalSpecies].isMegaEvolution)\n"
            "            return originalSpecies;",
            source,
        )

    def test_runtime_trainer_id_does_not_require_linker_data(self):
        source = (ROOT / "src/battle_main.c").read_text(
            encoding="utf-8"
        )

        self.assertNotIn("sRuntimeTrainerId", source)
        self.assertIn("CreateNPCTrainerPartyFromTrainerId", source)
        self.assertIn(
            "trainerId, monIndex, trainer->partySize",
            source,
        )

    def test_z_max_moves_and_z_crystals_are_not_runtime_candidates(self):
        source = (ROOT / "src/runtime_randomizer.c").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "move >= FIRST_Z_MOVE && move <= LAST_MAX_MOVE",
            source,
        )
        self.assertIn(
            "gItemsInfo[item].sortType == ITEM_TYPE_Z_CRYSTAL",
            source,
        )

    def test_build_time_pools_exclude_special_battle_moves_and_z_items(self):
        moves = (ROOT / "randomizer/randomize_moves.py").read_text(
            encoding="utf-8"
        )
        items = (ROOT / "randomizer/randomize_items.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("// Z Moves(?P<body>.*?)MOVES_COUNT_DYNAMAX", moves)
        self.assertIn('"ITEM_TYPE_Z_CRYSTAL" in info["block"]', items)
        self.assertIn("resolve_item_alias(item)", items)
        self.assertIn("ITEM_CONSTANTS_FILE", items)

    def test_wild_levels_are_clamped_to_the_active_level_cap(self):
        source = (ROOT / "src/wild_encounter.c").read_text(
            encoding="utf-8"
        )

        self.assertIn("ClampWildLevelToCurrentCap", source)
        self.assertIn("GetCurrentLevelCap()", source)
        self.assertIn(
            "ClampWildLevelToCurrentCap(gSaveBlock1Ptr->outbreakPokemonLevel)",
            source,
        )
        self.assertRegex(
            source,
            r"void CreateWildMon\(enum Species species, u8 level\)\n"
            r"\{\n\s*level = ClampWildLevelToCurrentCap\(level\);",
        )


if __name__ == "__main__":
    unittest.main()
