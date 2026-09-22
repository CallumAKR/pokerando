#!/usr/bin/env python3

import ast
import json
import random
import re
import sys
from pathlib import Path

from config import PROTECTED_SPECIES
from rival_starter_continuity import (
    is_rival_starter_slot,
    read_current_starters,
    rival_starter_species_for_trainer,
    rival_starter_continuity_enabled,
)
from trainer_difficulty_options import CONFIG_FILE
from wild_runtime_patch import BST_TOLERANCE


# ============================================================
# PATHS / CONFIG
# ============================================================

ROOT = Path(__file__).resolve().parent.parent

TRAINERS_FILE = ROOT / "src/data/trainers.party"
SPECIES_DIR = ROOT / "src/data/pokemon/species_info"
# ============================================================
# COMMAND LINE
# ============================================================

seed = (
    int(sys.argv[1])
    if len(sys.argv) > 1
    else random.randrange(2**32)
)

TRAINER_MODE = None

if "--mode" in sys.argv:
    mode_index = sys.argv.index("--mode") + 1

    if mode_index >= len(sys.argv):
        raise RuntimeError(
            "--mode requires 'mapping' or 'full'."
        )

    TRAINER_MODE = sys.argv[mode_index]

if TRAINER_MODE not in {
    "mapping",
    "full",
}:
    raise RuntimeError(
        "Trainer randomizer requires:\n"
        "  --mode mapping\n"
        "or\n"
        "  --mode full"
    )

TRAINER_ALLOW_SPECIAL = (
    "--allow-special"
    in sys.argv[2:]
)

TRAINER_SIMILAR_BST = (
    "--similar-bst"
    in sys.argv[2:]
)

TRAINER_FORCE_SIX_MAJOR = (
    "--force-six-major-trainers"
    in sys.argv[2:]
)

TRAINER_TYPE_THEMES = (
    "--type-theme-gyms-e4"
    in sys.argv[2:]
)

RIVAL_STARTER_CONTINUITY = rival_starter_continuity_enabled()
RIVAL_STARTERS = (
    read_current_starters()
    if RIVAL_STARTER_CONTINUITY
    else ()
)

trainer_difficulty = {
    "evolution_stage_rules": False,
    "boss_permanent_megas": False,
    "trainer_randomisation": False,
    "permanent_megas": False,
    "level_boost": 0,
    "level_scope": "all",
}

if CONFIG_FILE.exists():
    try:
        loaded_difficulty = json.loads(
            CONFIG_FILE.read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "Could not read randomizer/trainer_difficulty_options.json. "
            "Run the GUI again so it can regenerate the trainer settings."
        ) from exc

    if isinstance(loaded_difficulty, dict):
        for key, default in trainer_difficulty.items():
            trainer_difficulty[key] = loaded_difficulty.get(key, default)

TRAINER_EVOLUTION_STAGE_RULES = bool(
    trainer_difficulty["evolution_stage_rules"]
)
TRAINER_BOSS_PERMANENT_MEGAS = bool(
    trainer_difficulty["boss_permanent_megas"]
)
TRAINER_LEVEL_BOOST = int(
    trainer_difficulty["level_boost"]
)
TRAINER_LEVEL_SCOPE = trainer_difficulty["level_scope"]

if TRAINER_BOSS_PERMANENT_MEGAS and not bool(
    trainer_difficulty["permanent_megas"]
):
    raise RuntimeError(
        "Boss permanent Megas were enabled without Permanent Mega "
        "Evolutions. Run the GUI again to correct the settings."
    )

rng = random.Random(seed)

print(f"Trainer randomizer seed: {seed}")
print(f"Trainer mode: {TRAINER_MODE}")
print(
    "Legendary / special Pokemon allowed: "
    + ("yes" if TRAINER_ALLOW_SPECIAL else "no")
)
print(
    f"Similar BST (±{BST_TOLERANCE}): "
    + ("yes" if TRAINER_SIMILAR_BST else "no")
)
print(
    "Six-Pokémon Gym Leader / Elite Four / Champion teams: "
    + ("yes" if TRAINER_FORCE_SIX_MAJOR else "no")
)
print(
    "Randomized Gym / Elite Four type themes: "
    + ("yes" if TRAINER_TYPE_THEMES else "no")
)
print(
    "Trainer species only: yes "
    "(moves and abilities are not randomized by this component)"
)
print(
    "Evolution-stage trainer rules: "
    + ("yes" if TRAINER_EVOLUTION_STAGE_RULES else "no")
)
print(
    "Permanent Mega ace for later bosses: "
    + ("yes" if TRAINER_BOSS_PERMANENT_MEGAS else "no")
)
print(
    "Rival starter continuity protected: "
    + ("yes" if RIVAL_STARTER_CONTINUITY else "no")
)


# ============================================================
# SPECIES DATA
# ============================================================

