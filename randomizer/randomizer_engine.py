#!/usr/bin/env python3
"""
In-process randomizer execution engine.

This is the compatibility layer between the GUI/master controller and the
existing legacy randomizer scripts.

Why it exists:
- The GUI no longer needs to launch master_randomizer.py in a child process.
- master_randomizer.py no longer needs to launch every randomizer in a child
  process.
- Existing randomizer scripts can keep their current command-line style while
  we migrate them gradually to proper Python functions.

Later, individual randomizers can expose a function-based API and be registered
here directly without requiring any GUI changes.
"""

import contextlib
import io
import os
import runpy
import sys
import traceback
from pathlib import Path



from runtime_paths import ROOT, RANDOMIZER_DIR
COMPONENT_LABELS = {
    "pokemon_types": "Pokémon types",
    "pokemon_bst": "Pokémon base stats",
    "abilities": "Abilities",
    "evolutions": "Evolutions",
    "move_types": "Move types",
    "moves": "Pokémon level-up moves",
    "evolution_moves": "Evolution-required moves",
    "tms": "TM compatibility",
    "trade_evos": "Trade evolutions",
    "trades": "NPC trades",
    "wild": "Wild Pokémon encounters",
    "statics": "Static Pokémon encounters",
    "eggs": "Gift eggs",
    "starters": "Starters",
    "trainers": "Trainer Pokémon",
    "items": "Found items",
}


SCRIPT_CANDIDATES = {
    "pokemon_types": (
        "randomize_pokemon_types.py",
    ),
    "pokemon_bst": (
        "randomize_pokemon_bst.py",
    ),
    "abilities": (
        "randomize_abilities.py",
    ),
    "evolutions": (
        "randomize_evolutions.py",
    ),
    "move_types": (
        "randomize_move_types.py",
    ),
    "moves": (
        "randomize_moves.py",
    ),
    "evolution_moves": (
        "ensure_evolution_moves.py",
    ),
    "tms": (
        "randomize_tm_compatibility.py",
    ),
    "trade_evos": (
        "fix_trade_evolutions.py",
    ),
    "trades": (
        "randomize_trades.py",
    ),
    "wild": (
        "randomize_wild_encounters.py",
    ),
    "statics": (
        "randomize_static_encounters.py",
    ),
    "eggs": (
        "randomize_egg_gifts.py",
    ),
    "starters": (
        "randomize_starters.py",
    ),
    "trainers": (
        "randomize_trainer_pokemon.py",
    ),
    "items": (
        "randomize_items.py",
    ),
}


class RandomizerExecutionError(RuntimeError):
    pass


class TeeWriter(io.TextIOBase):
    """
    Write text to multiple streams.

    Used when legacy randomizer output needs to be mirrored to multiple streams.
    """

    def __init__(self, *streams):
        self.streams = [
            stream
            for stream in streams
            if stream is not None
        ]

    def write(self, text):
        for stream in self.streams:
            stream.write(text)
            stream.flush()

        return len(text)

    def flush(self):
        for stream in self.streams:
            stream.flush()


def resolve_script(component):
    if component not in SCRIPT_CANDIDATES:
        raise RandomizerExecutionError(
            f"Unknown randomizer component: {component}"
        )

    for filename in SCRIPT_CANDIDATES[component]:
        path = RANDOMIZER_DIR / filename

        if path.exists():
            return path

    tried = "\n".join(
        f"  {name}"
        for name in SCRIPT_CANDIDATES[component]
    )

    raise RandomizerExecutionError(
        f"No script found for component '{component}'. Tried:\n{tried}"
    )


