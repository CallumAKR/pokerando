#!/usr/bin/env python3
"""Tk editor for source-species Manual Customisation profiles."""

import copy
import math
import tkinter as tk
from tkinter import messagebox, ttk

from manual_customization import (
    STANDARD_TYPES,
    STAT_FIELDS,
    available_abilities,
    customization_summary,
    normalize_customizations,
)
from starter_helpers import (
    discover_customizable_species,
    find_front_sprite,
)


STAT_LABELS = {
    "baseHP": "HP",
    "baseAttack": "Attack",
    "baseDefense": "Defence",
    "baseSpeed": "Speed",
    "baseSpAttack": "Sp. Atk",
    "baseSpDefense": "Sp. Def",
}


def _constant_label(value, prefix):
    if value in {None, "", f"{prefix}NONE"}:
        return "None"
    return value.removeprefix(prefix).replace("_", " ").title()


class ManualCustomizationPanel(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.customizations = {}
        self.entries = discover_customizable_species()
        self.label_to_species = {label: species for label, species in self.entries}
        self.species_to_label = {species: label for label, species in self.entries}
        self.labels = [label for label, _species in self.entries]
        self.ability_constants = available_abilities()
        self.ability_constant_to_label = {
            value: _constant_label(value, "ABILITY_")
            for value in self.ability_constants
        }
        self.ability_label_to_constant = {
            label: value
            for value, label in self.ability_constant_to_label.items()
        }
        self.ability_labels = tuple(
            self.ability_constant_to_label[value]
            for value in self.ability_constants
        )
        self.type_constant_to_label = {
            value: _constant_label(value, "TYPE_")
            for value in STANDARD_TYPES
        }
        self.type_label_to_constant = {
            label: value
            for value, label in self.type_constant_to_label.items()
        }
        self.type_labels = (
            "None",
            *(self.type_constant_to_label[value] for value in STANDARD_TYPES),
        )
        self.sprite_images = {}

        self.selected_label_var = tk.StringVar(
            value=self.labels[0] if self.labels else ""
        )
        self.random_parent_var = tk.BooleanVar(value=False)
        self.manual_parent_var = tk.BooleanVar(value=False)

        self.random_vars = {
            key: tk.BooleanVar(value=False)
            for key in (
                "abilities",
                "learnset",
                "learnset_species_specific",
                "learnset_same_type_bias",
                "tm_compatibility",
                "evolutions",
                "trade_evolutions",
                "evolution_moves",
                "types",
                "stats",
            )
        }
        self.stats_mode_var = tk.StringVar(value="same")

        self.manual_enabled_vars = {
            key: tk.BooleanVar(value=False)
            for key in ("abilities", "types", "stats")
        }
        first_ability = (
            self.ability_constant_to_label[self.ability_constants[1]]
            if len(self.ability_constants) > 1
            else "None"
        )
        self.ability_vars = [
            tk.StringVar(value=first_ability),
            tk.StringVar(value="None"),
            tk.StringVar(value="None"),
        ]
        self.type_vars = [
            tk.StringVar(value="Normal"),
            tk.StringVar(value="None"),
        ]
        self.stat_vars = {
            field: tk.StringVar(value="50")
            for field in STAT_FIELDS
        }
        self.bst_var = tk.StringVar(value="BST: 300")
        self.editor_status_var = tk.StringVar(
            value="Add this Pokémon even with no child options to protect all listed categories."
        )

        self.random_widgets = []
        self.learnset_modifier_widgets = []
        self.stats_mode_widgets = []
        self.manual_widgets = []
        self.ability_widgets = []
        self.type_widgets = []
        self.stat_widgets = []

        self._build()
        self._update_states()

    def _build(self):
        canvas = tk.Canvas(
            self,
            height=430,
            borderwidth=0,
            highlightthickness=0,
        )
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        body = tk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )

        selector = tk.LabelFrame(body, text="Pokémon selector")
        selector.pack(fill="x", padx=10, pady=(10, 5))
        combo = ttk.Combobox(
            selector,
            textvariable=self.selected_label_var,
            values=self.labels,
            state="readonly",
            height=20,
            width=42,
        )
        combo.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        combo.bind("<<ComboboxSelected>>", self._selected_species_changed)

        editor = tk.Frame(body)
        editor.pack(fill="x", padx=10, pady=5)
        editor.columnconfigure(0, weight=1)
        editor.columnconfigure(1, weight=1)

        random_box = tk.LabelFrame(editor, text="Pokémon randomisation")
        random_box.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        manual_box = tk.LabelFrame(editor, text="Manually edit this Pokémon")
        manual_box.grid(row=0, column=1, sticky="nsew", padx=(5, 0))

        tk.Checkbutton(
            random_box,
            text="Enable selected randomisation for this Pokémon",
            variable=self.random_parent_var,
            command=self._random_parent_changed,
        ).pack(anchor="w", padx=8, pady=(6, 3))

        random_options = (
            ("abilities", "Randomise ability", self._random_abilities_changed),
            ("learnset", "Randomise level-up learnset", self._learnset_changed),
            ("tm_compatibility", "Randomise TM compatibility", None),
            ("evolutions", "Randomise evolution targets", None),
            ("trade_evolutions", "Convert trade evolutions", None),
            ("evolution_moves", "Keep evolution-required moves relearnable", None),
            ("types", "Randomise type", self._random_types_changed),
            ("stats", "Randomise stats", self._random_stats_changed),
        )

        for key, label, command in random_options:
            widget = tk.Checkbutton(
                random_box,
                text=label,
                variable=self.random_vars[key],
                command=command,
            )
            widget.pack(anchor="w", padx=22, pady=1)
            self.random_widgets.append(widget)

            if key == "learnset":
                for modifier, text in (
                    ("learnset_species_specific", "Use species-specific move pool"),
                    ("learnset_same_type_bias", "Bias toward matching types"),
                ):
                    child = tk.Checkbutton(
                        random_box,
                        text=text,
                        variable=self.random_vars[modifier],
                    )
                    child.pack(anchor="w", padx=44, pady=1)
                    self.learnset_modifier_widgets.append(child)

            if key == "stats":
                for value, text in (
                    ("same", "Same BST, different stats"),
                    ("stages", "Evolution-stage BST"),
                    ("full", "Fully random BST"),
                ):
                    radio = tk.Radiobutton(
                        random_box,
                        text=text,
                        variable=self.stats_mode_var,
                        value=value,
                    )
                    radio.pack(anchor="w", padx=44, pady=1)
                    self.stats_mode_widgets.append(radio)

        tk.Checkbutton(
            manual_box,
            text="Enable selected manual edits",
            variable=self.manual_parent_var,
            command=self._manual_parent_changed,
        ).pack(anchor="w", padx=8, pady=(6, 3))

        abilities_check = tk.Checkbutton(
            manual_box,
            text="Set all ability slots",
            variable=self.manual_enabled_vars["abilities"],
            command=self._manual_abilities_changed,
        )
        abilities_check.pack(anchor="w", padx=22, pady=1)
        self.manual_widgets.append(abilities_check)

        ability_row = tk.Frame(manual_box)
        ability_row.pack(fill="x", padx=42, pady=(1, 4))
        for index, variable in enumerate(self.ability_vars):
            combo = ttk.Combobox(
                ability_row,
                textvariable=variable,
                values=self.ability_labels,
                state="readonly",
                width=18,
                height=16,
            )
            combo.grid(row=index, column=0, sticky="ew", pady=1)
            self.ability_widgets.append(combo)
        ability_row.columnconfigure(0, weight=1)

        types_check = tk.Checkbutton(
            manual_box,
            text="Set type(s)",
            variable=self.manual_enabled_vars["types"],
            command=self._manual_types_changed,
        )
        types_check.pack(anchor="w", padx=22, pady=1)
        self.manual_widgets.append(types_check)

        type_row = tk.Frame(manual_box)
        type_row.pack(fill="x", padx=42, pady=(1, 4))
        for index, variable in enumerate(self.type_vars):
            combo = ttk.Combobox(
                type_row,
                textvariable=variable,
                values=self.type_labels,
                state="readonly",
                width=18,
            )
            combo.grid(row=0, column=index, sticky="ew", padx=(0, 4))
            self.type_widgets.append(combo)
            type_row.columnconfigure(index, weight=1)

        stats_check = tk.Checkbutton(
            manual_box,
            text="Set all six base stats",
            variable=self.manual_enabled_vars["stats"],
            command=self._manual_stats_changed,
        )
        stats_check.pack(anchor="w", padx=22, pady=1)
        self.manual_widgets.append(stats_check)

        stats_grid = tk.Frame(manual_box)
        stats_grid.pack(fill="x", padx=42, pady=(1, 2))
        for index, field in enumerate(STAT_FIELDS):
            row = index // 2
            column = (index % 2) * 2
            tk.Label(stats_grid, text=STAT_LABELS[field] + ":").grid(
                row=row,
                column=column,
                sticky="e",
                padx=(0, 3),
                pady=1,
            )
            spin = tk.Spinbox(
                stats_grid,
                from_=1,
                to=250,
                width=5,
                textvariable=self.stat_vars[field],
                command=self._update_bst,
            )
            spin.grid(row=row, column=column + 1, sticky="w", padx=(0, 10))
            spin.bind("<KeyRelease>", self._update_bst)
            self.stat_widgets.append(spin)

        tk.Label(
            manual_box,
            textvariable=self.bst_var,
            font=("TkDefaultFont", 10, "bold"),
        ).pack(anchor="w", padx=42, pady=(2, 6))

        action_row = tk.Frame(body)
        action_row.pack(fill="x", padx=10, pady=(5, 4))
        tk.Button(
            action_row,
            text="Add / Update Pokémon",
            command=self._save_editor,
        ).pack(side="left")
        tk.Button(
            action_row,
            text="Reset editor",
            command=self._reset_editor,
        ).pack(side="left", padx=6)
        tk.Label(
            action_row,
            textvariable=self.editor_status_var,
            anchor="w",
        ).pack(side="left", padx=8)

        list_box = tk.LabelFrame(body, text="Customised Pokémon list")
        list_box.pack(fill="x", padx=10, pady=(4, 10))
        self.list_body = tk.Frame(list_box)
        self.list_body.pack(fill="x", padx=6, pady=6)
        self._rebuild_list()

    def _set_widgets_state(self, widgets, enabled, *, readonly=False):
        state = "readonly" if enabled and readonly else ("normal" if enabled else "disabled")
        for widget in widgets:
            widget.configure(state=state)

    def _random_parent_changed(self):
        if not self.random_parent_var.get():
            for variable in self.random_vars.values():
                variable.set(False)
        self._update_states()

    def _manual_parent_changed(self):
        if not self.manual_parent_var.get():
            for variable in self.manual_enabled_vars.values():
                variable.set(False)
        self._update_states()

    def _random_abilities_changed(self):
        if self.random_vars["abilities"].get():
            self.manual_enabled_vars["abilities"].set(False)
        self._update_states()

    def _learnset_changed(self):
        if not self.random_vars["learnset"].get():
            self.random_vars["learnset_species_specific"].set(False)
            self.random_vars["learnset_same_type_bias"].set(False)
        self._update_states()

    def _random_types_changed(self):
        if self.random_vars["types"].get():
            self.manual_enabled_vars["types"].set(False)
        self._update_states()

    def _random_stats_changed(self):
        if self.random_vars["stats"].get():
            self.manual_enabled_vars["stats"].set(False)
            if self.stats_mode_var.get() not in {"same", "stages", "full"}:
                self.stats_mode_var.set("same")
        self._update_states()

    def _manual_abilities_changed(self):
        if self.manual_enabled_vars["abilities"].get():
            self.random_vars["abilities"].set(False)
        self._update_states()

    def _manual_types_changed(self):
        if self.manual_enabled_vars["types"].get():
            self.random_vars["types"].set(False)
        self._update_states()

    def _manual_stats_changed(self):
        if self.manual_enabled_vars["stats"].get():
            self.random_vars["stats"].set(False)
        self._update_states()

    def _update_states(self):
        random_enabled = self.random_parent_var.get()
        manual_enabled = self.manual_parent_var.get()
        self._set_widgets_state(self.random_widgets, random_enabled)
        self._set_widgets_state(
            self.learnset_modifier_widgets,
            random_enabled and self.random_vars["learnset"].get(),
        )
        self._set_widgets_state(
            self.stats_mode_widgets,
            random_enabled and self.random_vars["stats"].get(),
        )
        self._set_widgets_state(self.manual_widgets, manual_enabled)
        self._set_widgets_state(
            self.ability_widgets,
            manual_enabled and self.manual_enabled_vars["abilities"].get(),
            readonly=True,
        )
        self._set_widgets_state(
            self.type_widgets,
            manual_enabled and self.manual_enabled_vars["types"].get(),
            readonly=True,
        )
        self._set_widgets_state(
            self.stat_widgets,
            manual_enabled and self.manual_enabled_vars["stats"].get(),
        )
        self._update_bst()

    def _update_bst(self, _event=None):
        try:
            values = [int(variable.get()) for variable in self.stat_vars.values()]
            if any(value < 1 or value > 250 for value in values):
                raise ValueError
            self.bst_var.set(f"BST: {sum(values)}")
        except ValueError:
            self.bst_var.set("BST: invalid stats")

    def _editor_entry(self):
        randomize = {
            key: variable.get()
            for key, variable in self.random_vars.items()
            if key != "stats"
        }
        randomize["stats_mode"] = (
            self.stats_mode_var.get()
            if self.random_parent_var.get() and self.random_vars["stats"].get()
            else None
        )
        if not self.random_parent_var.get():
            randomize = {key: False for key in randomize}
            randomize["stats_mode"] = None

        manual = {"abilities": None, "types": None, "stats": None}
        if self.manual_parent_var.get():
            if self.manual_enabled_vars["abilities"].get():
                manual["abilities"] = [
                    self.ability_label_to_constant[variable.get()]
                    for variable in self.ability_vars
                ]
            if self.manual_enabled_vars["types"].get():
                manual["types"] = [
                    (
                        None
                        if variable.get() == "None"
                        else self.type_label_to_constant[variable.get()]
                    )
                    for variable in self.type_vars
                ]
            if self.manual_enabled_vars["stats"].get():
                manual["stats"] = {
                    field: int(variable.get())
                    for field, variable in self.stat_vars.items()
                }

        return {"randomize": randomize, "manual": manual}

    def _save_editor(self):
        species = self.label_to_species.get(self.selected_label_var.get())
        if species is None:
            messagebox.showerror("Pokémon required", "Choose a Pokémon first.")
            return

        try:
            candidate = copy.deepcopy(self.customizations)
            candidate[species] = self._editor_entry()
            candidate = normalize_customizations(candidate)
        except (ValueError, RuntimeError) as exc:
            messagebox.showerror("Invalid customisation", str(exc))
            return

        self.customizations = candidate
        self.editor_status_var.set(
            f"Saved {self.species_to_label.get(species, species)}."
        )
        self._rebuild_list()

    def _selected_species_changed(self, _event=None):
        species = self.label_to_species.get(self.selected_label_var.get())
        if species in self.customizations:
            self._load_entry(species)
        else:
            self._reset_editor(keep_species=True)

    def _load_entry(self, species):
        entry = self.customizations[species]
        randomize = entry["randomize"]
        manual = entry["manual"]
        self.random_parent_var.set(any(randomize.values()))
        for key, variable in self.random_vars.items():
            if key == "stats":
                variable.set(bool(randomize.get("stats_mode")))
            else:
                variable.set(bool(randomize.get(key)))
        self.stats_mode_var.set(randomize.get("stats_mode") or "same")
        self.manual_parent_var.set(any(value is not None for value in manual.values()))
        for key, variable in self.manual_enabled_vars.items():
            variable.set(manual.get(key) is not None)
        if manual.get("abilities") is not None:
            for variable, value in zip(self.ability_vars, manual["abilities"]):
                variable.set(self.ability_constant_to_label[value])
        if manual.get("types") is not None:
            values = list(manual["types"]) + [None, None]
            self.type_vars[0].set(
                self.type_constant_to_label.get(values[0], "None")
            )
            self.type_vars[1].set(
                self.type_constant_to_label.get(values[1], "None")
            )
        if manual.get("stats") is not None:
            for field, variable in self.stat_vars.items():
                variable.set(str(manual["stats"][field]))
        self._update_states()
        self.editor_status_var.set(
            f"Editing {self.species_to_label.get(species, species)}."
        )

    def _reset_editor(self, keep_species=False):
        self.random_parent_var.set(False)
        self.manual_parent_var.set(False)
        for variable in self.random_vars.values():
            variable.set(False)
        for variable in self.manual_enabled_vars.values():
            variable.set(False)
        self.stats_mode_var.set("same")
        self._update_states()
        if not keep_species and self.labels:
            self.selected_label_var.set(self.labels[0])
        self.editor_status_var.set(
            "Editor reset; no saved list entry was removed."
        )

    def _remove_entry(self, species):
        self.customizations.pop(species, None)
        self._rebuild_list()
        self.editor_status_var.set(
            f"Removed {self.species_to_label.get(species, species)}."
        )

    def _edit_entry(self, species):
        self.selected_label_var.set(self.species_to_label.get(species, species))
        self._load_entry(species)

    def _small_sprite(self, species):
        if species in self.sprite_images:
            return self.sprite_images[species]
        path = find_front_sprite(species)
        if path is None:
            self.sprite_images[species] = None
            return None
        try:
            source = tk.PhotoImage(file=str(path))
            frame = min(source.width(), source.height())
            image = tk.PhotoImage(width=frame, height=frame)
            image.tk.call(image, "copy", source, "-from", 0, 0, frame, frame)
            divisor = max(1, math.ceil(max(image.width(), image.height()) / 48))
            if divisor > 1:
                image = image.subsample(divisor, divisor)
            self.sprite_images[species] = image
            return image
        except tk.TclError:
            self.sprite_images[species] = None
            return None

    def _rebuild_list(self):
        for child in self.list_body.winfo_children():
            child.destroy()

        if not self.customizations:
            tk.Label(
                self.list_body,
                text="No customised Pokémon yet.",
                anchor="w",
            ).pack(fill="x")
            return

        for species, entry in sorted(
            self.customizations.items(),
            key=lambda item: self.species_to_label.get(item[0], item[0]),
        ):
            row = tk.Frame(self.list_body, relief="groove", borderwidth=1)
            row.pack(fill="x", pady=2)
            image = self._small_sprite(species)
            tk.Label(
                row,
                image=image or "",
                text="" if image else "No sprite",
                width=8 if not image else 0,
            ).pack(side="left", padx=5, pady=3)
            text = tk.Frame(row)
            text.pack(side="left", fill="x", expand=True, padx=4, pady=3)
            tk.Label(
                text,
                text=self.species_to_label.get(species, species),
                font=("TkDefaultFont", 10, "bold"),
                anchor="w",
            ).pack(fill="x")
            tk.Label(
                text,
                text=customization_summary(entry),
                anchor="w",
                justify="left",
                wraplength=560,
            ).pack(fill="x")
            tk.Button(
                row,
                text="Remove",
                command=lambda chosen=species: self._remove_entry(chosen),
            ).pack(side="right", padx=(2, 5), pady=5)
            tk.Button(
                row,
                text="Edit",
                command=lambda chosen=species: self._edit_entry(chosen),
            ).pack(side="right", padx=2, pady=5)

    def get_customizations(self):
        return normalize_customizations(copy.deepcopy(self.customizations))

    def has_customizations(self):
        return bool(self.customizations)
