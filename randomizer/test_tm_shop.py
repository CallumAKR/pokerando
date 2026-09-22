#!/usr/bin/env python3

import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import configure_tm_shop


class TMShopTests(unittest.TestCase):
    def test_discovery_uses_only_the_compiled_tm_table(self):
        item_blocks = configure_tm_shop._read_item_blocks()
        tm_items = configure_tm_shop._discover_all_tms(
            item_blocks
        )

        self.assertEqual(len(tm_items), 50)
        self.assertEqual(len(tm_items), len(set(tm_items)))
        self.assertNotIn("ITEM_TM_CASE", tm_items)
        self.assertNotIn("ITEM_TM66", tm_items)
        self.assertEqual(tm_items[0], "ITEM_TM_FOCUS_PUNCH")
        self.assertEqual(tm_items[-1], "ITEM_TM_OVERHEAT")

    def test_prefix_lookalikes_are_not_discovered(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            constants = Path(temp_dir) / "tms_hms.h"
            constants.write_text(
                """
#define FOREACH_TM(F) \\
    F(VALID_ONE) \\
    F(VALID_TWO)

#define FOREACH_HM(F) \\
    F(CUT)
""".lstrip(),
                encoding="utf-8",
            )

            valid_block = """
    {
        .description = COMPOUND_STRING("Valid"),
        .pocket = POCKET_TM_HM,
    },
"""
            item_blocks = {
                "ITEM_TM_VALID_ONE": valid_block,
                "ITEM_TM_VALID_TWO": valid_block,
                "ITEM_TM_NOT_COMPILED": valid_block,
                "ITEM_TM_CASE": "{ .pocket = POCKET_KEY_ITEMS },",
                "ITEM_TM66": (
                    "{ .description = sQuestionMarksDesc, "
                    ".pocket = POCKET_TM_HM },"
                ),
            }

            with mock.patch.object(
                configure_tm_shop,
                "TMHM_CONSTANTS_FILE",
                constants,
            ):
                result = configure_tm_shop._discover_all_tms(
                    item_blocks
                )

        self.assertEqual(
            result,
            ["ITEM_TM_VALID_ONE", "ITEM_TM_VALID_TWO"],
        )

    def test_compiled_tm_with_placeholder_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            constants = Path(temp_dir) / "tms_hms.h"
            constants.write_text(
                """
#define FOREACH_TM(F) \\
    F(BLANK)

#define FOREACH_HM(F) \\
    F(CUT)
""".lstrip(),
                encoding="utf-8",
            )

            with mock.patch.object(
                configure_tm_shop,
                "TMHM_CONSTANTS_FILE",
                constants,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "placeholder item data",
                ):
                    configure_tm_shop._discover_all_tms(
                        {
                            "ITEM_TM_BLANK": (
                                "{ .description = sQuestionMarksDesc, "
                                ".pocket = POCKET_TM_HM },"
                            )
                        }
                    )

    def test_lilycove_receives_exactly_the_fifty_real_tms(self):
        source_shop = configure_tm_shop.TM_SHOP_FILE

        with tempfile.TemporaryDirectory() as temp_dir:
            test_shop = Path(temp_dir) / "scripts.inc"
            shutil.copyfile(source_shop, test_shop)

            with mock.patch.object(
                configure_tm_shop,
                "TM_SHOP_FILE",
                test_shop,
            ):
                count = configure_tm_shop.add_all_tms_to_lilycove_shop()

            shop_text = test_shop.read_text(encoding="utf-8")

        self.assertEqual(count, 50)
        self.assertNotIn("ITEM_TM_CASE", shop_text)
        self.assertNotIn("ITEM_TM66", shop_text)
        for item in configure_tm_shop._discover_all_tms(
            configure_tm_shop._read_item_blocks()
        ):
            self.assertEqual(
                len(
                    re.findall(
                        rf"\b{re.escape(item)}\b",
                        shop_text,
                    )
                ),
                1,
            )


if __name__ == "__main__":
    unittest.main()
