#!/usr/bin/env python3

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
CURRENT_SPECIES_FILE = (
    ROOT
    / "src/data/pokemon/species_info/gen_7_families.h"
)
BASELINE_SPECIES_FILE = (
    ROOT
    / "randomizer/baseline/src/data/pokemon/species_info/gen_7_families.h"
)


def get_species_block(source, species):
    match = re.search(
        rf"(?ms)^\s*\[{re.escape(species)}\]\s*=\s*\{{.*?"
        rf"(?=^\s*\[SPECIES_|^#endif)",
        source,
    )
    if match is None:
        raise AssertionError(f"Could not find {species}")
    return match.group(0)


class TimeBranchEvolutionTests(unittest.TestCase):
    def species_sources(self):
        for path in (CURRENT_SPECIES_FILE, BASELINE_SPECIES_FILE):
            yield path, path.read_text(encoding="utf-8")

    def test_cosmoem_uses_day_side_for_solgaleo_and_night_for_lunala(self):
        solgaleo = (
            "{EVO_LEVEL, 53, SPECIES_SOLGALEO, "
            "CONDITIONS({IF_NOT_TIME, TIME_NIGHT})}"
        )
        lunala = (
            "{EVO_LEVEL, 53, SPECIES_LUNALA, "
            "CONDITIONS({IF_TIME, TIME_NIGHT})}"
        )

        for path, source in self.species_sources():
            with self.subTest(path=path):
                block = get_species_block(source, "SPECIES_COSMOEM")
                self.assertIn(solgaleo, block)
                self.assertIn(lunala, block)

    def test_normal_rockruff_can_reach_all_three_lycanroc_forms(self):
        dusk = (
            "{EVO_LEVEL, 25, SPECIES_LYCANROC_DUSK, "
            "CONDITIONS({IF_TIME, TIME_EVENING})}"
        )
        midday = (
            "{EVO_LEVEL, 25, SPECIES_LYCANROC_MIDDAY, "
            "CONDITIONS({IF_NOT_TIME, TIME_NIGHT})}"
        )
        midnight = (
            "{EVO_LEVEL, 25, SPECIES_LYCANROC_MIDNIGHT, "
            "CONDITIONS({IF_TIME, TIME_NIGHT})}"
        )

        for path, source in self.species_sources():
            with self.subTest(path=path):
                block = get_species_block(source, "SPECIES_ROCKRUFF")
                self.assertIn(dusk, block)
                self.assertIn(midday, block)
                self.assertIn(midnight, block)
                self.assertLess(block.index(dusk), block.index(midday))
                self.assertLess(block.index(midday), block.index(midnight))

    def test_own_tempo_rockruff_keeps_its_dusk_route(self):
        dusk = (
            "{EVO_LEVEL, 25, SPECIES_LYCANROC_DUSK, "
            "CONDITIONS({IF_TIME, TIME_EVENING})}"
        )

        for path, source in self.species_sources():
            with self.subTest(path=path):
                block = get_species_block(
                    source,
                    "SPECIES_ROCKRUFF_OWN_TEMPO",
                )
                self.assertIn(dusk, block)


if __name__ == "__main__":
    unittest.main()
