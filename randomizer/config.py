# ============================================================
# SHARED RANDOMIZER CONFIGURATION
# ============================================================

# ------------------------------------------------------------
# PROTECTED SPECIES
# ------------------------------------------------------------
#
# These Pokémon should not be directly randomized by scripts
# that respect PROTECTED_SPECIES, such as:
#
# - level-up move randomizer
# - TM compatibility randomizer
# - wild encounter replacement pools
# - gift egg pools
# - in-game trade pools
#
# Add more species here if you manually customize them.
#
# Example:
#
# PROTECTED_SPECIES = {
#     "SPECIES_SIRFETCHD",
#     "SPECIES_PIKACHU",
# }

PROTECTED_SPECIES = {

}


# ------------------------------------------------------------
# PROTECTED ABILITY FAMILIES
# ------------------------------------------------------------
#
# Key:
#   Any species belonging to the evolution family you want
#   protected.
#
# Value:
#   Ability slot 1, ability slot 2, hidden ability.
#
# The ability randomizer finds the entire connected evolution
# family automatically.
#
# This one-off branch locks each custom party family to its requested
# ability in all three slots. That makes the ability exact at creation and
# preserves it through evolution even when ability randomisation is enabled.

PROTECTED_FAMILIES = {
    "SPECIES_GOLETT": (
        "ABILITY_IRON_FIST",
        "ABILITY_IRON_FIST",
        "ABILITY_IRON_FIST",
    ),
    "SPECIES_KLEAVOR": (
        "ABILITY_SHARPNESS",
        "ABILITY_SHARPNESS",
        "ABILITY_SHARPNESS",
    ),
    "SPECIES_TYRUNT": (
        "ABILITY_STRONG_JAW",
        "ABILITY_STRONG_JAW",
        "ABILITY_STRONG_JAW",
    ),
    "SPECIES_MINCCINO": (
        "ABILITY_SKILL_LINK",
        "ABILITY_SKILL_LINK",
        "ABILITY_SKILL_LINK",
    ),
    "SPECIES_CLAUNCHER": (
        "ABILITY_MEGA_LAUNCHER",
        "ABILITY_MEGA_LAUNCHER",
        "ABILITY_MEGA_LAUNCHER",
    ),
    "SPECIES_TOXEL": (
        "ABILITY_PUNK_ROCK",
        "ABILITY_PUNK_ROCK",
        "ABILITY_PUNK_ROCK",
    ),
}


# ============================================================
# STARTER CONFIGURATION
# ============================================================
#
# Available modes:
#
# "one_fixed"
#     Keep the starter slots listed in FIXED_STARTERS and
#     randomize every other slot.
#
# "random"
#     Ignore FIXED_STARTERS and randomize all three starters.
#
# "fixed"
#     Use exactly the Pokémon in FIXED_STARTERS.
#     All three slots must be specified.
#
# With STARTER_MODE = "one_fixed", slots omitted from FIXED_STARTERS
# are randomized. An empty FIXED_STARTERS therefore randomizes all three.

STARTER_MODE = "one_fixed"


# Starter slot numbers:
# 0 = first starter  (currently GRASS_STARTER)
# 1 = second starter (currently FIRE_STARTER)
# 2 = third starter  (currently WATER_STARTER)

FIXED_STARTERS = {
}


# ------------------------------------------------------------
# SPECIAL STARTERS
# ------------------------------------------------------------
#
# False:
#   Random starter slots cannot contain:
#   - Restricted Legendaries
#   - Sub-Legendaries
#   - Mythicals
#   - Ultra Beasts
#   - Paradox Pokémon
#
# True:
#   All of the above may appear as random starters.

ALLOW_SPECIAL_STARTERS = True


# ------------------------------------------------------------
# STARTER EVOLUTION STAGE
# ------------------------------------------------------------
#
# True:
#   Random starters must have no pre-evolution.
#
#   Examples:
#       Bulbasaur
#       Ralts
#       Gible
#       Riolu
#
#   rather than:
#       Venusaur
#       Gardevoir
#       Garchomp
#
# False:
#   Any eligible species can become a starter.

BASE_STAGE_STARTERS_ONLY = False
