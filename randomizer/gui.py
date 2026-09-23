#!/usr/bin/env python3

import contextlib
import io
import queue
import random
import threading
import traceback
import tkinter as tk

from datetime import datetime
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

from event_island_access import configure_event_island_access
from fossil_options import configure_fossil_options
from trainer_difficulty_options import configure_trainer_difficulty_options
from rival_starter_continuity import configure_rival_starter_continuity
import master_randomizer
from manual_customization import customization_summary
from manual_customization_ui import ManualCustomizationPanel
from runtime_paths import OUTPUT_DIR
from tm_catalog_data import FIRST_TM_CATALOG, TM_CATALOGS
from starter_helpers import (
    discover_selectable_starters,
    find_front_sprite,
    read_default_starters,
)
from wild_runtime_patch import (
    BST_TOLERANCE,
)


# Keep the master controller's nested run summary consistent without replacing
# the user's newer master_randomizer.py merely to change one display label.
master_randomizer.COMPONENT_LABELS[
    "tms"
] = "TM/HM and move tutor compatibility"


COMPONENTS = [
    ("pokemon_types", "Pokémon type randomisation"),
    ("pokemon_bst", "Pokémon base-stat randomisation"),
    ("abilities", "Ability randomisation"),
    ("evolutions", "Evolution randomisation"),
    ("move_types", "Move type randomisation"),
    ("moves", "Level-up move randomisation"),
    ("evolution_moves", "Evolution-required move relearning"),
    ("tms", "TM/HM and move tutor compatibility randomisation"),
    ("trade_evos", "Trade evolution changes"),
    ("trades", "NPC trade randomisation"),
    ("wild", "Wild encounter randomisation"),
    ("statics", "Static encounter randomisation"),
    ("eggs", "Gift egg randomisation"),
    ("starters", "Starter randomisation"),
    ("trainers", "Trainer Pokémon randomisation"),
    ("items", "Item randomisation"),
]

COMPONENT_OPTION_LABELS = {
    "pokemon_types": "Enable Pokémon type randomisation",
    "pokemon_bst": "Enable Pokémon base-stat randomisation",
    "abilities": "Enable ability randomisation",
    "evolutions": "Enable evolution randomisation",
    "move_types": "Enable move type randomisation",
    "moves": "Enable level-up move randomisation",
    "evolution_moves": "Enable evolution-required move relearning",
    "tms": "Enable TM/HM and move tutor compatibility randomisation",
    "trade_evos": "Enable trade evolution changes",
    "trades": "Enable NPC trade randomisation",
    "wild": "Enable wild encounter randomisation",
    "statics": "Enable static encounter randomisation",
    "eggs": "Enable gift egg randomisation",
    "starters": "Enable starter randomisation",
    "trainers": "Enable trainer Pokémon randomisation",
    "items": "Enable item randomisation",
}


OPTION_HELP = {
    "pokemon_types": (
        "Randomises each Pokémon's type while preserving whether it is "
        "effectively mono- or dual-type. This runs before level-up move "
        "randomisation and trainer type themes, so those systems use the "
        "randomised Pokémon types."
    ),
    "pokemon_bst": (
        "Randomises Pokémon base stats. Choose one required mode below. "
        "Every randomised stat is at least 10% and at most 50% of that "
        "Pokémon's total BST, with the engine's 255 stat cap."
    ),
    "pokemon_bst_same": (
        "Keeps the Pokémon's original total BST exactly the same and only "
        "redistributes that total across its six base stats. Mega species "
        "participate and keep their own original Mega BST."
    ),
    "pokemon_bst_stages": (
        "Randomises both BST and stat distribution using sensible ranges for "
        "base, middle and final evolution stages. Direct evolutions gain at "
        "least 25 BST. Each Mega receives exactly 100 more BST than its "
        "current randomised base form."
    ),
    "pokemon_bst_full": (
        "Randomises both BST and stat distribution across the full natural "
        "BST range without protecting evolution-stage progression. Each Mega "
        "receives exactly 100 more BST than its current randomised base form."
    ),
    "abilities": (
        "Randomises Pokémon abilities."
    ),
    "evolutions": (
        "Randomises evolution targets while preserving each evolution method "
        "and condition. Every changed evolution must increase BST, and targets "
        "near the original evolution's BST are preferred."
    ),
    "evolution_moves": (
        "Makes every move named by a Pokémon's evolution condition available "
        "to that Pokémon through the move relearner as a level-0 move. This "
        "runs after move-type and level-up-move randomisation, includes "
        "White-Striped Basculin's Take Down recoil option, and automatically "
        "uses a move of the current required type for conditions such as "
        "Eevee's Fairy-type evolution requirement."
    ),
    "regional_evolution_postcards": (
        "Lets a held Alola, Galar or Hisui Postcard satisfy evolution "
        "requirements for that otherwise unavailable region. The original "
        "level, move, item and time requirements still apply. With a Hisui "
        "Postcard, using a Peat Block on Ursaring produces regular Ursaluna "
        "outside night and Bloodmoon Ursaluna at night. Postcards are reusable."
    ),
    "move_types": (
        "Randomises the elemental type of moves. This runs before Pokémon "
        "level-up move randomisation, so same-type/STAB bias uses the "
        "randomised move types."
    ),
    "moves": (
        "Randomises Pokémon level-up learnsets. By default moves are chosen "
        "uniformly from the full usable move list."
    ),
    "moves_species_specific": (
        "Restricts each randomised learnset to moves from that Pokémon "
        "species' own learnable-move pool. The pool follows the species itself, "
        "not its randomised evolution chain."
    ),
    "moves_same_type_bias": (
        "Makes moves matching the Pokémon's own type twice as likely when "
        "choosing randomised level-up moves. This is optional and defaults off."
    ),
    "tms": (
        "Randomises which Pokémon are compatible with every currently "
        "configured TM/HM and every move available from an in-game move "
        "tutor. Each Pokémon keeps at least the same total number of distinct "
        "teachable moves; evolved Pokémon may gain extra compatibility to "
        "retain their randomised pre-evolutions' moves. Same-type moves are "
        "favoured."
    ),
    "trade_evos": (
        "Changes trade-only evolution requirements so those Pokémon can "
        "evolve without needing to trade."
    ),
    "trades": (
        "Randomises the Pokémon offered and requested by in-game NPC trades."
    ),
    "game_permadeath": (
        "Enables the permanent-death system already built into this project. "
        "A Pokémon marked dead remains unusable and the custom Party Restorer "
        "will not revive it."
    ),
    "game_hm_free": (
        "Makes Cut, Rock Smash, Strength, Surf, Dive, Waterfall and Rock "
        "Climb work by interacting with the appropriate object or terrain, "
        "without teaching the move or adding it to a Pokémon's menu. It also "
        "gives the Fly, Flash, Dig and Teleport field tools. Badge/story "
        "requirements still apply unless their separate option is enabled."
    ),
    "game_hm_progression_bypass": (
        "Removes badge and configured progression requirements from HM field "
        "actions and field tools. This works with either normally learned HMs "
        "or the HM-free field interaction option."
    ),
    "game_receive_items": (
        "Enables the individual key item choices below. Each item is optional and "
        "defaults off."
    ),
    "game_perma_repel": (
        "Gives the existing Perma Repel key item on a new game. It toggles "
        "ordinary wild encounters off or back on indefinitely."
    ),
    "game_cap_candy": (
        "Adds Level to cap beside Summary in a Pokémon's field party menu. "
        "It raises a living Pokémon to the current cap, including its skipped "
        "level-up moves and evolution check. When level caps are off, the "
        "cap is level 100. No Cap Candy item is given."
    ),
    "game_mom_bonus": (
        "When Mom gives you the Running Shoes, she also gives you 99 Ultra "
        "Balls and enough money to reach the ₽999,999 limit. It happens once "
        "on a new game and is independent of item randomisation."
    ),
    "game_skip_intro": (
        "Keeps the moving-van exit, then skips Mom's welcome, setting the "
        "clock, the TV report, visiting the neighbour and the Route 101 help "
        "cutscene. You can walk directly to Professor Birch's bag and choose "
        "a starter. Later story events continue normally."
    ),
    "game_party_heal": (
        "Gives the existing Party Restorer key item on a new game. It fully "
        "heals living party Pokémon without reviving permanently dead ones."
    ),
    "game_time_turner": (
        "Gives the reusable Time Turner key item on a new game. It lets the "
        "player set the apparent time to Day, Evening or Night for evolutions, "
        "encounters, lighting and other time-of-day checks."
    ),
    "game_weather_setter": (
        "Gives the reusable Weather Setter key item on a new game. It offers "
        "a scrollable list of safe concrete overworld weather types for the "
        "player's current location."
    ),
    "game_always_catch": (
        "Makes a valid Poké Ball throw against a catchable wild Pokémon "
        "guarantee the capture."
    ),
    "game_force_shiny": (
        "Makes every Pokémon report as shiny, so shiny palettes/effects are "
        "used throughout the game."
    ),
    "game_permanent_megas": (
        "Turns every Mega Stone into a consumable party-menu evolution item. "
        "Using the correct stone permanently changes that Pokémon into its "
        "existing Mega species, using that species' current sprite, stats, "
        "types and ability. Stone-to-Mega pairings are never shuffled by "
        "evolution randomisation, while BST randomisation does affect Mega "
        "stats according to its selected mode. Permanent Megas do not revert "
        "after battle and can hold other items. Rayquaza keeps its existing "
        "Dragon Ascent battle transformation because it does not use a Mega "
        "Stone."
    ),
    "game_level_caps": (
        "Enables the hard badge/story level caps already configured in this "
        "project. Pokémon at the current cap stop gaining experience until "
        "the next milestone. When this option is off, normal Emerald "
        "levelling and Rare Candy behaviour are restored."
    ),
    "game_always_mirage_island": (
        "Makes Mirage Island remain visible on Route 130 every day. The "
        "existing island layout, Wynaut encounters, Liechi Berry tree and "
        "Pacifidlog watcher all use the normal game systems. When this option "
        "is off, Mirage Island returns to its standard daily personality-value "
        "check."
    ),
    "game_event_island_access": (
        "After the Hall of Fame, makes the Lilycove ferry attendant give any "
        "missing Eon Ticket, Aurora Ticket, Mystic Ticket and Old Sea Map, "
        "and enables their ferry destinations. Existing passes are not "
        "duplicated, and no event Pokémon is marked encountered, defeated or "
        "caught. When this option is off, normal Emerald event access is kept."
    ),
    "starter_random": (
        "Randomly replaces the three starter Pokémon for each New Game. "
        "The choices stay fixed for that save."
    ),
    "starter_three_stage": (
        "Restricts random starters to base Pokémon that can evolve twice, "
        "giving them a three-stage evolution path such as base → middle → final."
    ),
    "starter_manual": (
        "Lets you choose the three starter Pokémon yourself."
    ),
    "starter_rival_continuity": (
        "Keeps May's or Brendan's starter tied to the player's chosen bag "
        "slot throughout all five rival encounters. The normal Emerald slot "
        "cycle is preserved: leaf gives the rival fire, fire gives the rival "
        "water, and water gives the rival leaf. The rival's Pokémon follows "
        "permanent level evolutions at their exact thresholds using the "
        "current evolution tree, including randomised targets when evolution "
        "randomisation is enabled. Ordinary trainer randomisation cannot "
        "replace this one party slot."
    ),
    "starter_dropdown": (
        "Choose the exact Pokémon for this starter slot. Pokémon are listed "
        "in National Pokédex order, with forms grouped beside their base species."
    ),
    "wild": (
        "Randomises Pokémon found in normal wild encounter tables such as "
        "grass, caves, surfing and fishing."
    ),
    "wild_mapping": (
        "Creates one consistent replacement for each species. If a species "
        "is mapped to another species, that same replacement is used wherever "
        "the original appears in wild encounter tables."
    ),
    "wild_slots": (
        "Randomises every encounter-table slot independently for each New "
        "Game. Each route keeps those slots for the life of that save."
    ),
    "wild_runtime": (
        "Creates a separate species mapping for each route and encounter "
        "method. Repeated copies of a species on that route match, but the "
        "same original species may map differently elsewhere. The mapping is "
        "generated at New Game and remains fixed for that save."
    ),
    "wild_allow_special": (
        "Allows Legendary, Mythical, Ultra Beast and Paradox Pokémon to appear "
        "as wild replacement species."
    ),
    "wild_similar_bst": (
        f"Limits wild replacements to Pokémon within ±{BST_TOLERANCE} total "
        "base-stat points of the original species. If none qualify, the "
        "original stays unchanged."
    ),
    "statics": (
        "Randomises scripted/static Pokémon encounters such as legendary "
        "encounters, the television roamer and other Pokémon placed directly "
        "in event scripts. Root and Claw fossil revivals are included; when "
        "all fossil revivals are enabled, every revived fossil Pokémon is "
        "included."
    ),
    "static_preserve": (
        "Keeps encounter status broadly similar: legendary, mythical, "
        "Ultra Beast and Paradox-style special encounters are replaced from "
        "the special pool, while ordinary static encounters stay ordinary."
    ),
    "static_full": (
        "Randomises each static encounter from the full eligible Pokémon pool. "
        "A legendary can become an ordinary Pokémon, and an ordinary static "
        "encounter can become a legendary or other special Pokémon."
    ),
    "eggs": (
        "Randomises Pokémon received as scripted gift eggs."
    ),
    "trainers": (
        "Randomises which Pokémon NPC trainers use. Replacement Pokémon use "
        "their current species move and ability data rather than random moves "
        "or abilities generated by this option."
    ),
    "trainer_mapping": (
        "Creates one consistent replacement for each trainer species. "
        "The same original species maps to the same replacement everywhere."
    ),
    "trainer_full": (
        "Randomises each individual trainer Pokémon independently instead of "
        "using one consistent species mapping."
    ),
    "trainer_similar_bst": (
        f"Limits trainer replacements to Pokémon within ±{BST_TOLERANCE} total "
        "base-stat points of the original species."
    ),
    "trainer_allow_special": (
        "Allows Legendary, Mythical, Ultra Beast and Paradox Pokémon to appear "
        "as trainer replacement species. When off, those species are excluded."
    ),
    "trainer_force_six_major": (
        "Expands standard Gym Leader, Elite Four and Champion parties to six "
        "Pokémon. When off, their original party sizes are preserved."
    ),
    "trainer_type_themes": (
        "Gives each Hoenn Gym a randomised type shared by every trainer in "
        "that Gym and its Leader, and gives each Elite Four member their own "
        "randomised type. Dual-type Pokémon qualify if either type matches. "
        "When combined with similar BST, the type is mandatory; if no Pokémon "
        "of that type exists within the BST range, the closest-BST valid "
        "Pokémon of the required type is used."
    ),
    "difficulty_ai": (
        "Upgrades every trainer's decision-making. Fair smart AI uses move "
        "viability, KO planning, switching and informed predictions without "
        "reading the player's hidden moves or held item. Omniscient AI has "
        "full hidden-information knowledge."
    ),
    "difficulty_level_boost": (
        "Adds the selected number of levels after trainer Pokémon species are "
        "finalised. Levels are capped at 100. This does not alter any "
        "Pokémon's base stats."
    ),
    "difficulty_evolution_stage": (
        "For trainer Pokémon at an effective final level of 30 or above, "
        "follows the current evolution tree as far as that level permits. "
        "This runs after evolution randomisation, so it uses the randomised "
        "tree. Numeric level requirements remain exact; item, trade and other "
        "non-level evolutions become eligible from level 30. Temporary battle "
        "forms are excluded, and trainer type themes plus the special-Pokémon "
        "setting remain mandatory."
    ),
    "difficulty_boss_mega": (
        "Gives one permanent Mega ace to every Gym 5–8 Leader, Elite Four "
        "member, Champion party and the final Lilycove rival battle. The "
        "Mega species is rerolled for each New Game while the ace slot stays "
        "permanently Mega. The "
        "rival's continuous starter becomes its canonical Mega whenever it "
        "has one; otherwise another party member becomes a suitable Mega. It "
        "requires both trainer Pokémon randomisation and Permanent Mega "
        "Evolutions. The Mega respects any trainer type theme and the "
        "special-Pokémon and similar-BST settings."
    ),
    "difficulty_iv": (
        "Changes trainer-only IVs. Scaled IVs rise from 5 early in the game "
        "to 31 late in the game, with major trainers receiving at least 20. "
        "Perfect IVs sets all six IVs to 31."
    ),
    "difficulty_competitive_builds": (
        "Gives Gym Leaders, rivals, Elite Four and Champion Pokémon EV "
        "spreads and natures chosen from their finalised randomised stat "
        "distributions. Their strongest currently legal ability is also "
        "selected."
    ),
    "difficulty_movesets": (
        "Generates up to four legal, role-appropriate moves for every trainer "
        "Pokémon after move types, level-up moves and teachable-move "
        "compatibility have finished randomising. It favours current STAB, "
        "suitable physical or special attacks, coverage and useful "
        "setup/status moves."
    ),
    "difficulty_held_items": (
        "Gives Gym Leader, rival, Elite Four and Champion Pokémon held items "
        "selected after their finalised role and moveset are known."
    ),
    "difficulty_trainer_items": (
        "Gives Gym Leaders, rivals, Elite Four and the Champion suitable "
        "healing items to use during battle."
    ),
    "difficulty_force_set": (
        "Forces Set battle style in trainer battles, preventing the free "
        "switch prompt after an opposing Pokémon faints."
    ),
    "difficulty_disable_bag": (
        "Prevents the player from using Bag items during trainer battles. "
        "Held items still function and the Bag remains normal outside those "
        "battles."
    ),
    "items": (
        "Randomises eligible found items and safe NPC/script rewards while "
        "leaving progression-critical items protected."
    ),
    "game_corner": (
        "Also includes recognised Game Corner reward Pokémon/items in the "
        "item randomisation. This is optional and only applies when item "
        "randomisation is enabled."
    ),
    "all_fossils": (
        "Lets the Devon researcher revive every fossil item. When item "
        "randomisation is enabled, all fossil items can enter its replacement "
        "pool, so any fossil received can be used. Each Galar fossil piece "
        "works alone: Bird gives Dracozolt, Dino gives Arctozolt, Drake gives "
        "Dracovish and Fish gives Arctovish. This option does not control the "
        "Pokémon replacement pool for fossil revivals."
    ),
    "fossil_only_replacements": (
        "When static encounter randomisation is enabled, every Pokémon "
        "produced by fossil revival is selected only from the fossil-Pokémon "
        "pool. This does not affect fossil item rewards and does not require "
        "all fossil revivals to be enabled."
    ),
    "tm_shop": (
        "Adds one representative main-series TM catalogue to Lilycove 4F. "
        "Choose exactly one generation below; only valid TMs from that "
        "catalogue are added."
    ),
    "evolution_shop": (
        "Adds all evolution items to the Lilycove Department Store."
    ),
    "regional_postcard_shop": (
        "Adds the reusable Alola, Galar and Hisui evolution postcards to "
        "the Lilycove Department Store."
    ),
    "mega_shop": (
        "Adds all Mega Stones to the Lilycove Department Store."
    ),
    "build": (
        "Builds a playable ROM automatically after the selected randomisers "
        "finish. Turn this off if you only want to modify the source files."
    ),
    "clean_build": (
        "Deletes/rebuilds generated build output before compiling. This is "
        "much slower and should normally only be used to troubleshoot a bad "
        "incremental build."
    ),
}


