"""Allow randomized species to use otherwise species-locked signature moves.

Run by the master randomizer before compiling the ROM. Only known battle
guards are changed; every other source edit in the project is preserved.
"""

import os
import tempfile

from runtime_paths import ROOT


BATTLE_SOURCE = ROOT / "src/battle_move_resolution.c"
AI_SOURCE = ROOT / "src/battle_ai_main.c"

BATTLE_LOCKS = (
    "    case EFFECT_DARK_VOID:\n"
    "        if (gBattleStruct->bouncedMoveIsUsed)\n"
    "            break;\n"
    "        if (B_DARK_VOID_FAIL >= GEN_7 && gBattleMons[cv->battlerAtk].species != SPECIES_DARKRAI)\n"
    "            battleScript = BattleScript_PokemonCantUseTheMove;\n"
    "        break;\n"
    "    case EFFECT_AURA_WHEEL:\n"
    "        if (gBattleMons[cv->battlerAtk].species != SPECIES_MORPEKO_FULL_BELLY\n"
    "         && gBattleMons[cv->battlerAtk].species != SPECIES_MORPEKO_HANGRY)\n"
    "            battleScript = BattleScript_PokemonCantUseTheMove;\n"
    "        break;\n"
    "    case EFFECT_HYPERSPACE_FURY:\n"
    "        if (gBattleMons[cv->battlerAtk].species == SPECIES_HOOPA_CONFINED)\n"
    "            battleScript = BattleScript_ButHoopaCantUseIt;\n"
    "        else if (gBattleMons[cv->battlerAtk].species != SPECIES_HOOPA_UNBOUND)\n"
    "            battleScript = BattleScript_PokemonCantUseTheMove;\n"
    "        break;\n"
)

AI_LOCKS = (
    "    case EFFECT_DARK_VOID:\n"
    "        if (B_DARK_VOID_FAIL >= GEN_7 && gBattleMons[battlerAtk].species != SPECIES_DARKRAI)\n"
    "            ADJUST_SCORE(-10);\n"
    "        break;\n"
    "    case EFFECT_HYPERSPACE_FURY:\n"
    "        if (gBattleMons[battlerAtk].species != SPECIES_HOOPA_UNBOUND)\n"
    "            ADJUST_SCORE(-10);\n"
    "        break;\n"
)

BATTLE_MARKER = "    // RANDOMIZER: signature moves can be used by any species.\n"
AI_MARKER = "    // RANDOMIZER: signature moves are viable for any species.\n"


def _planned_update(path, original_block, marker):
    if not path.is_file():
        raise RuntimeError(f"Missing battle source: {path}")

    source = path.read_text(encoding="utf-8")
    if marker in source:
        if original_block in source:
            raise RuntimeError(f"Species restrictions remain after patch: {path}")
        return None

    if source.count(original_block) != 1:
        raise RuntimeError(
            f"Cannot safely find the original signature-move guards in {path}. "
            "Keep your current source and provide the file for a tailored patch."
        )

    return source.replace(original_block, marker, 1)


def _write_atomically(path, contents):
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".signature-moves-", suffix=".c", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(contents)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def ensure_signature_moves_usable():
    """Remove only the Dark Void, Aura Wheel, and Hyperspace Fury species locks."""
    plans = (
        (BATTLE_SOURCE, BATTLE_LOCKS, BATTLE_MARKER),
        (AI_SOURCE, AI_LOCKS, AI_MARKER),
    )
    # Check both source versions before writing either file.
    updates = [
        (path, _planned_update(path, original, marker))
        for path, original, marker in plans
    ]
    count = 0
    for path, contents in updates:
        if contents is not None:
            _write_atomically(path, contents)
            count += 1
    if count:
        print("Made Dark Void, Aura Wheel, and Hyperspace Fury usable by all Pokémon.")
    return count


if __name__ == "__main__":
    ensure_signature_moves_usable()
