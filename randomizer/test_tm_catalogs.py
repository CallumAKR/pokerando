#!/usr/bin/env python3

import json
import hashlib
import re
import sys
import tempfile
import unittest

from pathlib import Path
from unittest import mock


RANDOMIZER_DIR = Path(__file__).resolve().parent
ROOT = RANDOMIZER_DIR.parent

if str(RANDOMIZER_DIR) not in sys.path:
    sys.path.insert(0, str(RANDOMIZER_DIR))

import configure_tm_shop
from configure_tm_catalog import TM_SECTION_MARKER, configure_tm_catalog
from tm_catalog_data import (
    DEFAULT_TM_CATALOG,
    ORIGINAL_GEN3_TM_ITEMS_SHA256,
    TM_CATALOGS,
)


EXPECTED_COUNTS = {
    "gen1": 50,
    "gen2": 50,
    "gen3": 50,
    "gen4": 92,
    "gen5": 95,
    "gen6": 100,
    "gen7": 100,
    "gen8": 100,
}

SOURCE_FILES = {
    "gen1": ("y.json", 50),
    "gen2": ("c.json", 50),
    "gen3": ("rse.json", 50),
    "gen4": ("pt.json", 92),
    "gen5": ("b2w2.json", 95),
    "gen6": ("oras.json", 100),
    "gen7": ("usum.json", 100),
    "gen8": ("bdsp.json", 100),
}


class TMCatalogTests(unittest.TestCase):
    def test_profile_counts_and_unique_moves(self):
        self.assertEqual(DEFAULT_TM_CATALOG, "gen3")
        self.assertEqual(set(TM_CATALOGS), set(EXPECTED_COUNTS))

        for key, count in EXPECTED_COUNTS.items():
            moves = TM_CATALOGS[key]["moves"]
            self.assertEqual(len(moves), count, key)
            self.assertEqual(len(set(moves)), count, key)

    def test_embedded_profiles_match_project_source_data(self):
        source_dir = ROOT / "tools/learnset_helpers/porymoves_files"

        for key, (filename, count) in SOURCE_FILES.items():
            data = json.loads((source_dir / filename).read_text(encoding="utf-8"))
            expected = tuple(
                move.removeprefix("MOVE_")
                for move in data["MEW"]["TMMoves"][:count]
            )
            self.assertEqual(TM_CATALOGS[key]["moves"], expected, key)

    def test_profiles_are_reversible_and_shop_uses_only_active_tms(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            constants = temp / "tms_hms.h"
            items = temp / "items.h"
            moves_info = temp / "moves_info.h"
            constants.write_text(
                (ROOT / "include/constants/tms_hms.h").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            items.write_text(
                (ROOT / "src/data/items.h").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            moves_info.write_text(
                (ROOT / "src/data/moves_info.h").read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            for key, count in EXPECTED_COUNTS.items():
                result = configure_tm_catalog(key, constants, items, moves_info)
                self.assertEqual(result["count"], count)

                with mock.patch.object(configure_tm_shop, "ITEMS_FILE", items), mock.patch.object(
                    configure_tm_shop, "TMHM_CONSTANTS_FILE", constants
                ):
                    blocks = configure_tm_shop._read_item_blocks()
                    active_items = configure_tm_shop._discover_all_tms(blocks)

                self.assertEqual(
                    active_items,
                    [f"ITEM_TM_{move}" for move in TM_CATALOGS[key]["moves"]],
                )

                item_source = items.read_text(encoding="utf-8")
                for slot in range(count + 1, 101):
                    self.assertRegex(item_source, rf"\[ITEM_TM{slot:02d}\]\s*=")

            configure_tm_catalog("gen8", constants, items, moves_info)
            configure_tm_catalog("gen3", constants, items, moves_info)
            final_constants = constants.read_text(encoding="utf-8")
            macro = final_constants.split("#define FOREACH_HM(F)", 1)[0]
            final_moves = re.findall(r"F\(([A-Z0-9_]+)\)", macro)
            self.assertEqual(final_moves, list(TM_CATALOGS["gen3"]["moves"]))
            self.assertIn("[ITEM_TM51] =", items.read_text(encoding="utf-8"))

            item_source = items.read_text(encoding="utf-8")
            marker = item_source.index(TM_SECTION_MARKER)
            section_start = marker + len(TM_SECTION_MARKER)
            hm_match = re.search(
                r"(?m)^\s*\[ITEM_HM_CUT\]\s*=\s*$",
                item_source[section_start:],
            )
            section = item_source[
                section_start:section_start + hm_match.start()
            ]
            self.assertEqual(
                hashlib.sha256(section.encode("utf-8")).hexdigest(),
                ORIGINAL_GEN3_TM_ITEMS_SHA256,
            )

    def test_tm_and_hm_overlap_is_supported_by_separate_indexes(self):
        hm_moves = {
            "CUT", "FLY", "SURF", "STRENGTH",
            "FLASH", "ROCK_SMASH", "WATERFALL", "DIVE",
        }
        self.assertTrue(hm_moves & set(TM_CATALOGS["gen7"]["moves"]))
        self.assertTrue(hm_moves & set(TM_CATALOGS["gen8"]["moves"]))

        item_header = (ROOT / "include/item.h").read_text(encoding="utf-8")
        item_source = (ROOT / "src/item.c").read_text(encoding="utf-8")
        self.assertIn("CAT(ENUM_TM_, _tm)", item_header)
        self.assertIn("CAT(ENUM_HM_, _hm)", item_header)
        self.assertNotIn("ENUM_TM_HM_", item_header + item_source)

    def test_gui_master_and_item_randomizer_are_wired(self):
        gui_source = (RANDOMIZER_DIR / "gui.py").read_text(encoding="utf-8")
        master_source = (RANDOMIZER_DIR / "master_randomizer.py").read_text(
            encoding="utf-8"
        )
        item_randomizer = (RANDOMIZER_DIR / "randomize_items.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("self.tm_catalog_generation_var", gui_source)
        self.assertIn("for key, profile in TM_CATALOGS.items()", gui_source)
        self.assertIn("shape=\"circle\"", gui_source)
        self.assertIn("tm_catalog_generation=tm_catalog_generation", gui_source)
        self.assertIn("configure_tm_catalog(effective_tm_catalog)", master_source)
        self.assertIn("else DEFAULT_TM_CATALOG", master_source)
        self.assertIn('info["is_placeholder"]', item_randomizer)


if __name__ == "__main__":
    unittest.main()
