import re
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import configure_tm_shop

if "manual_customization_runtime" not in sys.modules:
    try:
        __import__("manual_customization_runtime")
    except ModuleNotFoundError:
        runtime_stub = types.ModuleType("manual_customization_runtime")
        runtime_stub.species_is_enabled = lambda _species: True
        sys.modules["manual_customization_runtime"] = runtime_stub

import ensure_evolution_moves
import game_options


ROOT = Path(__file__).resolve().parent.parent


class RegionalEvolutionTests(unittest.TestCase):
    def test_clean_baseline_has_thirteen_regional_evolution_branches(self):
        species_dir = ROOT / "randomizer/baseline/src/data/pokemon/species_info"
        regional_entries = []

        for filepath in species_dir.glob("*.h"):
            regional_entries.extend(
                re.findall(
                    r"\{IF_REGION\s*,\s*(REGION_[A-Z]+)\s*\}",
                    filepath.read_text(encoding="utf-8"),
                )
            )

        self.assertEqual(len(regional_entries), 13)
        self.assertEqual(
            set(regional_entries),
            {"REGION_ALOLA", "REGION_GALAR", "REGION_HISUI"},
        )

    def test_postcards_and_peat_block_are_discoverable(self):
        item_blocks = configure_tm_shop._read_item_blocks()
        evolution_items = configure_tm_shop._discover_evolution_items(
            item_blocks
        )

        self.assertIn("ITEM_PEAT_BLOCK", evolution_items)
        self.assertLessEqual(
            set(configure_tm_shop.REGIONAL_POSTCARDS),
            set(item_blocks),
        )
        self.assertFalse(
            set(configure_tm_shop.REGIONAL_POSTCARDS)
            & set(evolution_items)
        )

    def test_lilycove_shop_receives_peat_block_and_all_postcards(self):
        source_shop = configure_tm_shop.EVOLUTION_SHOP_FILE

        with tempfile.TemporaryDirectory() as temp_dir:
            test_shop = Path(temp_dir) / "scripts.inc"
            shutil.copyfile(source_shop, test_shop)

            with mock.patch.object(
                configure_tm_shop,
                "EVOLUTION_SHOP_FILE",
                test_shop,
            ):
                result = configure_tm_shop.configure_lilycove_evolution_shop(
                    add_evolution_items=True,
                    add_mega_stones=False,
                    add_regional_postcards=True,
                )

            shop_text = test_shop.read_text(encoding="utf-8")

        self.assertGreater(result["evolution_items"], 10)
        self.assertEqual(result["regional_postcards"], 3)
        self.assertIn("ITEM_PEAT_BLOCK", shop_text)
        for postcard in configure_tm_shop.REGIONAL_POSTCARDS:
            self.assertEqual(shop_text.count(postcard), 1)

    def test_mime_jr_mimic_is_discovered_as_an_evolution_move(self):
        learnset_text = ensure_evolution_moves.LEARNSET_FILE.read_text(
            encoding="utf-8"
        )
        _requirements, audit_rows = (
            ensure_evolution_moves._discover_requirements(
                ensure_evolution_moves.SPECIES_DIR,
                ensure_evolution_moves.MOVES_FILE,
                ensure_evolution_moves.LEARNABLES_FILE,
                learnset_text,
            )
        )

        self.assertTrue(
            any(
                species == "SPECIES_MIME_JR"
                and move == "MOVE_MIMIC"
                and reason == "knows move"
                for species, _learnset, move, reason in audit_rows
            )
        )

    def test_ursaring_bloodmoon_toggle_is_reversible(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            species_file = Path(temp_dir) / "gen_2_families.h"
            species_file.write_text(
                """
    [SPECIES_URSARING] =
    {
        .evolutions = EVOLUTION({EVO_ITEM, ITEM_PEAT_BLOCK, SPECIES_URSALUNA, CONDITIONS({IF_REGION, REGION_HISUI}, {IF_TIME, TIME_NIGHT})},
                                {EVO_NONE, 0, SPECIES_URSALUNA_BLOODMOON}),
    },
""".lstrip(),
                encoding="utf-8",
            )

            with mock.patch.object(
                game_options,
                "URSARING_SPECIES_H",
                species_file,
            ):
                self.assertTrue(
                    game_options._configure_ursaring_regional_evolutions(
                        True
                    )
                )
                enabled = species_file.read_text(encoding="utf-8")

                self.assertIn(
                    game_options.URSARING_REGIONAL_START,
                    enabled,
                )
                self.assertIn(
                    "EVO_ITEM, ITEM_PEAT_BLOCK, "
                    "SPECIES_URSALUNA_BLOODMOON",
                    enabled,
                )
                self.assertRegex(
                    enabled,
                    re.compile(
                        r"SPECIES_URSALUNA_BLOODMOON.*?"
                        r"IF_TIME, TIME_NIGHT.*?SPECIES_URSALUNA, "
                        r"CONDITIONS\(\{IF_REGION, REGION_HISUI\}\)",
                        re.DOTALL,
                    ),
                )

                self.assertTrue(
                    game_options._configure_ursaring_regional_evolutions(
                        False
                    )
                )
                disabled = species_file.read_text(encoding="utf-8")

            self.assertNotIn(
                game_options.URSARING_REGIONAL_START,
                disabled,
            )
            self.assertIn(
                "{EVO_NONE, 0, SPECIES_URSALUNA_BLOODMOON}",
                disabled,
            )
            self.assertIn(
                "SPECIES_URSALUNA, CONDITIONS("
                "{IF_REGION, REGION_HISUI}, ",
                disabled,
            )

    def test_pokemon_source_uses_held_postcard_as_virtual_region(self):
        pokemon_source = (ROOT / "src/pokemon.c").read_text(
            encoding="utf-8"
        )

        for item, region in (
            ("ITEM_ALOLA_POSTCARD", "REGION_ALOLA"),
            ("ITEM_GALAR_POSTCARD", "REGION_GALAR"),
            ("ITEM_HISUI_POSTCARD", "REGION_HISUI"),
        ):
            self.assertRegex(
                pokemon_source,
                re.compile(
                    rf"case {item}:\s+evolutionRegion = {region};"
                ),
            )

        self.assertIn(
            "if (evolutionRegion == params[i].arg1)",
            pokemon_source,
        )
        self.assertIn(
            "if (evolutionRegion != params[i].arg1)",
            pokemon_source,
        )

    def test_generated_header_includes_disabled_postcard_option(self):
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
                )

            self.assertIn(
                "#define RANDOMIZER_REGIONAL_EVOLUTION_POSTCARDS 0",
                header.read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