class HoverHelp:
    """
    Delayed tooltip opened only from its dedicated help icon.

    Moving from the icon onto the tooltip keeps the tooltip open.
    It closes only after the pointer leaves both areas.
    """

    def __init__(
        self,
        widget,
        text,
        *,
        delay_ms=700,
        leave_delay_ms=220,
    ):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.leave_delay_ms = leave_delay_ms

        self.after_id = None
        self.hide_id = None
        self.tip_window = None
        self.tip_label = None

        self.widget.bind(
            "<Enter>",
            self._source_enter,
            add="+",
        )
        self.widget.bind(
            "<Leave>",
            self._source_leave,
            add="+",
        )

    def _source_enter(
        self,
        _event=None,
    ):
        self._cancel_hide()
        self._cancel_show()

        if self.tip_window is None:
            self.after_id = self.widget.after(
                self.delay_ms,
                self._show,
            )

    def _source_leave(
        self,
        _event=None,
    ):
        self._cancel_show()
        self._schedule_hide()

    def _tooltip_enter(
        self,
        _event=None,
    ):
        # The user has moved from the ? icon onto the help text.
        # Keep the popup alive indefinitely while they are reading it.
        self._cancel_hide()

    def _tooltip_leave(
        self,
        _event=None,
    ):
        self._schedule_hide()

    def _schedule_hide(self):
        self._cancel_hide()

        self.hide_id = self.widget.after(
            self.leave_delay_ms,
            self._hide_if_pointer_outside,
        )

    def _pointer_is_over(
        self,
        target,
    ):
        if target is None:
            return False

        try:
            x = self.widget.winfo_pointerx()
            y = self.widget.winfo_pointery()

            left = target.winfo_rootx()
            top = target.winfo_rooty()
            right = left + target.winfo_width()
            bottom = top + target.winfo_height()

            return (
                left <= x < right
                and top <= y < bottom
            )
        except tk.TclError:
            return False

    def _hide_if_pointer_outside(self):
        self.hide_id = None

        if self._pointer_is_over(
            self.widget
        ):
            return

        if self._pointer_is_over(
            self.tip_window
        ):
            return

        self._hide()

    def _cancel_show(self):
        if self.after_id is not None:
            try:
                self.widget.after_cancel(
                    self.after_id
                )
            except tk.TclError:
                pass

            self.after_id = None

    def _cancel_hide(self):
        if self.hide_id is not None:
            try:
                self.widget.after_cancel(
                    self.hide_id
                )
            except tk.TclError:
                pass

            self.hide_id = None

    def _show(self):
        self.after_id = None

        if self.tip_window is not None:
            return

        try:
            x = self.widget.winfo_pointerx() + 14
            y = self.widget.winfo_pointery() + 16
        except tk.TclError:
            return

        tip = tk.Toplevel(
            self.widget
        )
        tip.wm_overrideredirect(
            True
        )
        tip.wm_geometry(
            f"+{x}+{y}"
        )

        label = tk.Label(
            tip,
            text=self.text,
            justify="left",
            background="#fffbe6",
            foreground="#111111",
            relief="solid",
            borderwidth=1,
            padx=8,
            pady=6,
            wraplength=380,
            font=("TkDefaultFont", 9),
            cursor="arrow",
        )
        label.pack()

        # Both the toplevel and the text label participate in hover state.
        for target in (
            tip,
            label,
        ):
            target.bind(
                "<Enter>",
                self._tooltip_enter,
                add="+",
            )
            target.bind(
                "<Leave>",
                self._tooltip_leave,
                add="+",
            )

        self.tip_window = tip
        self.tip_label = label

    def _hide(
        self,
        _event=None,
    ):
        self._cancel_show()
        self._cancel_hide()

        if self.tip_window is not None:
            try:
                self.tip_window.destroy()
            except tk.TclError:
                pass

        self.tip_window = None
        self.tip_label = None


class HelpIcon(tk.Canvas):
    """
    Small blue circular ? icon used as the sole tooltip hover target.
    """

    def __init__(
        self,
        parent,
        text,
    ):
        background = parent.cget("bg")

        super().__init__(
            parent,
            width=16,
            height=16,
            bg=background,
            bd=0,
            highlightthickness=0,
            cursor="question_arrow",
        )

        self.create_oval(
            1,
            1,
            15,
            15,
            fill="#2f6fda",
            outline="#2f6fda",
        )
        self.create_text(
            8,
            8,
            text="?",
            fill="white",
            font=("TkDefaultFont", 8, "bold"),
        )

        self.hover_help = HoverHelp(
            self,
            text,
        )



class QueueWriter(io.TextIOBase):
    def __init__(self, q, logfile):
        self.q = q
        self.logfile = logfile
        self.lock = threading.Lock()

    def write(self, text):
        if not text:
            return 0

        with self.lock:
            self.q.put(("output", text))
            try:
                self.logfile.write(text)
                self.logfile.flush()
            except Exception:
                pass

        return len(text)

    def flush(self):
        try:
            self.logfile.flush()
        except Exception:
            pass


