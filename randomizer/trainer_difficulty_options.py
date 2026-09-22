#!/usr/bin/env python3

"""Persist run-scoped trainer difficulty choices used by trainer randomisation."""

import json

from runtime_paths import RANDOMIZER_DIR


CONFIG_FILE = RANDOMIZER_DIR / "trainer_difficulty_options.json"


class TrainerDifficultyOptionError(RuntimeError):
    """Raised when incompatible trainer difficulty choices are requested."""


def configure_trainer_difficulty_options(
    evolution_stage_rules=False,
    boss_permanent_megas=False,
    trainer_randomisation=False,
    permanent_megas=False,
    level_boost=0,
    level_scope="all",
):
    """Write every option on every GUI run so settings cannot leak."""

    evolution_stage_rules = bool(evolution_stage_rules)
    boss_permanent_megas = bool(boss_permanent_megas)
    trainer_randomisation = bool(trainer_randomisation)
    permanent_megas = bool(permanent_megas)

    try:
        level_boost = int(level_boost)
    except (TypeError, ValueError) as exc:
        raise TrainerDifficultyOptionError(
            "Trainer level boost must be a whole number."
        ) from exc

    if not 0 <= level_boost <= 20:
        raise TrainerDifficultyOptionError(
            "Trainer level boost must be between 0 and 20."
        )

    if level_scope not in {"all", "major"}:
        raise TrainerDifficultyOptionError(
            "Trainer level scope must be 'all' or 'major'."
        )

    if evolution_stage_rules and not trainer_randomisation:
        raise TrainerDifficultyOptionError(
            "Evolution-stage trainer rules require Trainer Pokémon "
            "randomisation."
        )

    if boss_permanent_megas and not trainer_randomisation:
        raise TrainerDifficultyOptionError(
            "Boss permanent Megas require Trainer Pokémon randomisation."
        )

    if boss_permanent_megas and not permanent_megas:
        raise TrainerDifficultyOptionError(
            "Boss permanent Megas require Permanent Mega Evolutions."
        )

    config = {
        "evolution_stage_rules": evolution_stage_rules,
        "boss_permanent_megas": boss_permanent_megas,
        "trainer_randomisation": trainer_randomisation,
        "permanent_megas": permanent_megas,
        "level_boost": level_boost,
        "level_scope": level_scope,
    }
    config_text = json.dumps(config, indent=2) + "\n"
    changed = (
        not CONFIG_FILE.exists()
        or CONFIG_FILE.read_text(encoding="utf-8") != config_text
    )

    if changed:
        CONFIG_FILE.write_text(config_text, encoding="utf-8")

    print(
        "  Evolution-stage trainer rules: "
        + ("ON" if evolution_stage_rules else "off")
    )
    print(
        "  Later-boss permanent Mega ace: "
        + ("ON" if boss_permanent_megas else "off")
    )

    return changed