def _build_legacy_argv(
    script_path,
    seed,
    pokemon_bst_mode=None,
    wild_mode=None,
    wild_allow_special=False,
    wild_similar_bst=False,
    static_mode=None,
    trainer_mode=None,
    trainer_allow_special=False,
    trainer_similar_bst=False,
    trainer_force_six_major=False,
    trainer_type_themes=False,
    move_species_specific=False,
    move_same_type_bias=False,
    include_game_corner=False,
    starter_three_stage_base=False,
):
    argv = [
        str(script_path),
        str(seed),
    ]

    if script_path.name == "randomize_pokemon_bst.py":
        if pokemon_bst_mode not in {
            "same",
            "stages",
            "full",
        }:
            raise RandomizerExecutionError(
                "Pokémon BST randomization requires mode "
                "'same', 'stages', or 'full'."
            )

        argv.extend(
            [
                "--mode",
                pokemon_bst_mode,
            ]
        )

    if script_path.name == "randomize_moves.py":
        if move_species_specific:
            argv.append("--species-specific-pools")

        if move_same_type_bias:
            argv.append("--same-type-bias")

    if script_path.name == "randomize_wild_encounters.py":
        if wild_mode not in {"mapping", "slots", "runtime"}:
            raise RandomizerExecutionError(
                "Wild encounters require mode "
                "'mapping', 'slots', or 'runtime'."
            )

        argv.extend(
            [
                "--mode",
                wild_mode,
            ]
        )

        if wild_allow_special:
            argv.append("--allow-special")

        if wild_similar_bst:
            argv.append("--similar-bst")

    if script_path.name == "randomize_static_encounters.py":
        if static_mode not in {"preserve", "full"}:
            raise RandomizerExecutionError(
                "Static encounters require mode 'preserve' or 'full'."
            )

        argv.extend(
            [
                "--mode",
                static_mode,
            ]
        )

    if script_path.name == "randomize_trainer_pokemon.py":
        if trainer_mode not in {"mapping", "full"}:
            raise RandomizerExecutionError(
                "Trainers require mode 'mapping' or 'full'."
            )

        argv.extend(
            [
                "--mode",
                trainer_mode,
            ]
        )

        if trainer_allow_special:
            argv.append("--allow-special")

        if trainer_similar_bst:
            argv.append("--similar-bst")

        if trainer_force_six_major:
            argv.append("--force-six-major-trainers")

        if trainer_type_themes:
            argv.append("--type-theme-gyms-e4")

    if (
        script_path.name == "randomize_items.py"
        and include_game_corner
    ):
        argv.append("--include-game-corner")

    if (
        script_path.name == "randomize_starters.py"
        and starter_three_stage_base
    ):
        argv.append("--three-stage-base")

    return argv


@contextlib.contextmanager
def _legacy_script_environment(argv):
    """
    Temporarily reproduce the environment a legacy script expects.

    This lets scripts continue using sys.argv and `from config import ...`
    while executing inside the GUI process.
    """

    old_argv = sys.argv[:]
    old_cwd = Path.cwd()
    old_path = sys.path[:]

    try:
        sys.argv = list(argv)

        randomizer_path = str(RANDOMIZER_DIR)

        if randomizer_path not in sys.path:
            sys.path.insert(
                0,
                randomizer_path,
            )

        os.chdir(ROOT)

        yield

    finally:
        sys.argv = old_argv
        sys.path[:] = old_path
        os.chdir(old_cwd)


