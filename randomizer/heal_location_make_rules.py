"""Point the two heal-location Make rules at a stable build snapshot."""

import os
import tempfile
from pathlib import Path


SOURCE = "$(DATA_SRC_SUBDIR)/heal_locations.json"
SNAPSHOT = "$(HEAL_LOCATIONS_JSON)"
DEFAULT = f"HEAL_LOCATIONS_JSON ?= {SOURCE}\n"
TARGETS = (
    (
        "$(DATA_SRC_SUBDIR)/heal_locations.h",
        "$(DATA_SRC_SUBDIR)/heal_locations.json.txt",
    ),
    (
        "include/constants/heal_locations.h",
        "$(DATA_SRC_SUBDIR)/heal_locations.constants.json.txt",
    ),
)


def ensure_heal_locations_snapshot_rules(path: Path) -> bool:
    """Change only the two JSON prerequisites, preserving all custom rules."""
    if not path.is_file():
        raise RuntimeError(f"Missing required Make rules: {path}")

    original = path.read_text(encoding="utf-8")
    updated = original

    for target, template in TARGETS:
        old_rule = f"{target}: {SOURCE} {template}"
        new_rule = f"{target}: {SNAPSHOT} {template}"
        if updated.count(new_rule) == 1:
            continue
        if updated.count(old_rule) != 1:
            raise RuntimeError(
                f"Cannot safely locate the heal-location rule for {target} in {path}"
            )
        updated = updated.replace(old_rule, new_rule, 1)

    if updated.count(DEFAULT) == 0:
        if "HEAL_LOCATIONS_JSON ?=" in updated:
            raise RuntimeError(f"Unexpected heal-location source override in {path}")
        anchor = "AUTO_GEN_TARGETS += $(DATA_SRC_SUBDIR)/heal_locations.h"
        if updated.count(anchor) != 1:
            raise RuntimeError(f"Cannot safely insert heal-location default in {path}")
        updated = updated.replace(anchor, DEFAULT + "\n" + anchor, 1)

    if updated == original:
        return False

    # Replacing the complete small Make fragment avoids exposing a half-written
    # rules file to a parallel Make process or cloud synchronisation client.
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".heal-locations-", suffix=".mk", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(updated)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    print("Build backend: heal-location Make rules now use the validated snapshot.")
    return True
