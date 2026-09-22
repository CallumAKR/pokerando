"""Convert berry-tree objects into persistent item-ball pickups safely."""

import json
from pathlib import Path

from runtime_paths import BASELINE_ROOT, ROOT


# These flags are explicitly unused in Emerald's flags.h. Keep berry pickups
# inside the unused item-ball region first; the extra unused flags provide
# room for projects which added a handful of new berry trees.
UNUSED_BERRY_FLAGS = tuple(
    f"FLAG_UNUSED_0x{number:03X}"
    for number in (*range(0x493, 0x4F0), *range(0x021, 0x050))
)
TREE_SCRIPT = "BerryTreeScript"
BALL_SCRIPT = "Common_EventScript_FindItem"
RESTORED_FIELDS = (
    "graphics_id",
    "movement_type",
    "trainer_sight_or_berry_tree_id",
    "script",
    "flag",
)


def _write_map(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def restore_berry_item_events():
    """Undo only conversions made here, before positional item restoration."""
    changed = 0
    for path in sorted((ROOT / "data/maps").rglob("map.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        events = data.get("object_events", [])
        converted = [
            (i, event) for i, event in enumerate(events)
            if event.get("flag") in UNUSED_BERRY_FLAGS
            and event.get("script") == BALL_SCRIPT
        ]
        if not converted:
            continue
        baseline = BASELINE_ROOT / path.relative_to(ROOT)
        if not baseline.exists():
            raise RuntimeError(f"Missing berry-tree baseline: {baseline}")
        original = json.loads(baseline.read_text(encoding="utf-8"))
        original_events = original.get("object_events", [])
        for index, event in converted:
            if index >= len(original_events):
                raise RuntimeError(f"Berry-tree event index changed: {path}")
            tree = original_events[index]
            if (tree.get("script") != TREE_SCRIPT
                    or (event.get("x"), event.get("y"), event.get("elevation"))
                    != (tree.get("x"), tree.get("y"), tree.get("elevation"))):
                raise RuntimeError(f"Berry-tree location differs from baseline: {path}")
            for field in RESTORED_FIELDS:
                event[field] = tree[field]
            changed += 1
        _write_map(path, data)
    if changed:
        print(f"Restored {changed} original berry-tree objects.")
    return changed


def berry_flag_for_index(index):
    try:
        flag = UNUSED_BERRY_FLAGS[index]
    except IndexError as exc:
        raise RuntimeError(
            f"Not enough unused pickup flags for berry trees ({index + 1})."
        ) from exc
    header = ROOT / "include/constants/flags.h"
    if not header.exists() or f"#define {flag} " not in header.read_text(encoding="utf-8"):
        raise RuntimeError(f"Missing unused pickup flag {flag} in {header}")
    return flag