class FilledIndicatorOption(tk.Frame):
    """
    Option selector with a deliberately simple visual hierarchy.

    shape="square"
        Top-level option. Selected state is a filled square.

    shape="circle"
        Sub-option. Selected state is a filled circle.

    Boolean variables toggle on/off. For StringVar radio-style groups,
    pass `value=...`; clicking the selected value leaves it selected.
    """

    def __init__(
        self,
        parent,
        *,
        text,
        variable,
        shape="square",
        value=None,
        command=None,
        tooltip=None,
    ):
        background = parent.cget("bg")

        super().__init__(
            parent,
            bg=background,
            cursor="hand2",
        )

        if shape not in {
            "square",
            "circle",
        }:
            raise ValueError(
                f"Unsupported indicator shape: {shape}"
            )

        self.variable = variable
        self.shape = shape
        self.value = value
        self.command = command
        self.option_state = "normal"
        self.background = background

        self.indicator = tk.Canvas(
            self,
            width=18,
            height=18,
            bg=background,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.indicator.pack(
            side="left",
        )

        self.text_label = tk.Label(
            self,
            text=text,
            bg=background,
            anchor="w",
            cursor="hand2",
        )
        self.text_label.pack(
            side="left",
            padx=(4, 0),
        )

        for widget in (
            self,
            self.indicator,
            self.text_label,
        ):
            widget.bind(
                "<Button-1>",
                self._activate,
            )

        self.variable.trace_add(
            "write",
            self._variable_changed,
        )

        self._redraw()

        self.help_icon = None

        if tooltip:
            self.help_icon = HelpIcon(
                self,
                tooltip,
            )
            self.help_icon.pack(
                side="left",
                padx=(6, 0),
            )

    def _is_selected(self):
        if self.value is None:
            return bool(
                self.variable.get()
            )

        return (
            self.variable.get()
            == self.value
        )

    def _activate(self, _event=None):
        if self.option_state == "disabled":
            return

        if self.value is None:
            self.variable.set(
                not bool(
                    self.variable.get()
                )
            )
        else:
            self.variable.set(
                self.value
            )

        if self.command is not None:
            self.command()

    def _variable_changed(
        self,
        *_args,
    ):
        self._redraw()

    def set_state(self, state):
        if state not in {
            "normal",
            "disabled",
        }:
            raise ValueError(
                f"Unsupported option state: {state}"
            )

        self.option_state = state

        cursor = (
            "hand2"
            if state == "normal"
            else "arrow"
        )

        self.configure(
            cursor=cursor
        )
        self.indicator.configure(
            cursor=cursor
        )
        self.text_label.configure(
            cursor=cursor
        )

        self._redraw()

    def _redraw(self):
        selected = self._is_selected()

        if self.option_state == "disabled":
            outline = "#8a8a8a"
            foreground = "#8a8a8a"
        else:
            outline = "#000000"
            foreground = "#000000"

        self.indicator.delete(
            "all"
        )

        if self.shape == "square":
            # Compact top-level style:
            # small outlined square + inset filled square.
            self.indicator.create_rectangle(
                4,
                4,
                14,
                14,
                outline=outline,
                fill=self.background,
                width=2,
            )

            if selected:
                self.indicator.create_rectangle(
                    7,
                    7,
                    11,
                    11,
                    outline=outline,
                    fill=outline,
                    width=1,
                )

        else:
            # Compact sub-option style:
            # small outlined circle + inset filled dot.
            self.indicator.create_oval(
                4,
                4,
                14,
                14,
                outline=outline,
                fill=self.background,
                width=2,
            )

            if selected:
                self.indicator.create_oval(
                    7,
                    7,
                    11,
                    11,
                    outline=outline,
                    fill=outline,
                    width=1,
                )

        self.text_label.configure(
            fg=foreground
        )


class RandomizerGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Pokémon Emerald Expansion Randomiser")
        self.geometry("900x780")
        self.minsize(800, 650)

        self.q = queue.Queue()
        self.running = False

        self.seed_var = tk.StringVar()
        self.pokemon_bst_mode = tk.StringVar(value="")
        self.wild_mode = tk.StringVar(value="")
        self.wild_allow_special_var = tk.BooleanVar(value=False)
        self.wild_similar_bst_var = tk.BooleanVar(value=False)
        self.static_mode = tk.StringVar(value="")
        self.trainer_mode = tk.StringVar(value="")
        self.trainer_allow_special_var = tk.BooleanVar(value=False)
        self.trainer_similar_bst_var = tk.BooleanVar(value=False)
        self.trainer_force_six_major_var = tk.BooleanVar(value=False)
        self.trainer_type_themes_var = tk.BooleanVar(value=False)
        self.move_species_specific_var = tk.BooleanVar(value=False)
        self.move_same_type_bias_var = tk.BooleanVar(value=False)
        # A standalone release is expected to produce a playable ROM. Keep the
        # build enabled by default; users can still opt out for source-only
        # development runs.
        self.build_var = tk.BooleanVar(value=True)
        self.clean_build_var = tk.BooleanVar(value=False)
        self.tm_shop_var = tk.BooleanVar(value=False)
        self.tm_catalog_generation_var = tk.StringVar(value="")
        self.evolution_shop_var = tk.BooleanVar(value=False)
        self.regional_postcard_shop_var = tk.BooleanVar(value=False)
        self.mega_shop_var = tk.BooleanVar(value=False)
        self.game_corner_var = tk.BooleanVar(value=False)
        self.all_fossils_var = tk.BooleanVar(value=False)
        self.fossil_only_replacements_var = tk.BooleanVar(value=False)

        # Independent build/gameplay rules. All are opt-in.
        self.game_permadeath_var = tk.BooleanVar(value=False)
        self.game_hm_free_var = tk.BooleanVar(value=False)
        self.game_hm_progression_bypass_var = tk.BooleanVar(value=False)
        self.game_receive_items_var = tk.BooleanVar(value=False)
        self.game_perma_repel_var = tk.BooleanVar(value=False)
        self.game_cap_candy_var = tk.BooleanVar(value=False)
        self.game_mom_bonus_var = tk.BooleanVar(value=False)
        self.game_skip_intro_var = tk.BooleanVar(value=False)
        self.game_party_heal_var = tk.BooleanVar(value=False)
        self.game_time_turner_var = tk.BooleanVar(value=False)
        self.game_weather_setter_var = tk.BooleanVar(value=False)
        self.game_always_catch_var = tk.BooleanVar(value=False)
        self.game_force_shiny_var = tk.BooleanVar(value=False)
        self.game_permanent_megas_var = tk.BooleanVar(value=False)
        self.regional_evolution_postcards_var = tk.BooleanVar(value=False)
        self.game_level_caps_var = tk.BooleanVar(value=False)
        self.game_always_mirage_island_var = tk.BooleanVar(value=False)
        self.game_event_island_access_var = tk.BooleanVar(value=False)

        # Independent difficulty rules. All are opt-in.
        self.difficulty_ai_enabled_var = tk.BooleanVar(value=False)
        self.difficulty_ai_mode_var = tk.StringVar(value="")
        self.difficulty_levels_enabled_var = tk.BooleanVar(value=False)
        self.difficulty_level_amount_var = tk.StringVar(value="5")
        self.difficulty_level_scope_var = tk.StringVar(value="")
        self.difficulty_evolution_stage_var = tk.BooleanVar(value=False)
        self.difficulty_boss_mega_var = tk.BooleanVar(value=False)
        self.difficulty_iv_enabled_var = tk.BooleanVar(value=False)
        self.difficulty_iv_mode_var = tk.StringVar(value="")
        self.difficulty_competitive_builds_var = tk.BooleanVar(value=False)
        self.difficulty_movesets_var = tk.BooleanVar(value=False)
        self.difficulty_held_items_var = tk.BooleanVar(value=False)
        self.difficulty_trainer_items_var = tk.BooleanVar(value=False)
        self.difficulty_force_set_var = tk.BooleanVar(value=False)
        self.difficulty_disable_bag_var = tk.BooleanVar(value=False)

        # Starter selection uses two mutually exclusive top-level choices.
        # With neither selected, the normal starters are left unchanged.
        self.manual_starters_var = tk.BooleanVar(value=False)
        self.starter_three_stage_var = tk.BooleanVar(value=False)
        self.rival_starter_continuity_var = tk.BooleanVar(value=False)

        self.status_var = tk.StringVar(value="Ready")

        self.starter_entries = discover_selectable_starters()
        self.starter_label_to_species = {
            label: species
            for label, species in self.starter_entries
        }
        self.starter_species_to_label = {
            species: label
            for label, species in self.starter_entries
        }
        self.starter_labels = [
            label
            for label, _ in self.starter_entries
        ]

        default_starters = read_default_starters()
        fallback_labels = self.starter_labels[:3]
        self.manual_starter_vars = []

        for index in range(3):
            species = default_starters[index]
            label = self.starter_species_to_label.get(species)

            if label is None:
                label = fallback_labels[index]

            self.manual_starter_vars.append(
                tk.StringVar(value=label)
            )

        self.starter_sprite_images = [None, None, None]
        self.starter_combo_boxes = []
        self.starter_sprite_labels = []

        self.component_vars = {
            key: tk.BooleanVar(value=False)
            for key, _ in COMPONENTS
        }

        # Starters stay unchanged until random or manual starter mode is chosen.
        self.component_vars["starters"].set(False)

        self.log_path = OUTPUT_DIR / "randomizer_last.log"

        self._build_ui()
        self.after(100, self._poll_queue)

    def _build_ui(self):
        # Keep the options usable on smaller displays as the number of GUI
        # controls grows.  The main content scrolls, while RANDOMISE remains
        # fixed at the bottom of the window.
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll_host = tk.Frame(self)
        scroll_host.grid(row=0, column=0, sticky="nsew")
        scroll_host.grid_rowconfigure(0, weight=1)
        scroll_host.grid_columnconfigure(0, weight=1)

        main_canvas = tk.Canvas(
            scroll_host,
            borderwidth=0,
            highlightthickness=0,
            background=self.cget("background"),
        )
        main_scrollbar = ttk.Scrollbar(
            scroll_host,
            orient="vertical",
            command=main_canvas.yview,
        )
        main_canvas.configure(yscrollcommand=main_scrollbar.set)
        main_canvas.grid(row=0, column=0, sticky="nsew")
        main_scrollbar.grid(row=0, column=1, sticky="ns")

        main_content = tk.Frame(
            main_canvas,
            background=self.cget("background"),
        )
        main_window = main_canvas.create_window(
            (0, 0),
            window=main_content,
            anchor="nw",
        )

        def refresh_scroll_region(_event=None):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))

        def resize_main_content(event):
            # Match the content width to the viewport. Its natural requested
            # height remains free to grow and activate scrolling, including
            # when controls are shown or hidden after the window opens.
            main_canvas.itemconfigure(main_window, width=event.width)
            refresh_scroll_region()

        def scroll_main_content(event):
            # Preserve the Output / Build Log's own mouse-wheel behaviour.
            if isinstance(event.widget, tk.Text):
                return

            if getattr(event, "num", None) == 4:
                units = -3
            elif getattr(event, "num", None) == 5:
                units = 3
            else:
                delta = getattr(event, "delta", 0)
                if not delta:
                    return
                units = -max(1, abs(delta) // 120)
                if delta < 0:
                    units = -units

            main_canvas.yview_scroll(units, "units")

        main_content.bind("<Configure>", refresh_scroll_region)
        main_canvas.bind("<Configure>", resize_main_content)
        self.bind_all("<MouseWheel>", scroll_main_content, add="+")
        self.bind_all("<Button-4>", scroll_main_content, add="+")
        self.bind_all("<Button-5>", scroll_main_content, add="+")

        tk.Label(
            main_content,
            text="Pokémon Emerald Expansion Randomiser",
            font=("TkDefaultFont", 18, "bold"),
        ).pack(pady=(14, 4))

        tk.Label(
            main_content,
            text=(
                "Options are built into the ROM. Each New Game creates a new, "
                "stable randomised world."
            ),
        ).pack(pady=(0, 8))

        seed_box = tk.LabelFrame(main_content, text="Seed")
        seed_box.pack(fill="x", padx=18, pady=4)

        seed_row = tk.Frame(seed_box)
        seed_row.pack(fill="x", padx=8, pady=8)

        tk.Label(seed_row, text="Seed:").pack(side="left")

        tk.Entry(
            seed_row,
            textvariable=self.seed_var,
        ).pack(side="left", fill="x", expand=True, padx=8)

        tk.Button(
            seed_row,
            text="Random Seed",
            command=self._random_seed,
        ).pack(side="left")

        # ----------------------------------------------------
        # RANDOMIZER CATEGORY TABS
        # ----------------------------------------------------

        notebook = ttk.Notebook(main_content)
        notebook.pack(
            fill="x",
            padx=18,
            pady=4,
        )

        pokemon_tab = tk.Frame(notebook)
        manual_customization_tab = tk.Frame(notebook)
        moves_tab = tk.Frame(notebook)
        starters_tab = tk.Frame(notebook)
        encounters_tab = tk.Frame(notebook)
        trainers_tab = tk.Frame(notebook)
        difficulty_tab = tk.Frame(notebook)
        items_tab = tk.Frame(notebook)
        game_options_tab = tk.Frame(notebook)

        notebook.add(pokemon_tab, text="Pokémon")
        notebook.add(moves_tab, text="Moves")
        notebook.add(starters_tab, text="Starters")
        notebook.add(encounters_tab, text="Encounters")
        notebook.add(trainers_tab, text="Trainer Pokémon")
        notebook.add(items_tab, text="Item Randomisation")
        notebook.add(game_options_tab, text="Game Options")
        notebook.add(difficulty_tab, text="Difficulty")
        notebook.add(
            manual_customization_tab,
            text="Manual Customisation",
        )

        # ----------------------------------------------------
        # POKEMON TAB
        # ----------------------------------------------------

        pokemon_box = tk.LabelFrame(
            pokemon_tab,
            text="Pokémon Randomisation",
        )
        pokemon_box.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        pokemon_row = 0

        FilledIndicatorOption(
            pokemon_box,
            text=COMPONENT_OPTION_LABELS["pokemon_types"],
            variable=self.component_vars["pokemon_types"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["pokemon_types"],
        ).grid(
            row=pokemon_row,
            column=0,
            sticky="w",
            padx=12,
            pady=4,
        )

        pokemon_row += 1

        FilledIndicatorOption(
            pokemon_box,
            text=COMPONENT_OPTION_LABELS["pokemon_bst"],
            variable=self.component_vars["pokemon_bst"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["pokemon_bst"],
        ).grid(
            row=pokemon_row,
            column=0,
            sticky="w",
            padx=12,
            pady=(4, 2),
        )

        pokemon_row += 1

        pokemon_bst_modes = tk.Frame(
            pokemon_box,
        )
        pokemon_bst_modes.grid(
            row=pokemon_row,
            column=0,
            sticky="w",
            padx=38,
            pady=(2, 4),
        )

        self.pokemon_bst_same = FilledIndicatorOption(
            pokemon_bst_modes,
            text="Keep original BST",
            variable=self.pokemon_bst_mode,
            value="same",
            shape="circle",
            tooltip=OPTION_HELP["pokemon_bst_same"],
        )
        self.pokemon_bst_same.pack(
            side="left",
            padx=(0, 16),
        )

        self.pokemon_bst_stages = FilledIndicatorOption(
            pokemon_bst_modes,
            text="Randomise by evolution stage",
            variable=self.pokemon_bst_mode,
            value="stages",
            shape="circle",
            tooltip=OPTION_HELP["pokemon_bst_stages"],
        )
        self.pokemon_bst_stages.pack(
            side="left",
            padx=(0, 16),
        )

        self.pokemon_bst_full = FilledIndicatorOption(
            pokemon_bst_modes,
            text="Fully randomise BST",
            variable=self.pokemon_bst_mode,
            value="full",
            shape="circle",
            tooltip=OPTION_HELP["pokemon_bst_full"],
        )
        self.pokemon_bst_full.pack(
            side="left",
        )

        pokemon_row += 1

        for key in (
            "abilities",
            "evolutions",
            "trade_evos",
            "trades",
        ):
            FilledIndicatorOption(
                pokemon_box,
                text=COMPONENT_OPTION_LABELS[key],
                variable=self.component_vars[key],
                shape="square",
                command=self._update_modes,
                tooltip=OPTION_HELP[key],
            ).grid(
                row=pokemon_row,
                column=0,
                sticky="w",
                padx=12,
                pady=4,
            )

            pokemon_row += 1

        pokemon_box.columnconfigure(0, weight=1)

        # ----------------------------------------------------
        # MANUAL CUSTOMISATION TAB
        # ----------------------------------------------------

        self.manual_customization_panel = ManualCustomizationPanel(
            manual_customization_tab
        )
        self.manual_customization_panel.pack(
            fill="both",
            expand=True,
        )

        # ----------------------------------------------------
        # MOVES TAB
        # ----------------------------------------------------

        moves_box = tk.LabelFrame(
            moves_tab,
            text="Move Randomisation",
        )
        moves_box.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        FilledIndicatorOption(
            moves_box,
            text=COMPONENT_OPTION_LABELS["move_types"],
            variable=self.component_vars["move_types"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["move_types"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(7, 4),
        )

        FilledIndicatorOption(
            moves_box,
            text=COMPONENT_OPTION_LABELS["moves"],
            variable=self.component_vars["moves"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["moves"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(4, 2),
        )

        self.move_species_specific_option = FilledIndicatorOption(
            moves_box,
            text="Enable species-specific move pools",
            variable=self.move_species_specific_var,
            shape="square",
            tooltip=OPTION_HELP["moves_species_specific"],
        )
        self.move_species_specific_option.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.move_same_type_bias_option = FilledIndicatorOption(
            moves_box,
            text="Enable same-type move bias",
            variable=self.move_same_type_bias_var,
            shape="square",
            tooltip=OPTION_HELP["moves_same_type_bias"],
        )
        self.move_same_type_bias_option.pack(
            anchor="w",
            padx=38,
            pady=(2, 8),
        )

        FilledIndicatorOption(
            moves_box,
            text=COMPONENT_OPTION_LABELS["tms"],
            variable=self.component_vars["tms"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["tms"],
        ).pack(
            anchor="w",
            padx=12,
            pady=4,
        )

        FilledIndicatorOption(
            moves_box,
            text=COMPONENT_OPTION_LABELS["evolution_moves"],
            variable=self.component_vars["evolution_moves"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["evolution_moves"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(4, 8),
        )

        # ----------------------------------------------------
        # STARTERS TAB
        # ----------------------------------------------------

        starters_box = tk.LabelFrame(
            starters_tab,
            text="Starter Pokémon",
        )
        starters_box.pack(
            fill="x",
            padx=10,
            pady=(10, 4),
        )

        starter_mode_row = tk.Frame(
            starters_box,
        )
        starter_mode_row.pack(
            anchor="w",
            padx=12,
            pady=(7, 2),
        )

        FilledIndicatorOption(
            starter_mode_row,
            text=COMPONENT_OPTION_LABELS["starters"],
            variable=self.component_vars["starters"],
            shape="circle",
            command=lambda: self._select_starter_mode("random"),
            tooltip=OPTION_HELP["starter_random"],
        ).pack(
            side="left",
            padx=(0, 20),
        )

        FilledIndicatorOption(
            starter_mode_row,
            text="Enable manual starter selection",
            variable=self.manual_starters_var,
            shape="circle",
            command=lambda: self._select_starter_mode("manual"),
            tooltip=OPTION_HELP["starter_manual"],
        ).pack(
            side="left",
        )

        self.starter_three_stage_option = FilledIndicatorOption(
            starters_box,
            text="Enable three-stage evolution-line starters",
            variable=self.starter_three_stage_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["starter_three_stage"],
        )
        self.starter_three_stage_option.pack(
            anchor="w",
            padx=(36, 12),
            pady=(1, 3),
        )

        self.rival_starter_continuity_option = FilledIndicatorOption(
            starters_box,
            text="Enable rival starter continuity",
            variable=self.rival_starter_continuity_var,
            shape="square",
            tooltip=OPTION_HELP["starter_rival_continuity"],
        )
        self.rival_starter_continuity_option.pack(
            anchor="w",
            padx=(36, 12),
            pady=(1, 7),
        )

        # Hidden unless manual mode is active.
        self.manual_starter_box = tk.LabelFrame(
            starters_tab,
            text="Manual starter choices",
        )

        choices_row = tk.Frame(
            self.manual_starter_box
        )
        choices_row.pack(
            fill="x",
            padx=8,
            pady=8,
        )

        for slot in range(3):
            slot_frame = tk.Frame(
                choices_row
            )
            slot_frame.grid(
                row=0,
                column=slot,
                sticky="nsew",
                padx=6,
            )

            choices_row.columnconfigure(
                slot,
                weight=1,
            )

            tk.Label(
                slot_frame,
                text=f"Starter {slot + 1}",
                font=("TkDefaultFont", 10, "bold"),
            ).pack(
                anchor="center",
                pady=(0, 4),
            )

            combo_row = tk.Frame(
                slot_frame,
            )
            combo_row.pack(
                fill="x",
                padx=2,
            )

            combo = ttk.Combobox(
                combo_row,
                textvariable=self.manual_starter_vars[slot],
                values=self.starter_labels,
                state="readonly",
                height=18,
                width=25,
            )
            combo.pack(
                side="left",
                fill="x",
                expand=True,
            )
            combo.bind(
                "<<ComboboxSelected>>",
                lambda _event, index=slot: self._update_starter_sprite(index),
            )
            self.starter_combo_boxes.append(
                combo
            )

            HelpIcon(
                combo_row,
                OPTION_HELP["starter_dropdown"],
            ).pack(
                side="left",
                padx=(5, 0),
            )

            sprite_label = tk.Label(
                slot_frame,
                anchor="center",
            )
            sprite_label.pack(
                pady=(6, 0),
            )
            self.starter_sprite_labels.append(
                sprite_label
            )

        # ----------------------------------------------------
        # ENCOUNTERS TAB
        # ----------------------------------------------------

        encounters_box = tk.LabelFrame(
            encounters_tab,
            text="Encounters",
        )
        encounters_box.pack(
            fill="x",
            padx=10,
            pady=(10, 10),
        )

        FilledIndicatorOption(
            encounters_box,
            text=COMPONENT_OPTION_LABELS["wild"],
            variable=self.component_vars["wild"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["wild"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(8, 2),
        )

        wild_mode_row = tk.Frame(
            encounters_box,
        )
        wild_mode_row.pack(
            anchor="w",
            padx=38,
            pady=(2, 6),
        )

        self.wild_mapping = FilledIndicatorOption(
            wild_mode_row,
            text="Use one-to-one species mapping",
            variable=self.wild_mode,
            value="mapping",
            shape="circle",
            tooltip=OPTION_HELP["wild_mapping"],
        )
        self.wild_mapping.pack(
            side="left",
            padx=(0, 14),
        )

        self.wild_slots = FilledIndicatorOption(
            wild_mode_row,
            text="Randomise encounter slots",
            variable=self.wild_mode,
            value="slots",
            shape="circle",
            tooltip=OPTION_HELP["wild_slots"],
        )
        self.wild_slots.pack(
            side="left",
            padx=(0, 14),
        )

        self.wild_runtime = FilledIndicatorOption(
            wild_mode_row,
            text="Use route-local species mappings",
            variable=self.wild_mode,
            value="runtime",
            shape="circle",
            tooltip=OPTION_HELP["wild_runtime"],
        )
        self.wild_runtime.pack(
            side="left",
        )

        self.wild_similar_bst = FilledIndicatorOption(
            encounters_box,
            text=f"Enable similar-BST restriction (±{BST_TOLERANCE})",
            variable=self.wild_similar_bst_var,
            shape="square",
            tooltip=OPTION_HELP["wild_similar_bst"],
        )
        self.wild_similar_bst.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.wild_allow_special = FilledIndicatorOption(
            encounters_box,
            text="Enable legendary / special Pokémon",
            variable=self.wild_allow_special_var,
            shape="square",
            tooltip=OPTION_HELP["wild_allow_special"],
        )
        self.wild_allow_special.pack(
            anchor="w",
            padx=38,
            pady=(2, 8),
        )

        FilledIndicatorOption(
            encounters_box,
            text=COMPONENT_OPTION_LABELS["statics"],
            variable=self.component_vars["statics"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["statics"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(4, 2),
        )

        static_mode_row = tk.Frame(
            encounters_box,
        )
        static_mode_row.pack(
            anchor="w",
            padx=38,
            pady=(2, 8),
        )

        self.static_preserve = FilledIndicatorOption(
            static_mode_row,
            text="Preserve legendary / special status",
            variable=self.static_mode,
            value="preserve",
            shape="circle",
            tooltip=OPTION_HELP["static_preserve"],
        )
        self.static_preserve.pack(
            side="left",
            padx=(0, 18),
        )

        self.static_full = FilledIndicatorOption(
            static_mode_row,
            text="Use fully random replacements",
            variable=self.static_mode,
            value="full",
            shape="circle",
            tooltip=OPTION_HELP["static_full"],
        )
        self.static_full.pack(
            side="left",
        )

        FilledIndicatorOption(
            encounters_box,
            text=COMPONENT_OPTION_LABELS["eggs"],
            variable=self.component_vars["eggs"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["eggs"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(4, 8),
        )

        # ----------------------------------------------------
        # TRAINERS POKEMON TAB
        # ----------------------------------------------------

        trainers_box = tk.LabelFrame(
            trainers_tab,
            text="Trainer Pokémon",
        )
        trainers_box.pack(
            fill="x",
            padx=10,
            pady=(10, 10),
        )

        FilledIndicatorOption(
            trainers_box,
            text=COMPONENT_OPTION_LABELS["trainers"],
            variable=self.component_vars["trainers"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["trainers"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(8, 2),
        )

        trainer_mode_row = tk.Frame(
            trainers_box,
        )
        trainer_mode_row.pack(
            anchor="w",
            padx=38,
            pady=(2, 6),
        )

        self.trainer_mapping = FilledIndicatorOption(
            trainer_mode_row,
            text="Use one-to-one species mapping",
            variable=self.trainer_mode,
            value="mapping",
            shape="circle",
            tooltip=OPTION_HELP["trainer_mapping"],
        )
        self.trainer_mapping.pack(
            side="left",
            padx=(0, 14),
        )

        self.trainer_full = FilledIndicatorOption(
            trainer_mode_row,
            text="Randomise each trainer Pokémon",
            variable=self.trainer_mode,
            value="full",
            shape="circle",
            tooltip=OPTION_HELP["trainer_full"],
        )
        self.trainer_full.pack(
            side="left",
        )

        self.trainer_similar_bst = FilledIndicatorOption(
            trainers_box,
            text=f"Enable similar-BST restriction (±{BST_TOLERANCE})",
            variable=self.trainer_similar_bst_var,
            shape="square",
            tooltip=OPTION_HELP["trainer_similar_bst"],
        )
        self.trainer_similar_bst.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.trainer_allow_special = FilledIndicatorOption(
            trainers_box,
            text="Enable legendary / special Pokémon",
            variable=self.trainer_allow_special_var,
            shape="square",
            tooltip=OPTION_HELP["trainer_allow_special"],
        )
        self.trainer_allow_special.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.trainer_type_themes = FilledIndicatorOption(
            trainers_box,
            text="Enable randomised Gym and Elite Four type themes",
            variable=self.trainer_type_themes_var,
            shape="square",
            tooltip=OPTION_HELP["trainer_type_themes"],
        )
        self.trainer_type_themes.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.trainer_force_six_major = FilledIndicatorOption(
            trainers_box,
            text="Enable six-Pokémon major trainer parties",
            variable=self.trainer_force_six_major_var,
            shape="square",
            tooltip=OPTION_HELP["trainer_force_six_major"],
        )
        self.trainer_force_six_major.pack(
            anchor="w",
            padx=38,
            pady=(2, 8),
        )

        # ----------------------------------------------------
        # DIFFICULTY TAB
        # ----------------------------------------------------

        difficulty_ai_box = tk.LabelFrame(
            difficulty_tab,
            text="Trainer AI and Levels",
        )
        difficulty_ai_box.pack(
            fill="x",
            padx=10,
            pady=(10, 4),
        )

        FilledIndicatorOption(
            difficulty_ai_box,
            text="Enable improved trainer AI",
            variable=self.difficulty_ai_enabled_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["difficulty_ai"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(7, 2),
        )

        difficulty_ai_modes = tk.Frame(
            difficulty_ai_box,
        )
        difficulty_ai_modes.pack(
            anchor="w",
            padx=38,
            pady=(2, 5),
        )

        self.difficulty_ai_fair = FilledIndicatorOption(
            difficulty_ai_modes,
            text="Use fair smart AI",
            variable=self.difficulty_ai_mode_var,
            value="fair",
            shape="circle",
            tooltip=OPTION_HELP["difficulty_ai"],
        )
        self.difficulty_ai_fair.pack(
            side="left",
            padx=(0, 18),
        )

        self.difficulty_ai_omniscient = FilledIndicatorOption(
            difficulty_ai_modes,
            text="Use omniscient AI",
            variable=self.difficulty_ai_mode_var,
            value="omniscient",
            shape="circle",
            tooltip=OPTION_HELP["difficulty_ai"],
        )
        self.difficulty_ai_omniscient.pack(
            side="left",
        )

        FilledIndicatorOption(
            difficulty_ai_box,
            text="Enable trainer level increases",
            variable=self.difficulty_levels_enabled_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["difficulty_level_boost"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(4, 2),
        )

        difficulty_level_row = tk.Frame(
            difficulty_ai_box,
        )
        difficulty_level_row.pack(
            anchor="w",
            padx=38,
            pady=(2, 2),
        )

        tk.Label(
            difficulty_level_row,
            text="Additional levels:",
        ).pack(side="left")

        self.difficulty_level_spinbox = ttk.Spinbox(
            difficulty_level_row,
            from_=1,
            to=20,
            width=4,
            textvariable=self.difficulty_level_amount_var,
        )
        self.difficulty_level_spinbox.pack(
            side="left",
            padx=(6, 0),
        )

        difficulty_level_scopes = tk.Frame(
            difficulty_ai_box,
        )
        difficulty_level_scopes.pack(
            anchor="w",
            padx=38,
            pady=(2, 7),
        )

        self.difficulty_levels_all = FilledIndicatorOption(
            difficulty_level_scopes,
            text="Apply to all trainers",
            variable=self.difficulty_level_scope_var,
            value="all",
            shape="circle",
            tooltip=OPTION_HELP["difficulty_level_boost"],
        )
        self.difficulty_levels_all.pack(
            side="left",
            padx=(0, 18),
        )

        self.difficulty_levels_major = FilledIndicatorOption(
            difficulty_level_scopes,
            text="Apply only to Gym Leaders, rivals, Elite Four and Champion",
            variable=self.difficulty_level_scope_var,
            value="major",
            shape="circle",
            tooltip=OPTION_HELP["difficulty_level_boost"],
        )
        self.difficulty_levels_major.pack(
            side="left",
        )

        difficulty_species_box = tk.LabelFrame(
            difficulty_tab,
            text="Trainer Pokémon Species Rules",
        )
        difficulty_species_box.pack(
            fill="x",
            padx=10,
            pady=4,
        )

        self.difficulty_evolution_stage_option = FilledIndicatorOption(
            difficulty_species_box,
            text="Enable evolution-stage rules for late-game trainer Pokémon",
            variable=self.difficulty_evolution_stage_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["difficulty_evolution_stage"],
        )
        self.difficulty_evolution_stage_option.pack(
            anchor="w",
            padx=12,
            pady=(7, 3),
        )

        self.difficulty_boss_mega_option = FilledIndicatorOption(
            difficulty_species_box,
            text="Enable permanent Mega aces for later bosses",
            variable=self.difficulty_boss_mega_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["difficulty_boss_mega"],
        )
        self.difficulty_boss_mega_option.pack(
            anchor="w",
            padx=12,
            pady=(3, 7),
        )

        difficulty_build_box = tk.LabelFrame(
            difficulty_tab,
            text="Trainer Pokémon Builds",
        )
        difficulty_build_box.pack(
            fill="x",
            padx=10,
            pady=4,
        )

        FilledIndicatorOption(
            difficulty_build_box,
            text="Enable improved trainer Pokémon IVs",
            variable=self.difficulty_iv_enabled_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["difficulty_iv"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(7, 2),
        )

        difficulty_iv_modes = tk.Frame(
            difficulty_build_box,
        )
        difficulty_iv_modes.pack(
            anchor="w",
            padx=38,
            pady=(2, 5),
        )

        self.difficulty_iv_scaled = FilledIndicatorOption(
            difficulty_iv_modes,
            text="Scale IVs with game progress",
            variable=self.difficulty_iv_mode_var,
            value="scaled",
            shape="circle",
            tooltip=OPTION_HELP["difficulty_iv"],
        )
        self.difficulty_iv_scaled.pack(
            side="left",
            padx=(0, 18),
        )

        self.difficulty_iv_perfect = FilledIndicatorOption(
            difficulty_iv_modes,
            text="Use perfect IVs",
            variable=self.difficulty_iv_mode_var,
            value="perfect",
            shape="circle",
            tooltip=OPTION_HELP["difficulty_iv"],
        )
        self.difficulty_iv_perfect.pack(
            side="left",
        )

        for label, variable, help_key in (
            (
                "Enable competitive EVs and natures for major trainers",
                self.difficulty_competitive_builds_var,
                "difficulty_competitive_builds",
            ),
            (
                "Enable improved movesets for all trainers",
                self.difficulty_movesets_var,
                "difficulty_movesets",
            ),
            (
                "Enable held items for major trainer Pokémon",
                self.difficulty_held_items_var,
                "difficulty_held_items",
            ),
            (
                "Enable healing items for major trainers",
                self.difficulty_trainer_items_var,
                "difficulty_trainer_items",
            ),
        ):
            FilledIndicatorOption(
                difficulty_build_box,
                text=label,
                variable=variable,
                shape="square",
                tooltip=OPTION_HELP[help_key],
            ).pack(
                anchor="w",
                padx=12,
                pady=3,
            )

        difficulty_rules_box = tk.LabelFrame(
            difficulty_tab,
            text="Player Battle Rules",
        )
        difficulty_rules_box.pack(
            fill="x",
            padx=10,
            pady=(4, 10),
        )

        for label, variable, help_key in (
            (
                "Enable forced Set battle style",
                self.difficulty_force_set_var,
                "difficulty_force_set",
            ),
            (
                "Enable Bag restrictions in trainer battles",
                self.difficulty_disable_bag_var,
                "difficulty_disable_bag",
            ),
        ):
            FilledIndicatorOption(
                difficulty_rules_box,
                text=label,
                variable=variable,
                shape="square",
                tooltip=OPTION_HELP[help_key],
            ).pack(
                anchor="w",
                padx=12,
                pady=4,
            )

        # ----------------------------------------------------
        # ITEMS TAB
        # ----------------------------------------------------

        items_box = tk.LabelFrame(
            items_tab,
            text="Item Randomisation",
        )
        items_box.pack(
            fill="x",
            padx=10,
            pady=(10, 4),
        )

        FilledIndicatorOption(
            items_box,
            text=COMPONENT_OPTION_LABELS["items"],
            variable=self.component_vars["items"],
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["items"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(7, 2),
        )

        self.game_corner_check = FilledIndicatorOption(
            items_box,
            text="Enable Game Corner reward randomisation",
            variable=self.game_corner_var,
            shape="square",
            tooltip=OPTION_HELP["game_corner"],
        )
        self.game_corner_check.pack(
            anchor="w",
            padx=30,
            pady=2,
        )

        fossil_box = tk.LabelFrame(
            items_tab,
            text="Fossils",
        )
        fossil_box.pack(
            fill="x",
            padx=10,
            pady=(4, 10),
        )

        FilledIndicatorOption(
            fossil_box,
            text="Enable all fossil revivals",
            variable=self.all_fossils_var,
            shape="square",
            tooltip=OPTION_HELP["all_fossils"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(7, 2),
        )

        self.fossil_only_replacements_option = FilledIndicatorOption(
            fossil_box,
            text="Enable fossil-only Pokémon for fossil revivals",
            variable=self.fossil_only_replacements_var,
            shape="square",
            tooltip=OPTION_HELP["fossil_only_replacements"],
        )
        self.fossil_only_replacements_option.pack(
            anchor="w",
            padx=12,
            pady=(2, 7),
        )

        regional_postcard_box = tk.LabelFrame(
            items_tab,
            text="Regional Evolution Postcards",
        )
        regional_postcard_box.pack(
            fill="x",
            padx=10,
            pady=(4, 10),
        )

        FilledIndicatorOption(
            regional_postcard_box,
            text="Enable regional evolution postcards",
            variable=self.regional_evolution_postcards_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["regional_evolution_postcards"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(7, 2),
        )

        self.regional_postcard_shop_option = FilledIndicatorOption(
            regional_postcard_box,
            text="Enable all regional postcards in the Lilycove store",
            variable=self.regional_postcard_shop_var,
            shape="square",
            tooltip=OPTION_HELP["regional_postcard_shop"],
        )
        self.regional_postcard_shop_option.pack(
            anchor="w",
            padx=38,
            pady=(2, 7),
        )

        store_box = tk.LabelFrame(
            items_tab,
            text="Store Options",
        )
        store_box.pack(
            fill="x",
            padx=10,
            pady=(4, 10),
        )

        self.tm_shop_option = FilledIndicatorOption(
            store_box,
            text="Enable a Lilycove TM generation catalogue",
            variable=self.tm_shop_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["tm_shop"],
        )
        self.tm_shop_option.pack(
            anchor="w",
            padx=12,
            pady=(7, 2),
        )

        self.tm_catalog_options = []

        tm_catalog_grid = tk.Frame(
            store_box,
        )
        tm_catalog_grid.pack(
            fill="x",
            padx=38,
            pady=(2, 6),
        )

        for index, (key, profile) in enumerate(TM_CATALOGS.items()):
            option = FilledIndicatorOption(
                tm_catalog_grid,
                text=profile["label"],
                variable=self.tm_catalog_generation_var,
                value=key,
                shape="circle",
                tooltip=OPTION_HELP["tm_shop"],
            )
            option.grid(
                row=index // 3,
                column=index % 3,
                sticky="w",
                padx=(0, 16),
                pady=2,
            )
            self.tm_catalog_options.append(option)

        FilledIndicatorOption(
            store_box,
            text="Enable all evolution items in the Lilycove store",
            variable=self.evolution_shop_var,
            shape="square",
            tooltip=OPTION_HELP["evolution_shop"],
        ).pack(
            anchor="w",
            padx=12,
            pady=2,
        )

        FilledIndicatorOption(
            store_box,
            text="Enable all Mega Stones in the Lilycove store",
            variable=self.mega_shop_var,
            shape="square",
            tooltip=OPTION_HELP["mega_shop"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(2, 7),
        )

        # ----------------------------------------------------
        # ----------------------------------------------------
        # GAME OPTIONS TAB
        # ----------------------------------------------------

        game_options_box = tk.LabelFrame(
            game_options_tab,
            text="Game Options",
        )
        game_options_box.pack(
            fill="x",
            padx=10,
            pady=10,
        )

        for label, variable, help_key in (
            (
                "Enable HM use without teaching moves and receive field tools",
                self.game_hm_free_var,
                "game_hm_free",
            ),
            (
                "Enable removal of HM progression requirements",
                self.game_hm_progression_bypass_var,
                "game_hm_progression_bypass",
            ),
        ):
            FilledIndicatorOption(
                game_options_box,
                text=label,
                variable=variable,
                shape="square",
                tooltip=OPTION_HELP[help_key],
            ).pack(
                anchor="w",
                padx=12,
                pady=4,
            )

        FilledIndicatorOption(
            game_options_box,
            text="Enable custom field items",
            variable=self.game_receive_items_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["game_receive_items"],
        ).pack(
            anchor="w",
            padx=12,
            pady=(4, 2),
        )

        self.game_perma_repel_option = FilledIndicatorOption(
            game_options_box,
            text="Enable Perma Repel",
            variable=self.game_perma_repel_var,
            shape="square",
            tooltip=OPTION_HELP["game_perma_repel"],
        )
        self.game_perma_repel_option.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.game_party_heal_option = FilledIndicatorOption(
            game_options_box,
            text="Enable Party Heal",
            variable=self.game_party_heal_var,
            shape="square",
            tooltip=OPTION_HELP["game_party_heal"],
        )
        self.game_party_heal_option.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.game_time_turner_option = FilledIndicatorOption(
            game_options_box,
            text="Enable Time Turner",
            variable=self.game_time_turner_var,
            shape="square",
            tooltip=OPTION_HELP["game_time_turner"],
        )
        self.game_time_turner_option.pack(
            anchor="w",
            padx=38,
            pady=2,
        )

        self.game_weather_setter_option = FilledIndicatorOption(
            game_options_box,
            text="Enable Weather Setter",
            variable=self.game_weather_setter_var,
            shape="square",
            tooltip=OPTION_HELP["game_weather_setter"],
        )
        self.game_weather_setter_option.pack(
            anchor="w",
            padx=38,
            pady=(2, 4),
        )

        self.game_cap_candy_option = FilledIndicatorOption(
            game_options_box,
            text="Enable Level to cap party action",
            variable=self.game_cap_candy_var,
            shape="square",
            tooltip=OPTION_HELP["game_cap_candy"],
        )
        self.game_cap_candy_option.pack(anchor="w", padx=12, pady=4)

        FilledIndicatorOption(
            game_options_box,
            text="Mom gives 99 Ultra Balls and lots of money",
            variable=self.game_mom_bonus_var,
            shape="square",
            tooltip=OPTION_HELP["game_mom_bonus"],
        ).pack(anchor="w", padx=12, pady=4)

        FilledIndicatorOption(
            game_options_box,
            text="Skip intro",
            variable=self.game_skip_intro_var,
            shape="square",
            tooltip=OPTION_HELP["game_skip_intro"],
        ).pack(anchor="w", padx=12, pady=4)

        for label, variable, help_key in (
            (
                "Enable level caps",
                self.game_level_caps_var,
                "game_level_caps",
            ),
            (
                "Enable 100% catch rate",
                self.game_always_catch_var,
                "game_always_catch",
            ),
            (
                "Enable permanent death",
                self.game_permadeath_var,
                "game_permadeath",
            ),
            (
                "Enable forced shininess for all Pokémon",
                self.game_force_shiny_var,
                "game_force_shiny",
            ),
            (
                "Enable permanent Mega Evolutions",
                self.game_permanent_megas_var,
                "game_permanent_megas",
            ),
            (
                "Enable event-island access",
                self.game_event_island_access_var,
                "game_event_island_access",
            ),
            (
                "Enable permanent Mirage Island",
                self.game_always_mirage_island_var,
                "game_always_mirage_island",
            ),
        ):
            FilledIndicatorOption(
                game_options_box,
                text=label,
                variable=variable,
                shape="square",
                command=(
                    self._update_modes
                    if variable is self.game_permanent_megas_var
                    else None
                ),
                tooltip=OPTION_HELP[help_key],
            ).pack(
                anchor="w",
                padx=12,
                pady=4,
            )

        # SHARED BUILD / RUN CONTROLS
        # ----------------------------------------------------

        # Keep build controls outside the scrolling options area so they are
        # always visible alongside the fixed RANDOMISE button.
        build_box = tk.LabelFrame(self, text="Build")
        build_box.grid(
            row=1,
            column=0,
            sticky="ew",
            padx=18,
            pady=(4, 0),
        )

        FilledIndicatorOption(
            build_box,
            text="Enable ROM build after randomisation",
            variable=self.build_var,
            shape="square",
            command=self._update_modes,
            tooltip=OPTION_HELP["build"],
        ).pack(
            anchor="w",
            padx=8,
            pady=(7, 2),
        )

        self.clean_build_option = FilledIndicatorOption(
            build_box,
            text="Enable clean rebuild (slow; troubleshooting only)",
            variable=self.clean_build_var,
            shape="square",
            tooltip=OPTION_HELP["clean_build"],
        )
        self.clean_build_option.pack(
            anchor="w",
            padx=26,
            pady=(2, 7),
        )

        self.run_button = tk.Button(
            self,
            text="RANDOMISE",
            height=2,
            font=("TkDefaultFont", 13, "bold"),
            command=self._start,
        )
        self.run_button.grid(
            row=2,
            column=0,
            sticky="ew",
            padx=18,
            pady=(7, 8),
        )

        status_row = tk.Frame(main_content)
        status_row.pack(fill="x", padx=18, pady=2)

        tk.Label(
            status_row,
            text="Status:",
            font=("TkDefaultFont", 10, "bold"),
        ).pack(side="left")

        tk.Label(
            status_row,
            textvariable=self.status_var,
        ).pack(side="left", padx=6)

        output_box = tk.LabelFrame(main_content, text="Output / Build Log")
        output_box.pack(fill="both", expand=True, padx=18, pady=(4, 12))

        self.output = ScrolledText(
            output_box,
            wrap="word",
            state="disabled",
            font=("Consolas", 9),
        )
        self.output.pack(fill="both", expand=True, padx=6, pady=6)

        tk.Label(
            output_box,
            text=r"Latest run is also saved to output\randomizer_last.log",
            anchor="w",
        ).pack(fill="x", padx=6, pady=(0, 6))

        self._update_modes()


    def _select_starter_mode(self, mode):
        """
        Keep random and manual starter selection mutually exclusive.

        Either top-level circle can also be turned off. With both off, the
        normal game starters are left unchanged.
        """
        if mode not in {
            "random",
            "manual",
        }:
            raise ValueError(
                f"Unknown starter mode: {mode}"
            )

        if mode == "random":
            if self.component_vars["starters"].get():
                self.manual_starters_var.set(False)
            else:
                self.starter_three_stage_var.set(False)

        elif mode == "manual":
            if self.manual_starters_var.get():
                self.component_vars["starters"].set(False)
                self.starter_three_stage_var.set(False)

        self._update_modes()


    def _manual_starter_species(self):
        if not self.manual_starters_var.get():
            return None

        starters = []

        for variable in self.manual_starter_vars:
            label = variable.get().strip()
            species = self.starter_label_to_species.get(label)

            if species is None:
                return None

            starters.append(species)

        return tuple(starters)

    def _clear_starter_sprite(self, slot):
        self.starter_sprite_images[slot] = None
        self.starter_sprite_labels[slot].configure(
            image="",
            text="",
        )

    def _update_starter_sprite(self, slot):
        if not self.manual_starters_var.get():
            self._clear_starter_sprite(slot)
            return

        label = self.manual_starter_vars[slot].get().strip()
        species = self.starter_label_to_species.get(label)

        if species is None:
            self._clear_starter_sprite(slot)
            return

        sprite_path = find_front_sprite(species)

        if sprite_path is None:
            self.starter_sprite_images[slot] = None
            self.starter_sprite_labels[slot].configure(
                image="",
                text="Sprite unavailable",
            )
            return

        try:
            source_image = tk.PhotoImage(
                file=str(sprite_path)
            )

            # Expansion front graphics can contain multiple animation frames
            # vertically. Show only the first square frame.
            frame_size = min(
                source_image.width(),
                source_image.height(),
            )

            image = tk.PhotoImage(
                width=frame_size,
                height=frame_size,
            )
            image.tk.call(
                image,
                "copy",
                source_image,
                "-from",
                0,
                0,
                frame_size,
                frame_size,
                "-to",
                0,
                0,
            )

            # Normalize by the VISIBLE sprite artwork, not by the PNG canvas.
            #
            # Regional / alternate forms often use different amounts of empty
            # transparent space around the Pokemon. Scaling the entire image
            # therefore makes some forms look much larger than others even
            # when the source canvases are identical.
            #
            # Find the non-transparent bounding box, crop to it, then scale
            # that visible artwork to a consistent apparent size.
            min_x = frame_size
            min_y = frame_size
            max_x = -1
            max_y = -1

            for y in range(frame_size):
                for x in range(frame_size):
                    try:
                        transparent = (
                            image.transparency_get(
                                x,
                                y,
                            )
                        )
                    except tk.TclError:
                        # Fallback for Tk builds where transparency_get is
                        # unavailable: treat the whole frame as visible.
                        min_x = 0
                        min_y = 0
                        max_x = frame_size - 1
                        max_y = frame_size - 1
                        transparent = True
                        break

                    if not transparent:
                        min_x = min(
                            min_x,
                            x,
                        )
                        min_y = min(
                            min_y,
                            y,
                        )
                        max_x = max(
                            max_x,
                            x,
                        )
                        max_y = max(
                            max_y,
                            y,
                        )

                if (
                    min_x == 0
                    and min_y == 0
                    and max_x == frame_size - 1
                    and max_y == frame_size - 1
                ):
                    break

            if max_x >= min_x and max_y >= min_y:
                visible_width = (
                    max_x - min_x + 1
                )
                visible_height = (
                    max_y - min_y + 1
                )

                cropped = tk.PhotoImage(
                    width=visible_width,
                    height=visible_height,
                )
                cropped.tk.call(
                    cropped,
                    "copy",
                    image,
                    "-from",
                    min_x,
                    min_y,
                    max_x + 1,
                    max_y + 1,
                    "-to",
                    0,
                    0,
                )
                image = cropped

            # Target a much larger apparent sprite size than before.
            # The scale is based on the cropped visible Pokemon, so normal and
            # regional forms are kept visually consistent.
            preview_target = 96
            visible_max = max(
                image.width(),
                image.height(),
            )

            if visible_max > 0:
                scale = (
                    preview_target
                    / visible_max
                )

                # Tk PhotoImage supports integer zoom/subsample only. Search
                # for a small rational approximation so pixel art stays sharp
                # while getting close to the requested apparent size.
                best_zoom = 1
                best_subsample = 1
                best_error = abs(
                    1.0 - scale
                )

                for zoom in range(1, 9):
                    for subsample in range(1, 9):
                        candidate = (
                            zoom / subsample
                        )
                        error = abs(
                            candidate - scale
                        )

                        if error < best_error:
                            best_error = error
                            best_zoom = zoom
                            best_subsample = subsample

                if best_zoom != 1:
                    image = image.zoom(
                        best_zoom,
                        best_zoom,
                    )

                if best_subsample != 1:
                    image = image.subsample(
                        best_subsample,
                        best_subsample,
                    )

            self.starter_sprite_images[slot] = image
            self.starter_sprite_labels[slot].configure(
                image=image,
                text="",
            )
        except tk.TclError:
            self.starter_sprite_images[slot] = None
            self.starter_sprite_labels[slot].configure(
                image="",
                text="Sprite unavailable",
            )

    def _ensure_required_suboption(self, parent_var, mode_var, first_value):
        """
        Required subordinate choices use radio circles.

        When the parent is enabled and no valid choice is currently selected,
        automatically select the first choice. When the parent is disabled,
        clear the mode so reopening the parent consistently starts from the
        first required choice.
        """
        if parent_var.get():
            if not mode_var.get():
                mode_var.set(first_value)
        else:
            mode_var.set("")


    def _update_modes(self):
        pokemon_bst_enabled = self.component_vars["pokemon_bst"].get()
        wild_enabled = self.component_vars["wild"].get()
        static_enabled = self.component_vars["statics"].get()
        trainer_enabled = self.component_vars["trainers"].get()
        moves_enabled = self.component_vars["moves"].get()

        # Required one-of-many choices:
        # selecting the parent immediately selects the first required option
        # when no choice has been made yet.
        self._ensure_required_suboption(
            self.component_vars["pokemon_bst"],
            self.pokemon_bst_mode,
            "same",
        )
        self._ensure_required_suboption(
            self.component_vars["wild"],
            self.wild_mode,
            "mapping",
        )
        self._ensure_required_suboption(
            self.component_vars["statics"],
            self.static_mode,
            "preserve",
        )
        self._ensure_required_suboption(
            self.component_vars["trainers"],
            self.trainer_mode,
            "mapping",
        )
        self._ensure_required_suboption(
            self.difficulty_ai_enabled_var,
            self.difficulty_ai_mode_var,
            "fair",
        )
        self._ensure_required_suboption(
            self.difficulty_levels_enabled_var,
            self.difficulty_level_scope_var,
            "all",
        )
        self._ensure_required_suboption(
            self.difficulty_iv_enabled_var,
            self.difficulty_iv_mode_var,
            "scaled",
        )
        self._ensure_required_suboption(
            self.tm_shop_var,
            self.tm_catalog_generation_var,
            FIRST_TM_CATALOG,
        )

        pokemon_bst_state = (
            "normal"
            if pokemon_bst_enabled
            else "disabled"
        )
        wild_state = "normal" if wild_enabled else "disabled"
        static_state = "normal" if static_enabled else "disabled"
        trainer_state = "normal" if trainer_enabled else "disabled"

        self.pokemon_bst_same.set_state(pokemon_bst_state)
        self.pokemon_bst_stages.set_state(pokemon_bst_state)
        self.pokemon_bst_full.set_state(pokemon_bst_state)

        self.wild_mapping.set_state(wild_state)
        self.wild_slots.set_state(wild_state)
        self.wild_runtime.set_state(wild_state)
        self.wild_allow_special.set_state(wild_state)
        self.wild_similar_bst.set_state(wild_state)
        self.static_preserve.set_state(static_state)
        self.static_full.set_state(static_state)
        self.trainer_mapping.set_state(trainer_state)
        self.trainer_full.set_state(trainer_state)
        self.trainer_allow_special.set_state(trainer_state)
        self.trainer_similar_bst.set_state(trainer_state)
        self.trainer_force_six_major.set_state(trainer_state)
        self.trainer_type_themes.set_state(trainer_state)

        self.difficulty_evolution_stage_option.set_state(trainer_state)

        boss_mega_state = (
            "normal"
            if trainer_enabled and self.game_permanent_megas_var.get()
            else "disabled"
        )
        self.difficulty_boss_mega_option.set_state(boss_mega_state)

        if not trainer_enabled:
            self.difficulty_evolution_stage_var.set(False)

        if boss_mega_state == "disabled":
            self.difficulty_boss_mega_var.set(False)

        difficulty_ai_state = (
            "normal"
            if self.difficulty_ai_enabled_var.get()
            else "disabled"
        )
        self.difficulty_ai_fair.set_state(difficulty_ai_state)
        self.difficulty_ai_omniscient.set_state(difficulty_ai_state)

        difficulty_level_state = (
            "normal"
            if self.difficulty_levels_enabled_var.get()
            else "disabled"
        )
        self.difficulty_levels_all.set_state(difficulty_level_state)
        self.difficulty_levels_major.set_state(difficulty_level_state)
        self.difficulty_level_spinbox.configure(
            state=difficulty_level_state
        )

        difficulty_iv_state = (
            "normal"
            if self.difficulty_iv_enabled_var.get()
            else "disabled"
        )
        self.difficulty_iv_scaled.set_state(difficulty_iv_state)
        self.difficulty_iv_perfect.set_state(difficulty_iv_state)

        tm_catalog_state = (
            "normal"
            if self.tm_shop_var.get()
            else "disabled"
        )

        for option in self.tm_catalog_options:
            option.set_state(tm_catalog_state)

        regional_postcard_state = (
            "normal"
            if self.regional_evolution_postcards_var.get()
            else "disabled"
        )
        self.regional_postcard_shop_option.set_state(
            regional_postcard_state
        )

        if not self.regional_evolution_postcards_var.get():
            self.regional_postcard_shop_var.set(False)

        move_state = "normal" if moves_enabled else "disabled"
        self.move_species_specific_option.set_state(move_state)
        self.move_same_type_bias_option.set_state(move_state)

        if not moves_enabled:
            self.move_species_specific_var.set(False)
            self.move_same_type_bias_var.set(False)

        if not wild_enabled:
            self.wild_allow_special_var.set(False)
            self.wild_similar_bst_var.set(False)

        if not trainer_enabled:
            self.trainer_allow_special_var.set(False)
            self.trainer_similar_bst_var.set(False)
            self.trainer_force_six_major_var.set(False)
            self.trainer_type_themes_var.set(False)

        starter_random_enabled = self.component_vars["starters"].get()

        self.starter_three_stage_option.set_state(
            "normal"
            if starter_random_enabled
            else "disabled"
        )

        if not starter_random_enabled:
            self.starter_three_stage_var.set(False)

        manual_enabled = self.manual_starters_var.get()

        rival_continuity_state = (
            "normal"
            if starter_random_enabled or manual_enabled
            else "disabled"
        )
        self.rival_starter_continuity_option.set_state(
            rival_continuity_state
        )

        if rival_continuity_state == "disabled":
            self.rival_starter_continuity_var.set(False)

        if manual_enabled:
            if not self.manual_starter_box.winfo_manager():
                self.manual_starter_box.pack(
                    fill="x",
                    padx=10,
                    pady=(4, 10),
                )

            for combo in self.starter_combo_boxes:
                combo.configure(
                    state="readonly"
                )

            for slot in range(3):
                self._update_starter_sprite(
                    slot
                )
        else:
            for slot in range(3):
                self._clear_starter_sprite(
                    slot
                )

            if self.manual_starter_box.winfo_manager():
                self.manual_starter_box.pack_forget()

        items_enabled = self.component_vars["items"].get()

        self.game_corner_check.set_state(
            "normal"
            if items_enabled
            else "disabled"
        )

        if not items_enabled:
            self.game_corner_var.set(False)

        receive_items_enabled = self.game_receive_items_var.get()
        receive_item_state = (
            "normal"
            if receive_items_enabled
            else "disabled"
        )

        self.game_perma_repel_option.set_state(receive_item_state)
        self.game_party_heal_option.set_state(receive_item_state)
        self.game_time_turner_option.set_state(receive_item_state)
        self.game_weather_setter_option.set_state(receive_item_state)

        if not receive_items_enabled:
            self.game_perma_repel_var.set(False)
            self.game_party_heal_var.set(False)
            self.game_time_turner_var.set(False)
            self.game_weather_setter_var.set(False)

        build_enabled = self.build_var.get()

        self.clean_build_option.set_state(
            "normal"
            if build_enabled
            else "disabled"
        )

    def _random_seed(self):
        self.seed_var.set(str(random.randrange(2**32)))

    def _append(self, text):
        self.output.configure(state="normal")
        self.output.insert("end", text)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _selected(self):
        return [
            key
            for key, variable in self.component_vars.items()
            if variable.get()
        ]

    def _validate(self, selected):
        manual_starters = self._manual_starter_species()

        standalone_action = any(
            variable.get()
            for variable in (
                self.build_var,
                self.tm_shop_var,
                self.evolution_shop_var,
                self.regional_postcard_shop_var,
                self.mega_shop_var,
                self.game_permadeath_var,
                self.game_hm_free_var,
                self.game_hm_progression_bypass_var,
                self.game_perma_repel_var,
                self.game_cap_candy_var,
                self.game_mom_bonus_var,
                self.game_skip_intro_var,
                self.game_party_heal_var,
                self.game_time_turner_var,
                self.game_weather_setter_var,
                self.game_always_catch_var,
                self.game_force_shiny_var,
                self.game_permanent_megas_var,
                self.regional_evolution_postcards_var,
                self.game_level_caps_var,
                self.game_always_mirage_island_var,
                self.game_event_island_access_var,
                self.all_fossils_var,
                self.difficulty_ai_enabled_var,
                self.difficulty_levels_enabled_var,
                self.difficulty_evolution_stage_var,
                self.difficulty_boss_mega_var,
                self.difficulty_iv_enabled_var,
                self.difficulty_competitive_builds_var,
                self.difficulty_movesets_var,
                self.difficulty_held_items_var,
                self.difficulty_trainer_items_var,
                self.difficulty_force_set_var,
                self.difficulty_disable_bag_var,
                self.rival_starter_continuity_var,
            )
        )

        if (
            not selected
            and manual_starters is None
            and not self.manual_customization_panel.has_customizations()
            and not standalone_action
        ):
            messagebox.showerror(
                "Nothing selected",
                "Select at least one randomiser, game option, store option, "
                "manual starter choice, customised Pokémon or ROM build.",
            )
            return False

        if (
            self.component_vars["starters"].get()
            and self.manual_starters_var.get()
        ):
            messagebox.showerror(
                "Starter mode conflict",
                "Choose either random starters or manual starters, not both.",
            )
            return False

        if (
            self.rival_starter_continuity_var.get()
            and not (
                self.component_vars["starters"].get()
                or self.manual_starters_var.get()
            )
        ):
            messagebox.showerror(
                "Starter mode required",
                "Rival starter continuity requires random or manual starters.",
            )
            return False

        if self.manual_starters_var.get():
            if manual_starters is None:
                messagebox.showerror(
                    "Starter choices required",
                    "Choose all three manual starter Pokémon.",
                )
                return False

            if len(set(manual_starters)) != 3:
                messagebox.showerror(
                    "Duplicate starters",
                    "Choose three different manual starter Pokémon.",
                )
                return False

        if (
            "wild" in selected
            and self.wild_mode.get() not in {"mapping", "slots", "runtime"}
        ):
            messagebox.showerror(
                "Wild mode required",
                "Choose a wild encounter randomisation style.",
            )
            return False

        if (
            "statics" in selected
            and self.static_mode.get() not in {"preserve", "full"}
        ):
            messagebox.showerror(
                "Static encounter mode required",
                "Choose a static Pokémon encounter randomisation style.",
            )
            return False

        if (
            "trainers" in selected
            and self.trainer_mode.get() not in {"mapping", "full"}
        ):
            messagebox.showerror(
                "Trainer mode required",
                "Choose a trainer randomisation style.",
            )
            return False

        if self.difficulty_levels_enabled_var.get():
            try:
                level_boost = int(
                    self.difficulty_level_amount_var.get().strip()
                )
            except ValueError:
                level_boost = 0

            if not 1 <= level_boost <= 20:
                messagebox.showerror(
                    "Invalid trainer level boost",
                    "Additional trainer levels must be a whole number from 1 to 20.",
                )
                return False

        if (
            self.tm_shop_var.get()
            and self.tm_catalog_generation_var.get() not in TM_CATALOGS
        ):
            messagebox.showerror(
                "TM generation required",
                "Choose one TM generation catalogue for the Lilycove store.",
            )
            return False

        return True

    def _start(self):
        if self.running:
            return

        selected = self._selected()

        if not self._validate(selected):
            return

        manual_starters = self._manual_starter_species()

        try:
            manual_customizations = (
                self.manual_customization_panel.get_customizations()
            )
        except RuntimeError as exc:
            messagebox.showerror(
                "Invalid manual customisation",
                str(exc),
            )
            return

        seed_text = self.seed_var.get().strip()

        if seed_text:
            try:
                seed = int(seed_text, 0)
            except ValueError:
                messagebox.showerror(
                    "Invalid seed",
                    "Seed must be an integer or left blank.",
                )
                return
        else:
            seed = random.randrange(2**32)
            self.seed_var.set(str(seed))

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        self._clear()
        self._append(
            f"Randomiser started\nSeed: {seed}\n"
            f"Log file: {self.log_path}\n\n"
        )

        self.running = True
        self.run_button.configure(state="disabled")
        self.status_var.set("Running...")

        thread = threading.Thread(
            target=self._run,
            args=(
                seed,
                selected,
                self.pokemon_bst_mode.get(),
                self.wild_mode.get(),
                self.wild_allow_special_var.get(),
                self.wild_similar_bst_var.get(),
                self.static_mode.get(),
                self.trainer_mode.get(),
                self.trainer_allow_special_var.get(),
                self.trainer_similar_bst_var.get(),
                self.trainer_force_six_major_var.get(),
                self.trainer_type_themes_var.get(),
                self.move_species_specific_var.get(),
                self.move_same_type_bias_var.get(),
                self.build_var.get(),
                self.clean_build_var.get(),
                self.tm_shop_var.get(),
                self.tm_catalog_generation_var.get(),
                self.evolution_shop_var.get(),
                self.regional_postcard_shop_var.get(),
                self.mega_shop_var.get(),
                self.game_corner_var.get(),
                self.all_fossils_var.get(),
                self.fossil_only_replacements_var.get(),
                self.game_permadeath_var.get(),
                self.game_hm_free_var.get(),
                self.game_hm_progression_bypass_var.get(),
                self.game_perma_repel_var.get(),
                self.game_cap_candy_var.get(),
                self.game_mom_bonus_var.get(),
                self.game_skip_intro_var.get(),
                self.game_party_heal_var.get(),
                self.game_time_turner_var.get(),
                self.game_weather_setter_var.get(),
                self.game_always_catch_var.get(),
                self.game_force_shiny_var.get(),
                self.game_permanent_megas_var.get(),
                self.regional_evolution_postcards_var.get(),
                self.game_level_caps_var.get(),
                self.game_always_mirage_island_var.get(),
                self.game_event_island_access_var.get(),
                (
                    self.difficulty_ai_mode_var.get()
                    if self.difficulty_ai_enabled_var.get()
                    else None
                ),
                (
                    int(self.difficulty_level_amount_var.get())
                    if self.difficulty_levels_enabled_var.get()
                    else 0
                ),
                (
                    self.difficulty_level_scope_var.get()
                    if self.difficulty_levels_enabled_var.get()
                    else "all"
                ),
                self.difficulty_evolution_stage_var.get(),
                self.difficulty_boss_mega_var.get(),
                (
                    self.difficulty_iv_mode_var.get()
                    if self.difficulty_iv_enabled_var.get()
                    else None
                ),
                self.difficulty_competitive_builds_var.get(),
                self.difficulty_movesets_var.get(),
                self.difficulty_held_items_var.get(),
                self.difficulty_trainer_items_var.get(),
                self.difficulty_force_set_var.get(),
                self.difficulty_disable_bag_var.get(),
                self.starter_three_stage_var.get(),
                self.rival_starter_continuity_var.get(),
                manual_starters,
                manual_customizations,
            ),
            daemon=True,
        )
        thread.start()

    def _run(
        self,
        seed,
        selected,
        pokemon_bst_mode,
        wild_mode,
        wild_allow_special,
        wild_similar_bst,
        static_mode,
        trainer_mode,
        trainer_allow_special,
        trainer_similar_bst,
        trainer_force_six_major,
        trainer_type_themes,
        move_species_specific,
        move_same_type_bias,
        do_build,
        clean_build,
        add_all_tms,
        tm_catalog_generation,
        add_evolution_items,
        add_regional_postcards,
        add_mega_stones,
        include_game_corner,
        enable_all_fossils,
        fossil_only_replacements,
        game_permadeath,
        game_hm_free,
        game_hm_progression_bypass,
        game_perma_repel,
        game_cap_candy,
        game_mom_bonus,
        game_skip_intro,
        game_party_heal,
        game_time_turner,
        game_weather_setter,
        game_always_catch,
        game_force_shiny,
        game_permanent_megas,
        game_regional_evolutions,
        game_level_caps,
        game_always_mirage_island,
        game_event_island_access,
        difficulty_ai_mode,
        difficulty_level_boost,
        difficulty_level_scope,
        difficulty_evolution_stage,
        difficulty_boss_mega,
        difficulty_iv_mode,
        difficulty_competitive_builds,
        difficulty_movesets,
        difficulty_held_items,
        difficulty_trainer_items,
        difficulty_force_set,
        difficulty_disable_bag,
        starter_three_stage_base,
        rival_starter_continuity,
        manual_starters,
        manual_customizations,
    ):
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

            with self.log_path.open("w", encoding="utf-8") as log_file:
                writer = QueueWriter(self.q, log_file)

                with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                    print("=" * 70)
                    print("POKÉMON EMERALD EXPANSION RANDOMISER")
                    print("=" * 70)
                    print(f"Started: {datetime.now().isoformat()}")
                    print(f"Seed: {seed}")
                    print("Selected components:")

                    for key, label in COMPONENTS:
                        if key in selected:
                            suffix = ""
                            if key == "pokemon_bst":
                                bst_labels = {
                                    "same": "same BST",
                                    "stages": "evolution-stage ranges",
                                    "full": "fully random BST",
                                }
                                suffix = (
                                    " ["
                                    + bst_labels.get(
                                        pokemon_bst_mode,
                                        pokemon_bst_mode,
                                    )
                                    + "]"
                                )
                            elif key == "wild":
                                rules = []
                                if wild_allow_special:
                                    rules.append("special")
                                if wild_similar_bst:
                                    rules.append(
                                        f"±{BST_TOLERANCE} BST"
                                    )
                                rule_text = (
                                    "; " + ", ".join(rules)
                                    if rules
                                    else ""
                                )
                                suffix = f" [{wild_mode}{rule_text}]"
                            elif key == "moves":
                                rules = []
                                if move_species_specific:
                                    rules.append("species-specific pools")
                                if move_same_type_bias:
                                    rules.append("same-type bias")
                                if rules:
                                    suffix = " [" + ", ".join(rules) + "]"
                            elif key == "starters":
                                if starter_three_stage_base:
                                    suffix = " [three-stage base only]"
                            elif key == "statics":
                                suffix = f" [{static_mode}]"
                            elif key == "trainers":
                                rules = []
                                if trainer_allow_special:
                                    rules.append("special")
                                if trainer_similar_bst:
                                    rules.append(
                                        f"±{BST_TOLERANCE} BST"
                                    )
                                if trainer_force_six_major:
                                    rules.append("6-Pokémon major trainers")
                                if trainer_type_themes:
                                    rules.append("Gym/E4 type themes")
                                rule_text = (
                                    "; " + ", ".join(rules)
                                    if rules
                                    else ""
                                )
                                suffix = f" [{trainer_mode}{rule_text}]"
                            print(f"  {label}{suffix}")

                    if manual_starters is not None:
                        print("  Manual starters")

                    if rival_starter_continuity:
                        print("  Rival starter continuity")

                    if manual_customizations:
                        print(
                            "  Manual Pokémon customisation "
                            f"({len(manual_customizations)} Pokémon)"
                        )
                        for species, entry in sorted(manual_customizations.items()):
                            print(
                                f"    {species}: "
                                f"{customization_summary(entry)}"
                            )

                    print()

                    print("Store options:")

                    selected_store_options = []

                    if add_all_tms:
                        selected_store_options.append(
                            "Lilycove TM catalogue: "
                            + TM_CATALOGS[tm_catalog_generation]["label"]
                        )

                    if add_evolution_items:
                        selected_store_options.append(
                            "All evolution items in Lilycove"
                        )

                    if add_regional_postcards:
                        selected_store_options.append(
                            "Regional postcards in Lilycove"
                        )

                    if add_mega_stones:
                        selected_store_options.append(
                            "All Mega Stones in Lilycove"
                        )

                    if selected_store_options:
                        for label in selected_store_options:
                            print("  " + label)
                    else:
                        print("  None")

                    print()
                    print("Fossil options:")

                    selected_fossil_options = [
                        label
                        for enabled, label in (
                            (
                                enable_all_fossils,
                                "All fossil revivals",
                            ),
                            (
                                fossil_only_replacements,
                                "Fossil-only Pokémon for fossil revivals",
                            ),
                        )
                        if enabled
                    ]

                    if selected_fossil_options:
                        for label in selected_fossil_options:
                            print("  " + label)
                    else:
                        print("  None")

                    print()
                    print("Game options:")

                    selected_game_options = [
                        label
                        for enabled, label in (
                            (
                                game_hm_progression_bypass,
                                "Disable progression requirements to use HMs",
                            ),
                            (
                                game_hm_free,
                                "HM use without teaching moves and HM field tools",
                            ),
                            (game_perma_repel, "Receive Perma Repel"),
                            (game_cap_candy, "Level to cap party action"),
                            (game_mom_bonus, "Mom's Running Shoes bonus"),
                            (game_skip_intro, "Skip Littleroot intro"),
                            (game_party_heal, "Receive Party Heal"),
                            (game_time_turner, "Receive Time Turner"),
                            (game_weather_setter, "Receive Weather Setter"),
                            (game_always_catch, "100% catch rate"),
                            (game_permadeath, "Permanent death"),
                            (game_force_shiny, "Force all Pokémon shiny"),
                            (
                                game_permanent_megas,
                                "Permanent Mega Evolutions",
                            ),
                            (
                                game_regional_evolutions,
                                "Regional evolution postcards",
                            ),
                            (game_level_caps, "Level caps"),
                            (
                                game_always_mirage_island,
                                "Mirage Island always present",
                            ),
                            (
                                game_event_island_access,
                                "Event-island access",
                            ),
                        )
                        if enabled
                    ]

                    if selected_game_options:
                        for label in selected_game_options:
                            print("  " + label)
                    else:
                        print("  None")

                    print()
                    print("Difficulty options:")

                    selected_difficulty_options = []

                    if difficulty_ai_mode:
                        selected_difficulty_options.append(
                            "Trainer AI: "
                            + (
                                "fair smart AI"
                                if difficulty_ai_mode == "fair"
                                else "omniscient AI"
                            )
                        )

                    if difficulty_level_boost:
                        selected_difficulty_options.append(
                            f"Trainer levels +{difficulty_level_boost} "
                            f"({difficulty_level_scope})"
                        )

                    if difficulty_iv_mode:
                        selected_difficulty_options.append(
                            "Trainer IVs: "
                            + (
                                "scaled with progress"
                                if difficulty_iv_mode == "scaled"
                                else "perfect"
                            )
                        )

                    selected_difficulty_options.extend(
                        label
                        for enabled, label in (
                            (
                                difficulty_evolution_stage,
                                (
                                    "Evolution-stage rules for late-game "
                                    "trainer Pokémon"
                                ),
                            ),
                            (
                                difficulty_boss_mega,
                                "Permanent Mega aces for later bosses",
                            ),
                            (
                                difficulty_competitive_builds,
                                "Major trainers use competitive EVs/natures",
                            ),
                            (difficulty_movesets, "Improved trainer movesets"),
                            (
                                difficulty_held_items,
                                "Major trainers receive held items",
                            ),
                            (
                                difficulty_trainer_items,
                                "Major trainers receive healing items",
                            ),
                            (difficulty_force_set, "Force Set battle style"),
                            (
                                difficulty_disable_bag,
                                "Disable Bag items in trainer battles",
                            ),
                        )
                        if enabled
                    )

                    if selected_difficulty_options:
                        for label in selected_difficulty_options:
                            print("  " + label)
                    else:
                        print("  None")

                    print()

                    print("Configuring fossil options...")
                    configure_fossil_options(
                        enable_all_fossils=enable_all_fossils,
                        fossil_only_replacements=(
                            fossil_only_replacements
                        ),
                    )
                    print()

                    print("Configuring event-island access...")
                    configure_event_island_access(
                        game_event_island_access
                    )
                    print()

                    print("Configuring trainer difficulty options...")
                    configure_trainer_difficulty_options(
                        evolution_stage_rules=(
                            difficulty_evolution_stage
                        ),
                        boss_permanent_megas=difficulty_boss_mega,
                        trainer_randomisation=("trainers" in selected),
                        permanent_megas=game_permanent_megas,
                        level_boost=difficulty_level_boost,
                        level_scope=difficulty_level_scope,
                    )
                    print()

                    print("Configuring rival starter continuity...")
                    configure_rival_starter_continuity(
                        enabled=rival_starter_continuity,
                        random_starters=("starters" in selected),
                        manual_starters=(manual_starters is not None),
                        evolution_randomisation=("evolutions" in selected),
                    )
                    print()

                    published_rom = master_randomizer.randomize(
                        seed,
                        selected,
                        pokemon_bst_mode=(
                            pokemon_bst_mode
                            if "pokemon_bst" in selected
                            else None
                        ),
                        wild_mode=wild_mode if "wild" in selected else None,
                        wild_allow_special=(
                            wild_allow_special
                            if "wild" in selected
                            else False
                        ),
                        wild_similar_bst=(
                            wild_similar_bst
                            if "wild" in selected
                            else False
                        ),
                        static_mode=static_mode if "statics" in selected else None,
                        fossil_only_replacements=(
                            fossil_only_replacements
                            if "statics" in selected
                            else False
                        ),
                        trainer_mode=trainer_mode if "trainers" in selected else None,
                        trainer_allow_special=(
                            trainer_allow_special
                            if "trainers" in selected
                            else False
                        ),
                        trainer_similar_bst=(
                            trainer_similar_bst
                            if "trainers" in selected
                            else False
                        ),
                        trainer_force_six_major=(
                            trainer_force_six_major
                            if "trainers" in selected
                            else False
                        ),
                        trainer_type_themes=(
                            trainer_type_themes
                            if "trainers" in selected
                            else False
                        ),
                        move_species_specific=(
                            move_species_specific
                            if "moves" in selected
                            else False
                        ),
                        move_same_type_bias=(
                            move_same_type_bias
                            if "moves" in selected
                            else False
                        ),
                        do_build=do_build,
                        clean_build=clean_build,
                        add_all_tms=add_all_tms,
                        tm_catalog_generation=tm_catalog_generation,
                        add_evolution_items=add_evolution_items,
                        add_regional_postcards=add_regional_postcards,
                        add_mega_stones=add_mega_stones,
                        include_game_corner=include_game_corner,
                        enable_all_fossils=enable_all_fossils,
                        game_permadeath=game_permadeath,
                        game_hm_free=game_hm_free,
                        game_hm_progression_bypass=(
                            game_hm_progression_bypass
                        ),
                        game_perma_repel=game_perma_repel,
                        game_cap_candy=game_cap_candy,
                        game_mom_bonus=game_mom_bonus,
                        game_skip_intro=game_skip_intro,
                        game_party_heal=game_party_heal,
                        game_time_turner=game_time_turner,
                        game_weather_setter=game_weather_setter,
                        game_always_catch=game_always_catch,
                        game_force_shiny=game_force_shiny,
                        game_permanent_megas=game_permanent_megas,
                        game_regional_evolutions=(
                            game_regional_evolutions
                        ),
                        game_level_caps=game_level_caps,
                        game_always_mirage_island=(
                            game_always_mirage_island
                        ),
                        difficulty_ai_mode=difficulty_ai_mode,
                        difficulty_level_boost=difficulty_level_boost,
                        difficulty_level_scope=difficulty_level_scope,
                        difficulty_iv_mode=difficulty_iv_mode,
                        difficulty_competitive_builds=(
                            difficulty_competitive_builds
                        ),
                        difficulty_movesets=difficulty_movesets,
                        difficulty_held_items=difficulty_held_items,
                        difficulty_trainer_items=difficulty_trainer_items,
                        difficulty_force_set=difficulty_force_set,
                        difficulty_disable_bag=difficulty_disable_bag,
                        starter_three_stage_base=(
                            starter_three_stage_base
                            if "starters" in selected
                            else False
                        ),
                        rival_starter_continuity=rival_starter_continuity,
                        manual_starters=manual_starters,
                        manual_customizations=manual_customizations,
                    )

            self.q.put(("finished", published_rom))

        except Exception as exc:
            error_text = (
                "\n"
                + "=" * 70
                + "\nRANDOMISER FAILED\n"
                + "=" * 70
                + "\n\n"
                + traceback.format_exc()
                + "\n"
            )

            try:
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as f:
                    f.write(error_text)
            except Exception:
                pass

            self.q.put(("output", error_text))
            self.q.put(("error", str(exc)))

    def _poll_queue(self):
        try:
            while True:
                event, value = self.q.get_nowait()

                if event == "output":
                    self._append(value)

                elif event == "finished":
                    self.running = False
                    self.run_button.configure(state="normal")
                    self.status_var.set("Complete")

                    if value is not None:
                        completion_message = (
                            "ROM created successfully.\n\n"
                            f"Saved to:\n{value}"
                        )
                    else:
                        completion_message = (
                            "Source randomisation completed successfully.\n\n"
                            "No ROM was created because ROM building was "
                            "disabled."
                        )

                    messagebox.showinfo(
                        "Complete",
                        completion_message,
                    )

                elif event == "error":
                    self.running = False
                    self.run_button.configure(state="normal")
                    self.status_var.set("Failed")
                    messagebox.showerror(
                        "Randomiser failed",
                        f"{value}\n\n"
                        "The traceback is visible in the Output / Build Log "
                        f"and saved to:\n{self.log_path}",
                    )

        except queue.Empty:
            pass

        self.after(100, self._poll_queue)


if __name__ == "__main__":
    RandomizerGUI().mainloop()
