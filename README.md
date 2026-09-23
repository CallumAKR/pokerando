# PokéRando

[![Runtime randomisation](https://github.com/CallumAKR/pokerando/actions/workflows/runtime-randomisation.yml/badge.svg)](https://github.com/CallumAKR/pokerando/actions/workflows/runtime-randomisation.yml)

PokéRando is a graphical Pokémon Emerald randomiser built on
[`pokeemerald-expansion`](https://github.com/rh-hideout/pokeemerald-expansion).
It creates a playable GBA ROM containing the options selected in the GUI.

Unlike a traditional randomiser, most selected systems are not permanently
rolled while the ROM is being built. The GUI choices become rules inside the
ROM, and **each New Game creates a different randomised world**. That world then
remains consistent for the life of that save.

> [!IMPORTANT]
> This repository does not distribute a prebuilt Pokémon ROM. The project is
> intended for personal use with legally obtained game material. You are
> responsible for following the laws that apply where you live.

## How runtime randomisation works

The GUI seed defines the ROM's randomisation identity. When a New Game is
started, the ROM combines that identity with the new save's identity to create
its randomised world.

- Starting another New Game on the same ROM produces a new result.
- A save's starters, encounters, mappings and other rolls stay stable after
  they have been generated.
- The restrictions chosen in the GUI—such as similar BST, preserving special
  Pokémon status or using a particular mapping mode—are enforced on every new
  save made with that ROM.
- Changing the ROM's enabled options still requires building another ROM.

For example, one save might encounter a Charmander with Sap Sipper while a new
save made from the same ROM might give Charmander Vessel of Ruin instead.

## Quick start: packaged Windows version

The packaged Windows version contains its own build tools. Python, Git, WSL,
MSYS2 and devkitARM do not need to be installed.

1. Extract the entire `PokemonEmeraldRandomizer` folder. Do not run the program
   from inside the ZIP file.
2. Double-click `Randomizer.exe`.
3. Enter a seed or click **Random Seed**.
4. Select the randomisation, game and difficulty options you want.
5. Leave **Enable ROM build after randomisation** selected.
6. Click **RANDOMISE** and wait for the build to finish.
7. Find the finished ROM in `output\` as
   `Pokemon Emerald Randomized - <seed>.gba`.

The output panel shows progress and the location of the full build log. A clean
rebuild is normally unnecessary; use it only when troubleshooting an
incremental build.

## What can be randomised?

### Pokémon data

- Types
- Base stats, either preserving total BST, using evolution-stage ranges or
  using the full configured range
- Abilities
- Evolution targets
- Level-up moves and move types
- TM, HM and move-tutor compatibility
- Evolution-required moves for the move relearner

Species- or form-dependent abilities that cannot work correctly on arbitrary
Pokémon are excluded from the random pool. Z-Moves, Max Moves and G-Max Moves
are also excluded from ordinary learnsets. Supported formerly species-locked
moves such as Hyperspace Fury can be used by any Pokémon that receives them.

### Encounters and gifts

- Starters, with optional three-stage lines and rival continuity
- Wild encounters
- Trainer parties
- Static and legendary encounters
- Fossil revivals
- Gift Eggs
- NPC trades
- Field items and eligible NPC gifts

Item randomisation turns berry trees and empty berry plots into item balls.
Progression items and Z-Crystals are excluded, and Mom's optional 99 Ultra
Balls are never randomised.

### Mapping and restriction modes

- **One-to-one mapping:** an original species has one consistent replacement.
- **Encounter slots:** every encounter-table slot receives its own replacement.
- **Route-local mapping:** repeated species match within a route and encounter
  method, but may map differently elsewhere.
- **Fully random trainers/statics:** individual Pokémon can be replaced
  independently.
- **Similar BST:** restricts wild or trainer replacements to the configured BST
  tolerance.
- **Special status rules:** either preserve Legendary, Mythical, Ultra Beast
  and Paradox-style status or allow the full eligible pool.
- **Type themes:** gives each Hoenn Gym and Elite Four member a randomised type
  theme.

## Optional game features

The GUI also includes independent gameplay and quality-of-life options:

- Permanent Mega Evolutions that retain their Mega species, sprite, stats,
  type and ability while holding a different item
- Permanent Mega aces for later bosses
- Hard badge/story level caps and a reusable **Level to cap** party action
- Wild Pokémon clamped to the current level cap when caps are enabled
- Trade-evolution replacements and regional evolution postcards
- HM field actions without teaching the moves, with optional progression
  bypasses
- Perma Repel, Party Restorer, Time Turner and Weather Setter tools
- Guaranteed captures, forced shinies and permanent-death rules
- Mom's Running Shoes bonus of 99 Ultra Balls and maximum money
- Optional intro skip from the moving van directly to Birch's starter bag
- Expanded Bag capacity
- Mirage Island and event-island access options
- Lilycove catalogues for TMs, evolution items, regional postcards and Mega
  Stones

Difficulty options include smarter trainer AI, level increases, evolution-stage
rules, scaled or perfect IVs, competitive EVs and natures, improved movesets,
held items, healing items, forced Set mode and disabling the Bag in trainer
battles.

## Manual customisation

The **Manual Customisation** tab can protect or configure individual Pokémon
instead of applying every global randomisation rule to them. Manual starter
selection is also available. These choices are compiled into the generated ROM
alongside the global options.

## Running from source

### Prerequisites

Running PokéRando directly from source requires:

- **Python 3** with Tkinter support.
- **The pokeemerald-expansion build toolchain.** On native Windows, the
  simplest supported setup is **devkitPro with devkitARM**, including the
  MSYS2 tools supplied by devkitPro. GNU Make must be available on `PATH`.
- On Linux or WSL2, install the normal `pokeemerald-expansion` build
  dependencies instead.

The upstream build instructions are retained in [`INSTALL.md`](INSTALL.md).
Linux or WSL2 is the recommended development environment, but native Windows
works with devkitPro/devkitARM.

After installing the prerequisites, clone the repository and launch the GUI:

```bash
git clone https://github.com/CallumAKR/pokerando.git
cd pokerando
python3 randomizer/gui.py
```

On Windows, `python randomizer/gui.py` can be used if `python3` is not the
registered command. The GUI uses Tkinter; on Linux distributions that package
it separately, install the appropriate `python3-tk` package.

> [!NOTE]
> These prerequisites apply only when running PokéRando from source. The
> packaged Windows release contains its own Python runtime and build toolchain,
> so users of `Randomizer.exe` do not need to install Python, devkitPro,
> devkitARM, MSYS2 or GNU Make separately.

An advanced command-line interface is also available:

```bash
python3 randomizer/master_randomizer.py --help
```

## Troubleshooting

- **The build prints an RWX permissions warning:** this linker warning is
  expected for this GBA project and does not mean the build failed.
- **The memory table looks high:** EWRAM, IWRAM and ROM are the Game Boy
  Advance's memory regions, not your computer's RAM. A build fails if one of
  those fixed limits is exceeded.
- **A build fails after source changes:** try the GUI's clean rebuild option
  once, then read the first actual error above the final Python traceback.
- **A JSON file becomes truncated in a cloud-synchronised folder:** restore the
  file with Git or move the project to a normal local folder before rebuilding.
- **A new game does not use new settings:** GUI settings are compiled into the
  ROM. Rebuild the ROM after changing them, then start a New Game.

When reporting a problem, include the selected options, seed and the relevant
part of `build_last.log`. Do not upload copyrighted ROM files.

## Testing

The runtime-randomisation workflow runs focused Python regression tests and
compiles the changed runtime sources through the project's ARM preprocessing
pipeline. It also checks the GBA save-block size limits used by features such
as the expanded Bag.

## Credits

PokéRando is based on **RHH's pokeemerald-expansion 1.16.3**, itself built on
[pret's `pokeemerald`](https://github.com/pret/pokeemerald) decompilation.

Please retain credit for the original projects and their contributors. See
[`CREDITS.md`](CREDITS.md) for the full inherited credits.

Pokémon and all related names are trademarks of Nintendo, Game Freak and The
Pokémon Company. This is an unofficial fan project and is not affiliated with
or endorsed by them.
