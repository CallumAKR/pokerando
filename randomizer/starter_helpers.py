#!/usr/bin/env python3
"""Shared starter discovery, manual selection, and sprite helpers."""

import re
from pathlib import Path

from runtime_paths import ROOT, BASELINE_ROOT


SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
STARTER_FILE = ROOT / "src/starter_choose.c"
BASELINE_STARTER_FILE = BASELINE_ROOT / "src/starter_choose.c"
POKEMON_GRAPHICS_DIR = ROOT / "graphics/pokemon"
POKEDEX_CONSTANTS_FILE = ROOT / "include/constants/pokedex.h"

SPECIES_HEADER_PATTERN = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$"
)

INVALID_FORM_FLAGS = {
    "isMegaEvolution",
    "isPrimalReversion",
    "isUltraBurst",
    "isGigantamax",
    "isTeraForm",
    "isTotem",
}

STARTER_PATTERNS = (
    re.compile(
        r"(#define\s+GRASS_STARTER\s+"
        r"\(IS_FRLG\s*\?\s*"
        r"SPECIES_[A-Z0-9_]+\s*:\s*)"
        r"(SPECIES_[A-Z0-9_]+)"
        r"(\s*\))"
    ),
    re.compile(
        r"(#define\s+FIRE_STARTER\s+"
        r"\(IS_FRLG\s*\?\s*"
        r"SPECIES_[A-Z0-9_]+\s*:\s*)"
        r"(SPECIES_[A-Z0-9_]+)"
        r"(\s*\))"
    ),
    re.compile(
        r"(#define\s+WATER_STARTER\s+"
        r"\(IS_FRLG\s*\?\s*"
        r"SPECIES_[A-Z0-9_]+\s*:\s*)"
        r"(SPECIES_[A-Z0-9_]+)"
        r"(\s*\))"
    ),
)


def _read_species_blocks():
    blocks = {}

    for filepath in sorted(SPECIES_DIR.rglob("*.h")):
        lines = filepath.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines(keepends=True)

        i = 0

        while i < len(lines):
            match = SPECIES_HEADER_PATTERN.match(
                lines[i].rstrip("\r\n")
            )

            if not match:
                i += 1
                continue

            species = match.group(1)
            start = i
            i += 1

            while i < len(lines) and "{" not in lines[i]:
                i += 1

            if i >= len(lines):
                break

            depth = 0
            opened = False

            while i < len(lines):
                for char in lines[i]:
                    if char == "{":
                        depth += 1
                        opened = True
                    elif char == "}":
                        depth -= 1

                if opened and depth == 0:
                    end = i
                    break

                i += 1
            else:
                break

            blocks[species] = "".join(lines[start:end + 1])
            i = end + 1

    return blocks


def _has_flag(block, flag):
    return re.search(
        rf"\.{re.escape(flag)}\s*=\s*TRUE",
        block,
    ) is not None


def is_selectable_species(species, block):
    if species in {"SPECIES_NONE", "SPECIES_EGG"}:
        return False

    if any(_has_flag(block, flag) for flag in INVALID_FORM_FLAGS):
        return False

    return True


def species_display_name(species):
    """Create a readable, deterministic label from a SPECIES_* constant."""
    raw = species.removeprefix("SPECIES_")
    words = raw.split("_")

    special_words = {
        "MR": "Mr.",
        "MRS": "Mrs.",
        "JR": "Jr.",
        "F": "♀",
        "M": "♂",
        "GMAX": "G-Max",
        "ALOLA": "Alola",
        "GALAR": "Galar",
        "HISUI": "Hisui",
        "PALDEA": "Paldea",
    }

    rendered = []

    for word in words:
        if word in special_words:
            rendered.append(special_words[word])
        elif word.isdigit():
            rendered.append(word)
        elif len(word) == 1:
            rendered.append(word)
        else:
            rendered.append(word.title())

    name = " ".join(rendered)

    replacements = {
        "Ho Oh": "Ho-Oh",
        "Porygon Z": "Porygon-Z",
        "Type Null": "Type: Null",
        "Farfetchd": "Farfetch'd",
        "Sirfetchd": "Sirfetch'd",
        "Flabebe": "Flabébé",
    }

    return replacements.get(name, name)


def _read_national_dex_numbers():
    """
    Return {NATIONAL_DEX_*: number} from the project's Pokedex constants.

    pokeemerald-expansion keeps National Dex numbering in
    include/constants/pokedex.h. Parsing it at runtime means the dropdown
    follows the exact Expansion checkout being randomized.
    """
    if not POKEDEX_CONSTANTS_FILE.exists():
        return {}

    text = POKEDEX_CONSTANTS_FILE.read_text(
        encoding="utf-8",
        errors="replace",
    )

    numbers = {}

    for match in re.finditer(
        r"^\s*#define\s+"
        r"(NATIONAL_DEX_[A-Z0-9_]+)"
        r"\s+([0-9]+)\b",
        text,
        re.MULTILINE,
    ):
        numbers[match.group(1)] = int(
            match.group(2)
        )

    return numbers


def _species_national_dex_constant(
    species,
    block,
    blocks,
):
    """
    Find the National Dex constant for a species/form.

    Most species blocks provide `.natDexNum`. If a form omits it, follow its
    `.baseSpecies` link so regional and alternate forms still sort beside
    their base Pokemon.
    """
    dex_match = re.search(
        r"\.natDexNum\s*=\s*"
        r"(NATIONAL_DEX_[A-Z0-9_]+)",
        block,
    )

    if dex_match:
        return dex_match.group(1)

    visited = {
        species
    }
    current_block = block

    while True:
        base_match = re.search(
            r"\.baseSpecies\s*=\s*"
            r"(SPECIES_[A-Z0-9_]+)",
            current_block,
        )

        if not base_match:
            return None

        base_species = base_match.group(1)

        if base_species in visited:
            return None

        visited.add(
            base_species
        )

        base_block = blocks.get(
            base_species
        )

        if base_block is None:
            return None

        dex_match = re.search(
            r"\.natDexNum\s*=\s*"
            r"(NATIONAL_DEX_[A-Z0-9_]+)",
            base_block,
        )

        if dex_match:
            return dex_match.group(1)

        current_block = base_block