def run_component(
    component,
    seed,
    log_stream=None,
    pokemon_bst_mode=None,
    wild_mode=None,
    wild_allow_special=False,
    wild_similar_bst=False,
    static_mode=None,
    trainer_mode=None,
    trainer_allow_special=False,
    trainer_similar_bst=False,
    trainer_force_six_major=False,
    trainer_type_themes=False,
    move_species_specific=False,
    move_same_type_bias=False,
    include_game_corner=False,
    starter_three_stage_base=False,
    output_stream=None,
):
    """
    Execute one current randomizer IN THIS PYTHON PROCESS.

    This is intentionally a compatibility bridge. Existing scripts do not need
    to be rewritten immediately.

    Returns the script Path when successful.
    """

    script_path = resolve_script(
        component
    )

    label = COMPONENT_LABELS.get(
        component,
        component,
    )

    if output_stream is None:
        output_stream = sys.stdout

    argv = _build_legacy_argv(
        script_path,
        seed,
        pokemon_bst_mode=pokemon_bst_mode,
        wild_mode=wild_mode,
        wild_allow_special=wild_allow_special,
        wild_similar_bst=wild_similar_bst,
        static_mode=static_mode,
        trainer_mode=trainer_mode,
        trainer_allow_special=trainer_allow_special,
        trainer_similar_bst=trainer_similar_bst,
        trainer_force_six_major=trainer_force_six_major,
        trainer_type_themes=trainer_type_themes,
        move_species_specific=move_species_specific,
        move_same_type_bias=move_same_type_bias,
        include_game_corner=include_game_corner,
        starter_three_stage_base=starter_three_stage_base,
    )

    output_stream.write("\n")
    output_stream.write("=" * 70 + "\n")
    output_stream.write(
        f"{label} ({script_path.name})\n"
    )

    if component == "pokemon_bst":
        output_stream.write(
            f"Mode: {pokemon_bst_mode}\n"
        )

    if component == "moves":
        output_stream.write(
            "Species-specific move pools: "
            + ("yes" if move_species_specific else "no")
            + "\n"
        )
        output_stream.write(
            "Same-type move bias: "
            + ("yes" if move_same_type_bias else "no")
            + "\n"
        )

    if component == "wild":
        output_stream.write(
            f"Mode: {wild_mode}\n"
        )

    if component == "statics":
        output_stream.write(
            f"Mode: {static_mode}\n"
        )

    if component == "trainers":
        output_stream.write(
            f"Mode: {trainer_mode}\n"
        )
        output_stream.write(
            "Legendary / special Pokemon allowed: "
            + ("yes" if trainer_allow_special else "no")
            + "\n"
        )
        output_stream.write(
            f"Similar BST (±25): "
            + ("yes" if trainer_similar_bst else "no")
            + "\n"
        )
        output_stream.write(
            "Six-Pokémon Gym Leader / Elite Four / Champion teams: "
            + ("yes" if trainer_force_six_major else "no")
            + "\n"
        )
        output_stream.write(
            "Randomized Gym / Elite Four type themes: "
            + ("yes" if trainer_type_themes else "no")
            + "\n"
        )

    if component == "starters" and starter_three_stage_base:
        output_stream.write(
            "Rule: base Pokémon from three-stage evolution lines only\n"
        )

    output_stream.write("=" * 70 + "\n\n")
    output_stream.flush()

    if log_stream is not None:
        log_stream.write("\n")
        log_stream.write("=" * 70 + "\n")
        log_stream.write(
            f"{label} ({script_path.name})\n"
        )

        if component == "pokemon_bst":
            log_stream.write(
                f"Mode: {pokemon_bst_mode}\n"
            )

        if component == "moves":
            log_stream.write(
                "Species-specific move pools: "
                + ("yes" if move_species_specific else "no")
                + "\n"
            )
            log_stream.write(
                "Same-type move bias: "
                + ("yes" if move_same_type_bias else "no")
                + "\n"
            )

        if component == "wild":
            log_stream.write(
                f"Mode: {wild_mode}\n"
            )

        if component == "statics":
            log_stream.write(
                f"Mode: {static_mode}\n"
            )

        if component == "trainers":
            log_stream.write(
                f"Mode: {trainer_mode}\n"
            )
            log_stream.write(
                "Legendary / special Pokemon allowed: "
                + ("yes" if trainer_allow_special else "no")
                + "\n"
            )
            log_stream.write(
                f"Similar BST (±25): "
                + ("yes" if trainer_similar_bst else "no")
                + "\n"
            )
            log_stream.write(
                "Six-Pokémon Gym Leader / Elite Four / Champion teams: "
                + ("yes" if trainer_force_six_major else "no")
                + "\n"
            )
            log_stream.write(
                "Randomized Gym / Elite Four type themes: "
                + ("yes" if trainer_type_themes else "no")
                + "\n"
            )

        if component == "starters" and starter_three_stage_base:
            log_stream.write(
                "Rule: base Pokémon from three-stage evolution lines only\n"
            )

        log_stream.write("=" * 70 + "\n\n")
        log_stream.flush()

    tee = TeeWriter(
        output_stream,
        log_stream,
    )

    try:
        with _legacy_script_environment(argv):
            with contextlib.redirect_stdout(tee):
                with contextlib.redirect_stderr(tee):
                    runpy.run_path(
                        str(script_path),
                        run_name="__main__",
                    )

    except SystemExit as exc:
        # argparse and some scripts use sys.exit().
        code = exc.code

        if code in (
            None,
            0,
        ):
            return script_path

        raise RandomizerExecutionError(
            f"{script_path.name} exited with code {code}."
        ) from exc

    except Exception as exc:
        trace = traceback.format_exc()

        tee.write("\n")
        tee.write(trace)

        raise RandomizerExecutionError(
            f"{script_path.name} failed: {exc}"
        ) from exc

    return script_path