species_header_pattern = re.compile(
    r"^\s*\[(SPECIES_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

species_blocks = {}


def read_species_file(filepath):
    text = filepath.read_text(
        encoding="utf-8"
    )

    matches = list(
        species_header_pattern.finditer(text)
    )

    for i, match in enumerate(matches):
        species = match.group(1)

        start = match.start()

        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(text)

        species_blocks[species] = text[start:end]


for filepath in sorted(
    SPECIES_DIR.rglob("*.h")
):
    read_species_file(filepath)


print(
    f"Found {len(species_blocks)} species entries."
)

if len(species_blocks) < 500:
    raise RuntimeError(
        "Species parser found suspiciously few species."
    )


# ============================================================
# SPECIES CLASSIFICATION
# ============================================================

SPECIAL_FLAGS = {
    "isRestrictedLegendary",
    "isSubLegendary",
    "isMythical",
    "isUltraBeast",
    "isParadox",
}

INVALID_FORM_FLAGS = {
    "isMegaEvolution",
    "isPrimalReversion",
    "isUltraBurst",
    "isGigantamax",
    "isTeraForm",
    "isTotem",
}


def has_flag(block, flag):
    return (
        re.search(
            rf"\.{re.escape(flag)}\s*=\s*TRUE",
            block,
        )
        is not None
    )


def is_special(block):
    return any(
        has_flag(block, flag)
        for flag in SPECIAL_FLAGS
    )


def is_invalid_form(block):
    return any(
        has_flag(block, flag)
        for flag in INVALID_FORM_FLAGS
    )


BASE_STAT_FIELDS = (
    "baseHP",
    "baseAttack",
    "baseDefense",
    "baseSpeed",
    "baseSpAttack",
    "baseSpDefense",
)


def get_base_species(block):
    match = re.search(
        r"\.baseSpecies\s*=\s*(SPECIES_[A-Z0-9_]+)",
        block,
    )
    return match.group(1) if match else None


def species_is_special(species, visited=None):
    """Classify forms through their base species when flags are inherited."""

    block = species_blocks.get(species)

    if block is None:
        return False

    if is_special(block):
        return True

    if visited is None:
        visited = set()

    if species in visited:
        return False

    visited = set(visited)
    visited.add(species)

    base_species = get_base_species(block)

    if base_species:
        return species_is_special(base_species, visited)

    return False


def _safe_arithmetic(text):
    cleaned = text.strip()
    cleaned = re.sub(
        r"(?<=\d)[uUlL]+\b",
        "",
        cleaned,
    )

    if not re.fullmatch(
        r"[0-9xXa-fA-F+\-*/()% \t]+",
        cleaned,
    ):
        return None

    try:
        node = ast.parse(
            cleaned,
            mode="eval",
        )
    except SyntaxError:
        return None

    allowed = (
        ast.Expression,
        ast.Constant,
        ast.UnaryOp,
        ast.UAdd,
        ast.USub,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
    )

    if any(
        not isinstance(item, allowed)
        for item in ast.walk(node)
    ):
        return None

    try:
        value = eval(
            compile(node, "<trainer-bst>", "eval"),
            {"__builtins__": {}},
            {},
        )
        return int(value)
    except Exception:
        return None


def parse_stat_expression(expression):
    expression = expression.strip()

    direct = _safe_arithmetic(
        expression
    )
    if direct is not None:
        return direct

    ternary = re.search(
        r"\?\s*([^:]+?)\s*:\s*(.+)$",
        expression,
    )

    if ternary:
        preferred = _safe_arithmetic(
            ternary.group(1)
        )
        if preferred is not None:
            return preferred

        fallback = _safe_arithmetic(
            ternary.group(2)
        )
        if fallback is not None:
            return fallback

    return None


bst_cache = {}


def species_bst(
    species,
    visited=None,
):
    if species in bst_cache:
        return bst_cache[species]

    block = species_blocks.get(
        species
    )

    if block is None:
        bst_cache[species] = None
        return None

    if visited is None:
        visited = set()

    if species in visited:
        bst_cache[species] = None
        return None

    visited = set(visited)
    visited.add(species)

    values = []

    for field in BASE_STAT_FIELDS:
        match = re.search(
            rf"\.{field}\s*=\s*([^,\n]+)",
            block,
        )

        if not match:
            values = []
            break

        value = parse_stat_expression(
            match.group(1)
        )

        if value is None:
            values = []
            break

        values.append(value)

    if len(values) == len(BASE_STAT_FIELDS):
        result = sum(values)
        bst_cache[species] = result
        return result

    base_species = get_base_species(
        block
    )

    if base_species:
        result = species_bst(
            base_species,
            visited,
        )
        bst_cache[species] = result
        return result

    bst_cache[species] = None
    return None


STANDARD_TYPES = (
    "TYPE_NORMAL",
    "TYPE_FIRE",
    "TYPE_WATER",
    "TYPE_ELECTRIC",
    "TYPE_GRASS",
    "TYPE_ICE",
    "TYPE_FIGHTING",
    "TYPE_POISON",
    "TYPE_GROUND",
    "TYPE_FLYING",
    "TYPE_PSYCHIC",
    "TYPE_BUG",
    "TYPE_ROCK",
    "TYPE_GHOST",
    "TYPE_DRAGON",
    "TYPE_DARK",
    "TYPE_STEEL",
    "TYPE_FAIRY",
)

species_type_cache = {}


def species_types(
    species,
    visited=None,
):
    if species in species_type_cache:
        return species_type_cache[species]

    block = species_blocks.get(
        species
    )

    if block is None:
        species_type_cache[species] = frozenset()
        return species_type_cache[species]

    if visited is None:
        visited = set()

    if species in visited:
        species_type_cache[species] = frozenset()
        return species_type_cache[species]

    visited = set(visited)
    visited.add(species)

    match = re.search(
        r"\.types\s*=\s*MON_TYPES\(([^)]*)\)",
        block,
        re.DOTALL,
    )

    if match:
        parsed = frozenset(
            token.strip()
            for token in match.group(1).split(",")
            if token.strip().startswith("TYPE_")
            and token.strip() != "TYPE_NONE"
        )

        if parsed:
            species_type_cache[species] = parsed
            return parsed

    base_species = get_base_species(
        block
    )

    if base_species:
        parsed = species_types(
            base_species,
            visited,
        )
        species_type_cache[species] = parsed
        return parsed

    species_type_cache[species] = frozenset()
    return species_type_cache[species]


species_category = {}

normal_species = []
special_species = []


for species, block in species_blocks.items():

    # --------------------------------------------------------
    # Category
    # --------------------------------------------------------

    category = (
        "special"
        if species_is_special(species)
        else "normal"
    )

    species_category[species] = category

    # --------------------------------------------------------
    # Pool exclusions
    # --------------------------------------------------------

    if species in {
        "SPECIES_NONE",
        "SPECIES_EGG",
    }:
        continue

    if species in PROTECTED_SPECIES:
        continue

    if is_invalid_form(block):
        continue

    if category == "special":
        special_species.append(species)
    else:
        normal_species.append(species)


normal_species.sort()
special_species.sort()


if not normal_species:
    raise RuntimeError(
        "Normal trainer species pool is empty."
    )

eligible_trainer_species = list(
    normal_species
)

if TRAINER_ALLOW_SPECIAL:
    eligible_trainer_species.extend(
        special_species
    )

eligible_trainer_species.sort()

special_eligible_count = sum(
    1
    for species in eligible_trainer_species
    if species_category.get(species) == "special"
)

print()
print("Eligible trainer replacement pool:")
print(
    f"  Total: {len(eligible_trainer_species)}"
)
print(
    f"  Special: {special_eligible_count}"
)
print(
    f"  Ordinary: "
    f"{len(eligible_trainer_species) - special_eligible_count}"
)

if TRAINER_SIMILAR_BST:
    known_bst = sum(
        species_bst(species) is not None
        for species in eligible_trainer_species
    )
    print(
        f"  Species with parsed BST: "
        f"{known_bst}/{len(eligible_trainer_species)}"
    )


# ============================================================
# CURRENT EVOLUTION TREE / PERMANENT MEGA POOL
# ============================================================

EVOLUTION_ENTRY_PATTERN = re.compile(
    r"\{\s*(EVO_[A-Z0-9_]+)\s*,\s*([^,{}\n]+)\s*,\s*"
    r"(SPECIES_[A-Z0-9_]+)"
)

# Battle-only transformations and reverse/devolution entries are deliberately
# excluded. Permanent Mega edges are also excluded through is_invalid_form();
# the separate boss option owns those forms.
PERMANENT_EVOLUTION_METHODS = {
    "EVO_LEVEL",
    "EVO_ITEM",
    "EVO_TRADE",
    "EVO_SCRIPT_TRIGGER",
    "EVO_SPIN",
}

# For methods without a numeric level requirement, wait until the late game
# rather than putting stone/trade/condition evolutions on early trainers.
NON_LEVEL_EVOLUTION_MIN_LEVEL = 30
LATE_GAME_TRAINER_MIN_LEVEL = 30

evolution_edges = {}

for source_species, block in species_blocks.items():
    entries = []

    for method, parameter, target in EVOLUTION_ENTRY_PATTERN.findall(block):
        if method not in PERMANENT_EVOLUTION_METHODS:
            continue

        target_block = species_blocks.get(target)

        if target_block is None or is_invalid_form(target_block):
            continue

        entries.append(
            (
                method,
                parameter.strip(),
                target,
            )
        )

    if entries:
        evolution_edges[source_species] = entries


def evolution_available_at_level(method, parameter, level):
    if method == "EVO_LEVEL":
        try:
            required_level = int(parameter, 0)
        except ValueError:
            required_level = 0

        if required_level > 0:
            return level >= required_level

    return level >= NON_LEVEL_EVOLUTION_MIN_LEVEL


evolution_stage_cache = {}
evolution_stage_upgrades = []


def advance_evolution_stage(species, level, required_type=None):
    """Follow the current (possibly randomised) tree as far as level permits."""

    if (
        not TRAINER_EVOLUTION_STAGE_RULES
        or level < LATE_GAME_TRAINER_MIN_LEVEL
    ):
        return species

    cache_key = (
        species,
        level,
        required_type,
        TRAINER_ALLOW_SPECIAL,
    )

    if cache_key in evolution_stage_cache:
        return evolution_stage_cache[cache_key]

    original = species
    visited = {species}

    for _ in range(8):
        candidates = []

        for method, parameter, target in evolution_edges.get(species, ()):
            if target in visited or target in PROTECTED_SPECIES:
                continue

            if not evolution_available_at_level(
                method,
                parameter,
                level,
            ):
                continue

            if (
                not TRAINER_ALLOW_SPECIAL
                and species_category.get(target) == "special"
            ):
                continue

            if (
                required_type is not None
                and required_type not in species_types(target)
            ):
                continue

            candidates.append(target)

        if not candidates:
            break

        # Branches remain deterministic and difficulty-oriented: take the
        # strongest currently valid target, using the run RNG only for ties.
        known_bst = [
            candidate
            for candidate in candidates
            if species_bst(candidate) is not None
        ]

        if known_bst:
            strongest_bst = max(
                species_bst(candidate)
                for candidate in known_bst
            )
            candidates = [
                candidate
                for candidate in known_bst
                if species_bst(candidate) == strongest_bst
            ]

        species = rng.choice(sorted(candidates))
        visited.add(species)

    evolution_stage_cache[cache_key] = species

    if species != original:
        evolution_stage_upgrades.append(
            (
                original,
                species,
                level,
            )
        )

    return species


mega_species_pool = sorted(
    species
    for species, block in species_blocks.items()
    if (
        has_flag(block, "isMegaEvolution")
        and species not in PROTECTED_SPECIES
        and (
            TRAINER_ALLOW_SPECIAL
            or species_category.get(species) != "special"
        )
    )
)


def mega_base_species(mega_species):
    stem = mega_species.split("_MEGA", 1)[0]
    return stem if stem in species_blocks else None


def direct_mega_candidates(current_species, required_type=None):
    """Return permanent Mega forms belonging to the current species."""

    return [
        species
        for species in mega_species_pool
        if (
            mega_base_species(species) == current_species
            and (
                required_type is None
                or required_type in species_types(species)
            )
        )
    ]


def choose_boss_mega(
    current_species,
    already_used,
    required_type=None,
):
    """Choose one legal permanent Mega for a later boss's ace slot."""

    candidates = [
        species
        for species in mega_species_pool
        if (
            required_type is None
            or required_type in species_types(species)
        )
    ]

    unused = [
        species
        for species in candidates
        if species not in already_used
    ]

    if unused:
        candidates = unused

    if not candidates:
        theme_text = (
            f" for required type {required_type}"
            if required_type is not None
            else ""
        )
        raise RuntimeError(
            "No eligible permanent Mega species exists"
            + theme_text
            + ". Check the protected and special-Pokémon settings."
        )

    direct = direct_mega_candidates(
        current_species,
        required_type=required_type,
    )

    # Respect the no-duplicate preference used for the general candidate
    # pool, but do not discard a canonical Mega merely because the same Mega
    # happens to appear elsewhere on the generated team.
    unused_direct = [
        species
        for species in direct
        if species not in already_used
    ]

    if unused_direct:
        return rng.choice(sorted(unused_direct))

    if direct:
        return rng.choice(sorted(direct))

    # Without a formal boss type theme, prefer a Mega sharing a type with the
    # current ace before comparing power. This makes the replacement feel like
    # it still belongs on that team.
    if required_type is None:
        current_types = species_types(current_species)
        type_matches = [
            species
            for species in candidates
            if current_types.intersection(species_types(species))
        ]

        if type_matches:
            candidates = type_matches

    current_bst = species_bst(current_species)
    known_bst = [
        species
        for species in candidates
        if species_bst(species) is not None
    ]

    if current_bst is not None and known_bst:
        closest_difference = min(
            abs(species_bst(species) - current_bst)
            for species in known_bst
        )
        candidates = [
            species
            for species in known_bst
            if abs(species_bst(species) - current_bst)
            == closest_difference
        ]

    return rng.choice(sorted(candidates))


if TRAINER_BOSS_PERMANENT_MEGAS and not mega_species_pool:
    raise RuntimeError(
        "Boss permanent Megas are enabled, but no eligible Mega species "
        "were found in the current species data."
    )


# ============================================================
# SPECIES SELECTION / GLOBAL MAPPING
# ============================================================

# Mapping keys include the required type theme. This is necessary because the
# same original species can appear in two differently themed Gyms; a single
# global species mapping could not satisfy both themes.
trainer_species_mapping = {}
trainer_mapping_targets_used = {}

bst_audited_source_species = set()
type_theme_bst_fallbacks = []


def mapping_context(required_type):
    return required_type or "__UNTHEMED__"


def candidate_pool(
    original_species,
    required_type=None,
):
    """
    Build the approved replacement pool for this original trainer species.

    Hard rules:
    - special Pokémon are excluded unless --allow-special is active;
    - if required_type is set, every candidate must contain that type.

    Similar BST is hard for normal trainer randomization. For a Gym / Elite
    Four type theme, however, the type rule has priority. If the required type
    has no candidate within ±BST_TOLERANCE, use the closest-BST valid Pokémon
    of that type and record the fallback in the log.
    """
    candidates = list(
        eligible_trainer_species
    )

    if required_type is not None:
        candidates = [
            species
            for species in candidates
            if required_type
            in species_types(species)
        ]

        if not candidates:
            raise RuntimeError(
                "No eligible trainer Pokémon exist for required type "
                f"{required_type}. Check protected/special species settings."
            )

    if not TRAINER_SIMILAR_BST:
        return candidates

    original_bst = species_bst(
        original_species
    )

    if original_bst is None:
        if (
            required_type is None
            and original_species in candidates
        ):
            return [original_species]

        # Theme remains hard. With an unknown source BST, we cannot apply the
        # numeric restriction, so retain the correct themed pool.
        if required_type is not None:
            type_theme_bst_fallbacks.append(
                (
                    original_species,
                    None,
                    required_type,
                    None,
                    None,
                )
            )
            return candidates

        raise RuntimeError(
            "Could not apply the trainer similar-BST rule to "
            f"{original_species}: its BST could not be parsed and the "
            "original species is excluded by the current trainer options."
        )

    bst_candidates = []

    for species in candidates:
        candidate_bst = species_bst(
            species
        )

        if (
            candidate_bst is not None
            and abs(
                candidate_bst
                - original_bst
            )
            <= BST_TOLERANCE
        ):
            bst_candidates.append(
                species
            )

    if bst_candidates:
        bst_audited_source_species.add(
            (
                original_species,
                required_type,
            )
        )
        return bst_candidates

    if required_type is not None:
        known = [
            (
                species,
                species_bst(species),
            )
            for species in candidates
            if species_bst(species) is not None
        ]

        if not known:
            raise RuntimeError(
                "No BST data could be parsed for any eligible "
                f"{required_type} trainer Pokémon."
            )

        closest_difference = min(
            abs(candidate_bst - original_bst)
            for _, candidate_bst in known
        )

        closest = [
            species
            for species, candidate_bst in known
            if abs(candidate_bst - original_bst)
            == closest_difference
        ]

        closest_bsts = sorted({
            species_bst(species)
            for species in closest
        })

        type_theme_bst_fallbacks.append(
            (
                original_species,
                original_bst,
                required_type,
                closest_difference,
                tuple(closest_bsts),
            )
        )

        return closest

    if original_species in candidates:
        return [original_species]

    raise RuntimeError(
        "No eligible trainer replacement satisfies the "
        f"±{BST_TOLERANCE} BST rule for {original_species} "
        f"(BST {original_bst})."
    )


def choose_random_species(
    original_species,
    already_used,
    required_type=None,
):
    """
    mapping:
        Reuse one replacement for each (original species, type-theme context).

    full:
        Reroll every trainer Pokémon independently.

    Both modes obey the special-Pokémon, type-theme and BST rules.
    """
    key = (
        original_species,
        required_type,
    )

    if (
        TRAINER_MODE == "mapping"
        and key in trainer_species_mapping
    ):
        return trainer_species_mapping[
            key
        ]

    pool = candidate_pool(
        original_species,
        required_type=required_type,
    )

    context = mapping_context(
        required_type
    )

    used_mapping_targets = (
        trainer_mapping_targets_used
        .setdefault(
            context,
            set(),
        )
    )

    if TRAINER_MODE == "mapping":
        candidates = [
            species
            for species in pool
            if species not in used_mapping_targets
        ]

        if not candidates:
            candidates = list(pool)

        if (
            original_species in candidates
            and len(candidates) > 1
        ):
            candidates = [
                species
                for species in candidates
                if species != original_species
            ]

        result = rng.choice(
            candidates
        )

        trainer_species_mapping[
            key
        ] = result

        used_mapping_targets.add(
            result
        )

        return result

    candidates = [
        species
        for species in pool
        if species not in already_used
    ]

    if not candidates:
        candidates = list(pool)

    if (
        original_species in candidates
        and len(candidates) > 1
    ):
        candidates = [
            species
            for species in candidates
            if species != original_species
        ]

    return rng.choice(
        candidates
    )


# ============================================================
# TRAINERS.PARTY PARSING
# ============================================================

trainer_header_pattern = re.compile(
    r"^===\s*(TRAINER_[A-Z0-9_]+)\s*===\s*$",
    re.MULTILINE,
)


def split_paragraphs(text):
    """
    Split a trainer's party body into blank-line-separated
    paragraphs while keeping paragraph text intact.
    """

    return re.split(
        r"\n[ \t]*\n",
        text.strip(),
    )


def paragraph_is_mon(paragraph):
    """
    A trainer Pokémon paragraph has a Level: line in the current baseline.

    Pool members use the same Pokémon paragraph format, so they are handled by
    exactly the same species/BST randomization logic as fixed-party members.
    """

    return (
        re.search(
            r"^Level:\s*[0-9]+\s*$",
            paragraph,
            re.MULTILINE,
        )
        is not None
    )


def get_party_size(section):
    """
    Expansion's current Trainer Party Pool syntax uses Party Size.

    A trainer is a party pool when the number of defined Pokémon is greater
    than Party Size. The game then selects the actual battle party from the
    defined pool at runtime.
    """
    match = re.search(
        r"^Party Size:\s*([0-9]+)\s*$",
        section,
        re.MULTILINE,
    )

    return int(match.group(1)) if match else None


def get_copy_pool_target(section):
    """
    Return the TRAINER_* referenced by Copy Pool, if present.
    """
    match = re.search(
        r"^Copy Pool:\s*(TRAINER_[A-Z0-9_]+)\s*$",
        section,
        re.MULTILINE,
    )

    return match.group(1) if match else None


def get_level(paragraph):
    match = re.search(
        r"^Level:\s*([0-9]+)\s*$",
        paragraph,
        re.MULTILINE,
    )

    if match:
        return int(match.group(1))

    return 1


def set_level(
    paragraph,
    level,
):

    if re.search(
        r"^Level:\s*[0-9]+\s*$",
        paragraph,
        re.MULTILINE,
    ):

        return re.sub(
            r"^Level:\s*[0-9]+\s*$",
            f"Level: {level}",
            paragraph,
            count=1,
            flags=re.MULTILINE,
        )

    lines = paragraph.splitlines()

    if lines:
        lines.insert(
            1,
            f"Level: {level}",
        )

    return "\n".join(lines)


def get_original_species(paragraph):
    """
    Current clean trainers.party mostly uses display names,
    whereas our randomized output will use SPECIES_*.

    Try constants first.

    For original display names, map common names using
    speciesName from species_info.
    """

    first_line = (
        paragraph.splitlines()[0].strip()
    )

    # Strip held item.
    first_part = first_line.split(
        " @ ",
        1,
    )[0].strip()

    # Strip nickname syntax:
    #
    # Bubbles (Wobbuffet) (F)
    #
    if "(" in first_part:

        paren_names = re.findall(
            r"\(([^()]+)\)",
            first_part,
        )

        if paren_names:

            for candidate in reversed(
                paren_names
            ):

                if candidate in {"M", "F"}:
                    continue

                first_part = candidate
                break

    if first_part.startswith("SPECIES_"):
        return first_part

    normalized = (
        first_part
        .upper()
        .replace("É", "E")
        .replace("’", "")
        .replace("'", "")
        .replace(".", "")
        .replace(":", "")
        .replace("-", "_")
        .replace(" ", "_")
    )

    # Direct constant guess.
    direct = "SPECIES_" + normalized

    if direct in species_blocks:
        return direct

    # Fall back to speciesName fields.
    for species, block in species_blocks.items():

        match = re.search(
            r'\.speciesName\s*=\s*_?\("([^"]+)"\)',
            block,
        )

        if (
            match
            and match.group(1).casefold()
            == first_part.casefold()
        ):
            return species

    # Unknown original species should not stop the entire run.
    return None


def get_held_item(paragraph):
    """
    Preserve the trainer's existing held item.

    Example:
        Nosepass @ Oran Berry
    """

    first_line = (
        paragraph.splitlines()[0]
        if paragraph.splitlines()
        else ""
    )

    if " @ " in first_line:
        return (
            first_line.split(
                " @ ",
                1,
            )[1].strip()
        )

    return None


def remove_move_lines(paragraph):

    lines = []

    for line in paragraph.splitlines():

        if re.match(
            r"^\s*-\s+",
            line,
        ):
            continue

        lines.append(line)

    return "\n".join(lines)


def remove_ability_line(paragraph):
    """
    Remove a species-specific forced Ability: override when the species changes.

    The Trainer Pokémon randomizer does not choose an ability. With no forced
    override, Expansion uses the replacement species' current ability data,
    which is exactly what the separate Abilities randomizer controls.
    """

    return re.sub(
        r"^Ability:.*\n?",
        "",
        paragraph,
        flags=re.MULTILINE,
    )


def randomize_mon_paragraph(
    paragraph,
    used_species,
    override_level=None,
    preserve_item=True,
    required_type=None,
    evolution_level=None,
):

    original_species = (
        get_original_species(paragraph)
    )

    if original_species is None:

        # If we can't identify a Pokémon safely, preserve it.
        return (
            paragraph,
            None,
            None,
            get_level(paragraph),
        )

    level = (
        override_level
        if override_level is not None
        else get_level(paragraph)
    )

    new_species = choose_random_species(
        original_species,
        used_species,
        required_type=required_type,
    )

    new_species = advance_evolution_stage(
        new_species,
        (
            evolution_level
            if evolution_level is not None
            else level
        ),
        required_type=required_type,
    )

    held_item = (
        get_held_item(paragraph)
        if preserve_item
        else None
    )

    # --------------------------------------------------------
    # Species-only trainer randomization
    # --------------------------------------------------------
    #
    # Explicit moves and Ability: overrides belong to the old species. Remove
    # those overrides rather than inventing replacements here.
    #
    # Expansion will generate the replacement Pokémon's normal moves from the
    # current learnset data and use its current species ability data. Therefore
    # the separate Level-up Moves / Abilities randomizers remain the only
    # components that alter those underlying systems.
    #
    # Nature, EVs, IVs, gender, shiny state, ball, tags and other trainer
    # metadata are left untouched.
    # --------------------------------------------------------

    new_paragraph = remove_move_lines(
        paragraph
    )

    new_paragraph = remove_ability_line(
        new_paragraph
    )

    # --------------------------------------------------------
    # Replace first line
    # --------------------------------------------------------

    lines = new_paragraph.splitlines()

    first_line = new_species

    if held_item:
        first_line += f" @ {held_item}"

    lines[0] = first_line

    new_paragraph = "\n".join(lines)

    # --------------------------------------------------------
    # Level
    # --------------------------------------------------------

    new_paragraph = set_level(
        new_paragraph,
        level,
    )

    return (
        new_paragraph.strip(),
        original_species,
        new_species,
        level,
    )


def replace_paragraph_species(paragraph, new_species):
    """Replace only the species, retaining the generated party metadata."""

    lines = paragraph.splitlines()

    if not lines:
        return paragraph

    held_item = get_held_item(paragraph)
    lines[0] = new_species

    if held_item:
        lines[0] += f" @ {held_item}"

    return "\n".join(lines)


def validate_trainer_output(text):
    """
    Catch trainer.party formatting corruption before writing the file.

    A move line must stay inside its Pokémon paragraph. A blank line followed
    by "- Move Name" makes trainerproc interpret that move as a new Pokémon.
    """
    bad_move_paragraph = re.search(
        r"\n[ \t]*\n[ \t]*-\s+\S",
        text,
    )

    if bad_move_paragraph:
        line = (
            text.count(
                "\n",
                0,
                bad_move_paragraph.start(),
            )
            + 1
        )

        raise RuntimeError(
            "Trainer output validation failed: a move line was separated "
            "from its Pokémon by a blank line "
            f"(near line {line})."
        )

    # Randomized Pokémon lines should contain a real SPECIES_* constant,
    # never the malformed double-underscore form produced when trainerproc
    # mistakes a move paragraph for a Pokémon.
    bad_species = re.search(
        r"^SPECIES__",
        text,
        re.MULTILINE,
    )

    if bad_species:
        line = (
            text.count(
                "\n",
                0,
                bad_species.start(),
            )
            + 1
        )

        raise RuntimeError(
            "Trainer output validation failed: malformed species constant "
            f"near line {line}."
        )


# ============================================================
# TRAINER SECTIONS
# ============================================================

trainer_text = TRAINERS_FILE.read_text(
    encoding="utf-8"
)

header_matches = list(
    trainer_header_pattern.finditer(
        trainer_text
    )
)

print(
    f"Found {len(header_matches)} trainer entries."
)

trainer_names = {
    match.group(1)
    for match in header_matches
}


replacements = []

randomized_trainers = 0
randomized_mons = 0
expanded_trainers = 0
special_results = 0

party_pool_trainers = 0
party_pool_members = 0
party_pool_runtime_slots = 0
copy_pool_trainers = 0
legacy_pool_fields = 0
unusual_sections_skipped = 0
continuous_rival_starters = 0

spoiler_entries = []


# These trainer classes can optionally be expanded to at least six Pokémon.
FORCE_SIX_CLASS_NAMES = {
    "Leader",
    "Elite Four",
    "Champion",
}

# Difficulty options treat May and Brendan as major opponents without making
# the separate six-Pokemon-team option expand their early-game parties.
DIFFICULTY_MAJOR_CLASS_NAMES = FORCE_SIX_CLASS_NAMES | {
    "Rival",
}

FINAL_RIVAL_BATTLE_PATTERN = re.compile(
    r"^TRAINER_(?:MAY|BRENDAN)_LILYCOVE_"
    r"(?:TREECKO|TORCHIC|MUDKIP)$"
)


def effective_trainer_level(level, trainer_class):
    """Return the level the trainer will have after difficulty processing."""

    should_boost = (
        TRAINER_LEVEL_BOOST > 0
        and (
            TRAINER_LEVEL_SCOPE == "all"
            or trainer_class in DIFFICULTY_MAJOR_CLASS_NAMES
        )
    )

    return min(
        100,
        level + (TRAINER_LEVEL_BOOST if should_boost else 0),
    )


GYM_MAP_PREFIXES = (
    ("Rustboro Gym", "RustboroCity"),
    ("Dewford Gym", "DewfordTown"),
    ("Mauville Gym", "MauvilleCity"),
    ("Lavaridge Gym", "LavaridgeTown"),
    ("Petalburg Gym", "PetalburgCity"),
    ("Fortree Gym", "FortreeCity"),
    ("Mossdeep Gym", "MossdeepCity"),
    ("Sootopolis Gym", "SootopolisCity"),
)


def trainer_section_bounds():
    result = {}

    for index, match in enumerate(
        header_matches
    ):
        trainer_id = match.group(1)
        start = match.start()
        end = (
            header_matches[index + 1].start()
            if index + 1 < len(header_matches)
            else len(trainer_text)
        )
        result[trainer_id] = trainer_text[start:end]

    return result


trainer_sections = trainer_section_bounds()


def trainer_metadata(section):
    class_match = re.search(
        r"^Class:\s*(.+?)\s*$",
        section,
        re.MULTILINE,
    )
    name_match = re.search(
        r"^Name:\s*(.+?)\s*$",
        section,
        re.MULTILINE,
    )

    return (
        class_match.group(1).strip()
        if class_match
        else "Unknown",
        name_match.group(1).strip()
        if name_match
        else None,
    )


trainer_meta = {
    trainer_id: trainer_metadata(section)
    for trainer_id, section in trainer_sections.items()
}


def discover_gym_trainer_groups():
    maps_root = ROOT / "data/maps"
    groups = {}
    missing = []

    for label, city_prefix in GYM_MAP_PREFIXES:
        ids = set()

        gym_dirs = sorted(
            path
            for path in maps_root.glob(
                f"{city_prefix}_Gym*"
            )
            if path.is_dir()
        )

        for gym_dir in gym_dirs:
            for script_path in sorted(
                gym_dir.rglob("*.inc")
            ):
                text = script_path.read_text(
                    encoding="utf-8"
                )

                ids.update(
                    trainer_id
                    for trainer_id in re.findall(
                        r"\bTRAINER_[A-Z0-9_]+\b",
                        text,
                    )
                    if trainer_id in trainer_names
                )

        # Include Leader rematch/alternate party entries that share the same
        # display Name as the Leader referenced by the Gym scripts.
        leader_names = {
            display_name
            for trainer_id in ids
            for trainer_class, display_name in [
                trainer_meta.get(
                    trainer_id,
                    ("Unknown", None),
                )
            ]
            if trainer_class == "Leader"
            and display_name
        }

        if leader_names:
            ids.update(
                trainer_id
                for trainer_id, (
                    trainer_class,
                    display_name,
                ) in trainer_meta.items()
                if trainer_class == "Leader"
                and display_name in leader_names
            )

        if not ids:
            missing.append(
                label
            )
        else:
            groups[label] = ids

    if missing:
        raise RuntimeError(
            "Could not discover trainer IDs for required Hoenn Gym map(s): "
            + ", ".join(missing)
        )

    return groups


def discover_elite_four_groups():
    groups = {}

    for trainer_id, (
        trainer_class,
        display_name,
    ) in trainer_meta.items():
        if (
            trainer_class != "Elite Four"
            or not display_name
        ):
            continue

        groups.setdefault(
            display_name,
            set(),
        ).add(
            trainer_id
        )

    if len(groups) != 4:
        raise RuntimeError(
            "Expected 4 Elite Four member groups, found "
            f"{len(groups)}: {', '.join(sorted(groups))}"
        )

    return groups


def human_type(type_name):
    return (
        type_name
        .removeprefix("TYPE_")
        .replace("_", " ")
        .title()
    )


def assign_unique_types(group_names):
    available = [
        type_name
        for type_name in STANDARD_TYPES
        if any(
            type_name in species_types(species)
            for species in eligible_trainer_species
        )
    ]

    if len(available) < len(group_names):
        raise RuntimeError(
            "Not enough eligible Pokémon types to assign unique "
            "trainer themes."
        )

    chosen = rng.sample(
        available,
        len(group_names),
    )

    return dict(
        zip(
            group_names,
            chosen,
        )
    )


trainer_theme_types = {}
gym_theme_assignments = {}
elite_four_theme_assignments = {}

gym_groups = {}
elite_four_groups = {}

if TRAINER_TYPE_THEMES or TRAINER_BOSS_PERMANENT_MEGAS:
    gym_groups = discover_gym_trainer_groups()

if TRAINER_TYPE_THEMES:
    elite_four_groups = discover_elite_four_groups()

    # Gyms are unique from other Gyms; E4 members are unique from other E4
    # members. A Gym and an E4 member may coincidentally share a type, matching
    # the way main-series games can reuse types across different challenge sets.
    gym_theme_assignments = assign_unique_types(
        list(gym_groups)
    )
    elite_four_theme_assignments = assign_unique_types(
        list(elite_four_groups)
    )

    for label, trainer_ids in gym_groups.items():
        required_type = gym_theme_assignments[
            label
        ]
        for trainer_id in trainer_ids:
            trainer_theme_types[
                trainer_id
            ] = required_type

    for member_name, trainer_ids in elite_four_groups.items():
        required_type = elite_four_theme_assignments[
            member_name
        ]
        for trainer_id in trainer_ids:
            trainer_theme_types[
                trainer_id
            ] = required_type

    print()
    print("Gym type themes:")
    for label in gym_groups:
        print(
            f"  {label}: "
            f"{human_type(gym_theme_assignments[label])}"
        )

    print("Elite Four type themes:")
    for member_name in sorted(
        elite_four_groups
    ):
        print(
            f"  {member_name}: "
            f"{human_type(elite_four_theme_assignments[member_name])}"
        )


boss_mega_trainer_ids = set()
boss_mega_applied_ids = set()
rival_starter_mega_applied_ids = set()
rival_fallback_mega_applied_ids = set()

if TRAINER_BOSS_PERMANENT_MEGAS:
    late_gym_labels = {
        label
        for label, _ in GYM_MAP_PREFIXES[4:]
    }

    for label in late_gym_labels:
        boss_mega_trainer_ids.update(
            trainer_id
            for trainer_id in gym_groups[label]
            if trainer_meta.get(trainer_id, (None, None))[0] == "Leader"
        )

    boss_mega_trainer_ids.update(
        trainer_id
        for trainer_id, (trainer_class, _) in trainer_meta.items()
        if trainer_class in {"Elite Four", "Champion"}
    )

    final_rival_ids = {
        trainer_id
        for trainer_id, (trainer_class, _) in trainer_meta.items()
        if (
            trainer_class == "Rival"
            and FINAL_RIVAL_BATTLE_PATTERN.fullmatch(trainer_id)
        )
    }

    if len(final_rival_ids) != 6:
        raise RuntimeError(
            "Expected six May/Brendan Lilycove rival variants for the "
            f"Boss Mega option, found {len(final_rival_ids)}."
        )

    boss_mega_trainer_ids.update(final_rival_ids)

    print()
    print(
        "Later Gym / Elite Four / Champion / final rival parties receiving a "
        f"permanent Mega ace: {len(boss_mega_trainer_ids)}"
    )


for index, header_match in enumerate(
    header_matches
):

    trainer_name = (
        header_match.group(1)
    )

    start = header_match.start()

    end = (
        header_matches[index + 1].start()
        if index + 1 < len(header_matches)
        else len(trainer_text)
    )

    section = trainer_text[start:end]

    if re.search(
        r"^(?:Pool|Party Pool):",
        section,
        re.MULTILINE,
    ):
        # This is not the current documented TPP syntax, but preserve custom or
        # legacy metadata if present and still randomize any normal Pokémon
        # paragraphs we can identify safely.
        legacy_pool_fields += 1

    # --------------------------------------------------------
    # Current Expansion Trainer Party Pool handling
    # --------------------------------------------------------

    copy_pool_target = get_copy_pool_target(
        section
    )

    if copy_pool_target is not None:
        copy_pool_trainers += 1

        if copy_pool_target not in trainer_names:
            raise RuntimeError(
                f"{trainer_name} uses Copy Pool: {copy_pool_target}, "
                "but that trainer section does not exist."
            )

        # Copy Pool trainers inherit the source trainer's party/pool.
        # A themed Copy Pool is only valid if its source has the same theme.
        if TRAINER_TYPE_THEMES:
            copy_theme = trainer_theme_types.get(
                trainer_name
            )
            source_theme = trainer_theme_types.get(
                copy_pool_target
            )

            if (
                copy_theme is not None
                and copy_theme != source_theme
            ):
                raise RuntimeError(
                    f"{trainer_name} requires {copy_theme} but copies pool "
                    f"{copy_pool_target} with theme {source_theme}."
                )

        # Do not manufacture or rewrite a separate party here. The referenced
        # trainer is randomized in its own section, and this trainer inherits
        # that randomized result when trainerproc builds the data.
        continue

    # --------------------------------------------------------
    # Trainer class
    # --------------------------------------------------------

    class_match = re.search(
        r"^Class:\s*(.+?)\s*$",
        section,
        re.MULTILINE,
    )

    trainer_class = (
        class_match.group(1).strip()
        if class_match
        else "Unknown"
    )

    required_type = (
        trainer_theme_types.get(
            trainer_name
        )
        if TRAINER_TYPE_THEMES
        else None
    )

    # --------------------------------------------------------
    # Find first Pokémon paragraph.
    # --------------------------------------------------------

    paragraphs = split_paragraphs(
        section
    )

    mon_indices = [
        i
        for i, paragraph in enumerate(
            paragraphs
        )
        if paragraph_is_mon(paragraph)
    ]

    if not mon_indices:
        continue

    first_mon_index = min(
        mon_indices
    )

    metadata_paragraphs = (
        paragraphs[:first_mon_index]
    )

    mon_paragraphs = [
        paragraphs[i]
        for i in mon_indices
    ]

    declared_party_size = get_party_size(
        section
    )

    is_party_pool = (
        declared_party_size is not None
        and len(mon_paragraphs) > declared_party_size
    )

    if is_party_pool:
        party_pool_trainers += 1
        party_pool_members += len(
            mon_paragraphs
        )
        party_pool_runtime_slots += (
            declared_party_size
        )

        if trainer_name in boss_mega_trainer_ids:
            raise RuntimeError(
                f"{trainer_name} uses a Trainer Party Pool. A permanent "
                "Mega ace cannot be guaranteed until this custom pool is "
                "given an explicit fixed ace slot."
            )

    # If there are strange non-mon paragraphs after the party,
    # leave this trainer untouched rather than risk corruption.
    expected_indices = list(
        range(
            first_mon_index,
            first_mon_index
            + len(mon_paragraphs),
        )
    )

    if mon_indices != expected_indices:
        unusual_sections_skipped += 1
        continue

    old_party_size = len(
        mon_paragraphs
    )

    if old_party_size == 0:
        continue

    target_party_size = old_party_size

    if (
        TRAINER_FORCE_SIX_MAJOR
        and trainer_class in FORCE_SIX_CLASS_NAMES
        and not is_party_pool
    ):
        target_party_size = max(
            6,
            old_party_size,
        )

    levels = [
        get_level(paragraph)
        for paragraph in mon_paragraphs
    ]

    highest_level = max(levels)

    working_paragraphs = list(
        mon_paragraphs
    )

    # --------------------------------------------------------
    # Optionally expand Leaders / Elite Four / Champion
    # --------------------------------------------------------

    if (
        len(working_paragraphs)
        < target_party_size
    ):

        expanded_trainers += 1

        template_index = 0

        while (
            len(working_paragraphs)
            < target_party_size
        ):

            template = mon_paragraphs[
                template_index
                % len(mon_paragraphs)
            ]

            working_paragraphs.append(
                template
            )

            template_index += 1

    # --------------------------------------------------------
    # Randomize party
    # --------------------------------------------------------

    used_species = set()

    randomized_paragraphs = []

    trainer_log = []

    for mon_index, paragraph in enumerate(
        working_paragraphs
    ):

        is_extra = (
            mon_index >= old_party_size
        )

        override_level = (
            highest_level
            if is_extra
            else None
        )

        base_level = (
            override_level
            if override_level is not None
            else get_level(paragraph)
        )

        evolution_level = effective_trainer_level(
            base_level,
            trainer_class,
        )

        if (
            RIVAL_STARTER_CONTINUITY
            and is_rival_starter_slot(
                trainer_name,
                mon_index,
                len(working_paragraphs),
            )
        ):
            continuous_species = rival_starter_species_for_trainer(
                trainer_name,
                evolution_level,
                starters=RIVAL_STARTERS,
                species_blocks=species_blocks,
            )

            if continuous_species is None:
                raise RuntimeError(
                    "Could not identify the protected rival starter in "
                    f"{trainer_name}."
                )

            randomized_paragraphs.append(
                replace_paragraph_species(
                    paragraph.strip(),
                    continuous_species,
                )
            )
            used_species.add(continuous_species)
            continuous_rival_starters += 1
            trainer_log.append(
                (
                    mon_index + 1,
                    base_level,
                    continuous_species,
                    continuous_species,
                    is_extra,
                )
            )
            continue

        (
            randomized_paragraph,
            original_species,
            new_species,
            level,
        ) = randomize_mon_paragraph(
            paragraph,
            used_species,
            override_level=override_level,

            # Don't clone a held item onto newly-added
            # Leader/Elite Four/Champion slots.
            preserve_item=not is_extra,
            required_type=required_type,
            evolution_level=evolution_level,
        )

        randomized_paragraphs.append(
            randomized_paragraph
        )

        if new_species is None:
            continue

        if (
            required_type is not None
            and required_type
            not in species_types(new_species)
        ):
            raise RuntimeError(
                f"Trainer type-theme audit failed for {trainer_name}: "
                f"{new_species} does not contain {required_type}."
            )

        used_species.add(
            new_species
        )

        randomized_mons += 1

        if (
            species_category.get(
                new_species,
                "normal",
            )
            == "special"
        ):
            special_results += 1

        trainer_log.append(
            (
                mon_index + 1,
                level,
                original_species,
                new_species,
                is_extra,
            )
        )

    # --------------------------------------------------------
    # Guarantee one permanent Mega ace for later bosses.
    # --------------------------------------------------------

    if trainer_name in boss_mega_trainer_ids:
        valid_ace_indices = [
            mon_index
            for mon_index, paragraph in enumerate(randomized_paragraphs)
            if get_original_species(paragraph) is not None
        ]

        if not valid_ace_indices:
            raise RuntimeError(
                f"Could not identify a valid ace slot for {trainer_name}."
            )

        is_final_continuity_rival = (
            RIVAL_STARTER_CONTINUITY
            and FINAL_RIVAL_BATTLE_PATTERN.fullmatch(trainer_name)
            is not None
        )
        continuity_index = (
            len(randomized_paragraphs) - 1
            if is_final_continuity_rival
            else None
        )
        continuity_species = (
            get_original_species(randomized_paragraphs[continuity_index])
            if continuity_index is not None
            else None
        )
        continuity_megas = (
            direct_mega_candidates(
                continuity_species,
                required_type=required_type,
            )
            if continuity_species is not None
            else []
        )

        if continuity_megas:
            ace_index = continuity_index
            mega_species = rng.choice(sorted(continuity_megas))
            rival_starter_mega_applied_ids.add(trainer_name)
        else:
            fallback_indices = list(valid_ace_indices)

            # The rival's continuous starter must remain continuous. If it
            # has no canonical Mega form, give the permanent Mega role to a
            # different party member instead.
            if continuity_index is not None:
                fallback_indices = [
                    mon_index
                    for mon_index in fallback_indices
                    if mon_index != continuity_index
                ]

            if not fallback_indices:
                raise RuntimeError(
                    f"{trainer_name} has no non-starter slot available for "
                    "its fallback permanent Mega ace."
                )

            ace_index = max(
                fallback_indices,
                key=lambda mon_index: (
                    effective_trainer_level(
                        get_level(randomized_paragraphs[mon_index]),
                        trainer_class,
                    ),
                    mon_index,
                ),
            )

            old_fallback_species = get_original_species(
                randomized_paragraphs[ace_index]
            )
            fallback_team_species = {
                get_original_species(paragraph)
                for mon_index, paragraph in enumerate(randomized_paragraphs)
                if mon_index != ace_index
            }
            fallback_team_species.discard(None)

            mega_species = choose_boss_mega(
                old_fallback_species,
                fallback_team_species,
                required_type=required_type,
            )

            if is_final_continuity_rival:
                rival_fallback_mega_applied_ids.add(trainer_name)

        old_ace_species = get_original_species(
            randomized_paragraphs[ace_index]
        )

        if (
            required_type is not None
            and required_type not in species_types(mega_species)
        ):
            raise RuntimeError(
                f"Boss Mega type-theme audit failed for {trainer_name}: "
                f"{mega_species} does not contain {required_type}."
            )

        if species_category.get(old_ace_species) == "special":
            special_results -= 1

        if species_category.get(mega_species) == "special":
            special_results += 1

        randomized_paragraphs[ace_index] = replace_paragraph_species(
            randomized_paragraphs[ace_index],
            mega_species,
        )

        for log_index, entry in enumerate(trainer_log):
            if entry[0] == ace_index + 1:
                trainer_log[log_index] = (
                    entry[0],
                    entry[1],
                    entry[2],
                    mega_species,
                    entry[4],
                )
                break

        boss_mega_applied_ids.add(trainer_name)

    # --------------------------------------------------------
    # Rebuild trainer section
    # --------------------------------------------------------

    rebuilt_section = (
        "\n\n".join(
            metadata_paragraphs
            + randomized_paragraphs
        )
        .rstrip()
        + "\n\n"
    )

    if rebuilt_section != section:

        replacements.append(
            (
                start,
                end,
                rebuilt_section,
            )
        )

        randomized_trainers += 1

        spoiler_entries.append(
            (
                trainer_name,
                trainer_class,
                old_party_size,
                target_party_size,
                trainer_log,
            )
        )


# ============================================================
# APPLY FROM END OF FILE
# ============================================================

new_trainer_text = trainer_text


for start, end, replacement in sorted(
    replacements,
    key=lambda item: item[0],
    reverse=True,
):

    new_trainer_text = (
        new_trainer_text[:start]
        + replacement
        + new_trainer_text[end:]
    )


validate_trainer_output(
    new_trainer_text
)

TRAINERS_FILE.write_text(
    new_trainer_text,
    encoding="utf-8",
)


# ============================================================
# SUMMARY
# ============================================================

print()
print("Trainer party structure audit:")
print(
    f"  Trainer Party Pools: "
    f"{party_pool_trainers}"
)
print(
    f"  Defined pool members: "
    f"{party_pool_members}"
)
print(
    f"  Runtime party slots across pools: "
    f"{party_pool_runtime_slots}"
)
print(
    f"  Copy Pool trainers: "
    f"{copy_pool_trainers}"
)
print(
    f"  Legacy Pool:/Party Pool: metadata sections: "
    f"{legacy_pool_fields}"
)
print(
    f"  Unusual non-contiguous party sections preserved: "
    f"{unusual_sections_skipped}"
)

print()
print(
    f"Randomized trainers: "
    f"{randomized_trainers}"
)

print(
    f"Randomized Pokémon: "
    f"{randomized_mons}"
)

print(
    f"Expanded Leader/Elite Four/Champion teams: "
    f"{expanded_trainers} "
    f"(option {'on' if TRAINER_FORCE_SIX_MAJOR else 'off'})"
)

print(
    "Evolution-stage upgrade contexts: "
    f"{len(evolution_stage_upgrades)} "
    f"(option {'on' if TRAINER_EVOLUTION_STAGE_RULES else 'off'})"
)

print(
    "Protected continuous rival starter slots: "
    f"{continuous_rival_starters} "
    f"(option {'on' if RIVAL_STARTER_CONTINUITY else 'off'})"
)

if TRAINER_BOSS_PERMANENT_MEGAS:
    missing_boss_megas = (
        boss_mega_trainer_ids
        - boss_mega_applied_ids
    )

    if missing_boss_megas:
        raise RuntimeError(
            "Permanent Mega ace audit failed for: "
            + ", ".join(sorted(missing_boss_megas))
        )

    print(
        "Permanent Mega boss parties: "
        f"{len(boss_mega_applied_ids)}/"
        f"{len(boss_mega_trainer_ids)}"
    )
    print(
        "  Final rival Megas using the continuous starter: "
        f"{len(rival_starter_mega_applied_ids)}"
    )
    print(
        "  Final rival Megas using another party member: "
        f"{len(rival_fallback_mega_applied_ids)}"
    )
else:
    print("Permanent Mega boss parties: 0 (option off)")

if party_pool_trainers:
    print(
        "Trainer Party Pool members were randomized individually; "
        "Party Size, pool rules, and Tags were preserved."
    )

if copy_pool_trainers:
    print(
        "Copy Pool trainers inherit their randomized source trainer pool."
    )

if (
    not TRAINER_ALLOW_SPECIAL
    and special_results != 0
):
    raise RuntimeError(
        "Trainer special-Pokémon audit failed: "
        f"{special_results} special result(s) were produced while "
        "special Pokémon were disabled."
    )

if TRAINER_SIMILAR_BST:
    print(
        "Similar-BST candidate audit covered "
        f"{len(bst_audited_source_species)} trainer source/type contexts."
    )

if TRAINER_TYPE_THEMES:
    print(
        "Type-theme BST fallbacks: "
        f"{len(type_theme_bst_fallbacks)}"
    )

    if type_theme_bst_fallbacks:
        print(
            "  Type theme remained mandatory; when no same-type Pokémon "
            f"existed within ±{BST_TOLERANCE}, the closest BST was used."
        )

        seen_fallbacks = set()

        for (
            original_species,
            original_bst,
            required_type,
            difference,
            closest_bsts,
        ) in type_theme_bst_fallbacks:
            key = (
                original_species,
                required_type,
                original_bst,
                difference,
                closest_bsts,
            )

            if key in seen_fallbacks:
                continue

            seen_fallbacks.add(
                key
            )

            if original_bst is None:
                detail = (
                    f"{original_species}: unknown source BST -> "
                    f"{human_type(required_type)} pool"
                )
            else:
                bst_text = "/".join(
                    str(value)
                    for value in closest_bsts
                )
                detail = (
                    f"{original_species} BST {original_bst} -> "
                    f"{human_type(required_type)} closest BST "
                    f"{bst_text} (Δ{difference})"
                )

            print(
                "  " + detail
            )

            if len(seen_fallbacks) >= 20:
                remaining = (
                    len({
                        (
                            item[0],
                            item[2],
                            item[1],
                            item[3],
                            item[4],
                        )
                        for item in type_theme_bst_fallbacks
                    })
                    - len(seen_fallbacks)
                )

                if remaining > 0:
                    print(
                        f"  ... {remaining} more unique fallback context(s)"
                    )
                break

print(
    f"Special Pokémon results: "
    f"{special_results}"
)


print(
    f"Seed: {seed}"
)