def _starter_pokedex_sort_key(
    species,
    block,
    blocks,
    dex_numbers,
):
    dex_constant = _species_national_dex_constant(
        species,
        block,
        blocks,
    )

    dex_number = dex_numbers.get(
        dex_constant,
    )

    if dex_number is None:
        # Unknown/internal species go after normal National Dex entries while
        # remaining deterministic.
        return (
            10**9,
            1,
            species,
        )

    expected_base_species = (
        dex_constant.replace(
            "NATIONAL_DEX_",
            "SPECIES_",
            1,
        )
        if dex_constant
        else None
    )

    # Put the ordinary/base form first, then its regional/alternate forms.
    form_rank = (
        0
        if species == expected_base_species
        else 1
    )

    return (
        dex_number,
        form_rank,
        species,
    )


def discover_selectable_starters():
    """
    Return sorted (display_label, species_constant) pairs for manual selection.

    Manual selection intentionally allows legendary/mythical species and
    evolved Pokémon. Only invalid/internal and temporary battle-only forms are
    filtered out.
    """
    blocks = _read_species_blocks()

    if len(blocks) < 500:
        raise RuntimeError(
            "Starter selector found suspiciously few species definitions."
        )

    dex_numbers = _read_national_dex_numbers()

    entries = []

    for species, block in blocks.items():
        if not is_selectable_species(species, block):
            continue

        entries.append(
            (
                species_display_name(species),
                species,
                _starter_pokedex_sort_key(
                    species,
                    block,
                    blocks,
                    dex_numbers,
                ),
            )
        )

    entries.sort(
        key=lambda item: item[2]
    )

    return [
        (label, species)
        for label, species, _ in entries
    ]


def discover_customizable_species():
    """Return the species entries used by Manual Customisation.

    Manual Customisation and manual starter selection share the same safe,
    National-Dex-ordered species catalogue: ordinary species and persistent
    regional/alternate forms are included, while invalid/internal entries and
    temporary battle-only forms are excluded.

    Keep this named entry point for compatibility with
    manual_customization_ui.py.
    """

    return discover_selectable_starters()


def read_starters_from_file(filepath):
    if not Path(filepath).exists():
        return None

    text = Path(filepath).read_text(
        encoding="utf-8",
        errors="replace",
    )

    starters = []

    for pattern in STARTER_PATTERNS:
        match = pattern.search(text)
        if not match:
            return None
        starters.append(match.group(2))

    return tuple(starters)


def read_default_starters():
    """Prefer packaged baseline starters for GUI defaults."""
    starters = read_starters_from_file(BASELINE_STARTER_FILE)

    if starters:
        return starters

    starters = read_starters_from_file(STARTER_FILE)

    if starters:
        return starters

    return (
        "SPECIES_TREECKO",
        "SPECIES_TORCHIC",
        "SPECIES_MUDKIP",
    )


def validate_manual_starters(starters):
    if starters is None:
        return None

    starters = tuple(starters)

    if len(starters) != 3:
        raise RuntimeError(
            "Manual starter selection requires exactly three Pokémon."
        )

    blocks = _read_species_blocks()

    for species in starters:
        block = blocks.get(species)

        if block is None:
            raise RuntimeError(
                f"Manual starter species does not exist: {species}"
            )

        if not is_selectable_species(species, block):
            raise RuntimeError(
                f"Manual starter species is not selectable: {species}"
            )

    if len(set(starters)) != 3:
        raise RuntimeError(
            "Choose three different manual starter Pokémon."
        )

    return starters


def apply_manual_starters(starters):
    starters = validate_manual_starters(starters)

    text = STARTER_FILE.read_text(
        encoding="utf-8"
    )

    new_text = text

    for pattern, species in zip(STARTER_PATTERNS, starters):
        new_text, count = pattern.subn(
            lambda match, chosen=species: (
                match.group(1)
                + chosen
                + match.group(3)
            ),
            new_text,
            count=1,
        )

        if count != 1:
            raise RuntimeError(
                "Could not locate all three starter slots in starter_choose.c."
            )

    STARTER_FILE.write_text(
        new_text,
        encoding="utf-8",
    )

    print()
    print("Manual starters:")

    for slot, species in enumerate(starters, start=1):
        print(
            f"  Starter {slot}: {species_display_name(species)} "
            f"({species})"
        )

    return starters


def find_front_sprite(species):
    """Return the best available PNG preview path for a species."""
    if not POKEMON_GRAPHICS_DIR.exists():
        return None

    slug = species.removeprefix("SPECIES_").lower()

    candidate_dirs = [
        POKEMON_GRAPHICS_DIR / slug,
    ]

    # Expansion form graphics are commonly nested, for example
    # graphics/pokemon/rotom/heat/front.png rather than rotom_heat/front.png.
    parts = slug.split("_")

    for split_at in range(1, len(parts)):
        candidate_dirs.append(
            POKEMON_GRAPHICS_DIR
            / "_".join(parts[:split_at])
            / "_".join(parts[split_at:])
        )

    for directory in candidate_dirs:
        for filename in ("front.png", "icon.png"):
            path = directory / filename
            if path.exists():
                return path

    return None
