#!/usr/bin/env python3
"""
Audit NPC/script-given items without modifying the game.

Run from the pokeemerald-expansion project root:

    py randomizer/audit_npc_gifts.py

The report lists script item-giving commands found under data/maps and
data/scripts, along with an automatic safety classification based on items.h.

This is intentionally an AUDIT ONLY. It changes no files.
"""

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
ITEMS_FILE = ROOT / "src/data/items.h"
SEARCH_ROOTS = (
    ROOT / "data/maps",
    ROOT / "data/scripts",
)

ITEM_HEADER_PATTERN = re.compile(
    r"^\s*\[(ITEM_[A-Z0-9_]+)\]\s*=\s*$",
    re.MULTILINE,
)

COMMAND_PATTERNS = (
    (
        "giveitem",
        re.compile(
            r"^\s*giveitem\s+(ITEM_[A-Z0-9_]+)\b",
            re.MULTILINE,
        ),
    ),
    (
        "msgreceiveditem",
        re.compile(
            r"^\s*msgreceiveditem\s+[^,\n]+,\s*"
            r"(ITEM_[A-Z0-9_]+)\b",
            re.MULTILINE,
        ),
    ),
    (
        "additem",
        re.compile(
            r"^\s*additem\s+(ITEM_[A-Z0-9_]+)\b",
            re.MULTILINE,
        ),
    ),
)


def read_item_info():
    text = ITEMS_FILE.read_text(encoding="utf-8")
    headers = list(ITEM_HEADER_PATTERN.finditer(text))
    info = {}

    for index, match in enumerate(headers):
        item = match.group(1)
        end = (
            headers[index + 1].start()
            if index + 1 < len(headers)
            else len(text)
        )
        block = text[match.start():end]

        pocket_match = re.search(
            r"\.pocket\s*=\s*(POCKET_[A-Z0-9_]+)",
            block,
        )
        sort_match = re.search(
            r"\.sortType\s*=\s*(ITEM_TYPE_[A-Z0-9_]+)",
            block,
        )

        info[item] = {
            "pocket": pocket_match.group(1) if pocket_match else None,
            "sort_type": sort_match.group(1) if sort_match else None,
            "importance": bool(
                re.search(r"\.importance\s*=\s*1\b", block)
            ),
        }

    return info


def classify(item, command, item_info):
    info = item_info.get(item)

    if item == "ITEM_NONE":
        return "PROTECT", "ITEM_NONE"

    if item.startswith("ITEM_HM_") or re.match(r"ITEM_HM\d", item):
        return "PROTECT", "HM"

    if "BADGE" in item:
        return "PROTECT", "Badge/progression"

    if info is None:
        return "REVIEW", "Item definition not found"

    if info["importance"]:
        return "PROTECT", "importance = 1"

    if info["pocket"] == "POCKET_KEY_ITEMS":
        return "PROTECT", "Key Item pocket"

    if info["pocket"] is None:
        return "REVIEW", "No detected pocket"

    if command == "additem":
        return "REVIEW", "additem can be story/transfer logic"

    return "CANDIDATE", "Ordinary non-key gift"


def iter_script_files():
    for root in SEARCH_ROOTS:
        if not root.exists():
            continue

        for path in sorted(root.rglob("*")):
            if (
                path.is_file()
                and path.suffix in {".inc", ".s", ".txt"}
            ):
                yield path


def line_number(text, offset):
    return text.count("\n", 0, offset) + 1


def main():
    item_info = read_item_info()
    rows = []

    for path in iter_script_files():
        text = path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        for command, pattern in COMMAND_PATTERNS:
            for match in pattern.finditer(text):
                item = match.group(1)
                status, reason = classify(
                    item,
                    command,
                    item_info,
                )

                rows.append(
                    (
                        status,
                        item,
                        command,
                        path.relative_to(ROOT).as_posix(),
                        line_number(text, match.start()),
                        reason,
                    )
                )

    rows.sort(
        key=lambda row: (
            {"PROTECT": 0, "REVIEW": 1, "CANDIDATE": 2}[row[0]],
            row[1],
            row[3],
            row[4],
        )
    )

    print("=" * 100)
    print("NPC / SCRIPT ITEM GIFT AUDIT")
    print("=" * 100)
    print()
    print(
        "PROTECT   = automatically unsafe to randomize\n"
        "REVIEW    = needs context/manual decision\n"
        "CANDIDATE = ordinary non-key gift; likely safe to randomize"
    )

    for status in ("PROTECT", "REVIEW", "CANDIDATE"):
        subset = [row for row in rows if row[0] == status]

        print()
        print("=" * 100)
        print(f"{status}: {len(subset)} occurrence(s)")
        print("=" * 100)

        for _, item, command, path, line, reason in subset:
            print(
                f"{item:<32} "
                f"{command:<16} "
                f"{path}:{line:<5} "
                f"[{reason}]"
            )

    unique_candidates = sorted(
        {
            row[1]
            for row in rows
            if row[0] == "CANDIDATE"
        }
    )

    unique_review = sorted(
        {
            row[1]
            for row in rows
            if row[0] == "REVIEW"
        }
    )

    print()
    print("=" * 100)
    print("UNIQUE CANDIDATE ITEMS")
    print("=" * 100)
    for item in unique_candidates:
        print(item)

    print()
    print("=" * 100)
    print("UNIQUE ITEMS NEEDING REVIEW")
    print("=" * 100)
    for item in unique_review:
        print(item)

    print()
    print(
        "No files were modified. Paste this report back into ChatGPT "
        "before enabling NPC gift randomization."
    )


if __name__ == "__main__":
    main()
