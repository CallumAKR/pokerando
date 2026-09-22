#!/usr/bin/env python3
"""
Install/remove the runtime wild-species reroll hook.

Runtime mode uses Python-preapproved candidate pools. The ROM only chooses from
the already-approved list assigned to the encounter-table source species.

Important lifecycle rule:
    src/wild_encounter.c is backed up exactly before patching and restored
    exactly before the next randomizer run.

This makes the runtime source transformation reversible and prevents cleanup
from deleting/reconstructing ordinary game code.

There is also a one-time legacy repair path for checkouts damaged by older
runtime bundles that removed the original CreateWildMon call.
"""

import re
import shutil
import subprocess
from pathlib import Path

from runtime_paths import (
    BASELINE_ROOT,
    ROOT,
    WINDOWS_TOOLS_ROOT,
)


WILD_SOURCE = ROOT / "src/wild_encounter.c"
GENERATED_HEADER = ROOT / "src/data/randomizer_wild_runtime.h"

# Exact source backup used by the reversible runtime patch.
#
# IMPORTANT: keep this OUTSIDE src/. The Expansion build automatically treats
# .c files under src/ as compilation units, so an earlier implementation that
# stored the backup under src/data/ was accidentally compiled by make.
RUNTIME_STATE_DIR = (
    ROOT
    / ".randomizer_runtime"
)

SOURCE_BACKUP = (
    RUNTIME_STATE_DIR
    / "wild_encounter.c.backup"
)

# Migration path for the short-lived broken implementation. If this exists,
# restore it once and delete it before any build can see it.
LEGACY_SOURCE_BACKUP = (
    ROOT
    / "src/data/randomizer_wild_runtime_source_backup.c"
)

BASELINE_WILD_SOURCE = (
    BASELINE_ROOT
    / "src/wild_encounter.c"
)

INCLUDE_BEGIN = "// RANDOMIZER_RUNTIME_WILD_INCLUDE_BEGIN"
INCLUDE_END = "// RANDOMIZER_RUNTIME_WILD_INCLUDE_END"

# Older marker styles retained only for legacy cleanup/repair.
OLD_CALL_BEGIN = "// RANDOMIZER_RUNTIME_WILD_CALL_BEGIN"
OLD_CALL_END = "// RANDOMIZER_RUNTIME_WILD_CALL_END"
TABLE_CALL_BEGIN = "// RANDOMIZER_RUNTIME_WILD_TABLE_CALL_BEGIN"
TABLE_CALL_END = "// RANDOMIZER_RUNTIME_WILD_TABLE_CALL_END"
FISH_CALL_BEGIN = "// RANDOMIZER_RUNTIME_WILD_FISH_CALL_BEGIN"
FISH_CALL_END = "// RANDOMIZER_RUNTIME_WILD_FISH_CALL_END"

BST_TOLERANCE = 25


# ============================================================
# Low-level C source helpers
# ============================================================

def _remove_marked_block(text, begin, end):
    """
    Remove a marker block only when the entire marked block is randomizer-owned
    injected code.

    This is safe for the include hook and the old CreateWildMon-body assignment
    hook. It must NOT be used for the table/fishing replacement blocks created
    by the first pre-approved-pool implementation.
    """
    while begin in text:
        start = text.index(begin)
        stop = text.find(end, start)

        if stop < 0:
            raise RuntimeError(
                f"Found {begin!r} without matching {end!r} "
                f"in {WILD_SOURCE}."
            )

        stop += len(end)

        if stop < len(text) and text[stop] == "\r":
            stop += 1
        if stop < len(text) and text[stop] == "\n":
            stop += 1

        line_start = text.rfind("\n", 0, start) + 1

        if text[line_start:start].strip() == "":
            start = line_start

        text = text[:start] + text[stop:]

    return text


def _find_matching_brace(text, open_index):
    depth = 0
    i = open_index

    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    escaped = False

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_char = False
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue

        if ch == '"':
            in_string = True
            i += 1
            continue

        if ch == "'":
            in_char = True
            i += 1
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1

            if depth == 0:
                return i

        i += 1

    raise RuntimeError(
        "Could not find matching closing brace in src/wild_encounter.c."
    )


def _find_function_span(text, function_name):
    """
    Locate a real C function definition, not a call site.

    The previous implementation could mistake code such as:

        if (TryGenerateWildMon(...))
        {

    for the TryGenerateWildMon() definition because the call was followed by
    a brace. That is why a clean Expansion reference could report several
    "matches".

    A definition candidate must:
      - have a declaration-like prefix on the same line before the function
        name (for example "static bool8 " or "u16 ");
      - have balanced function parameters;
      - have a '{' immediately after the parameter list, ignoring whitespace.

    Call sites inside if/else/while expressions are therefore excluded.
    """
    name_pattern = re.compile(
        rf"\b{re.escape(function_name)}\s*\("
    )

    candidates = []

    for match in name_pattern.finditer(text):
        line_start = text.rfind(
            "\n",
            0,
            match.start(),
        ) + 1

        declaration_prefix = text[
            line_start:
            match.start()
        ].strip()

        # Real definitions in this source put their return-type/declaration
        # tokens before the function name on the same line. A call in
        # "if (...", "return ...", an assignment, etc. contains punctuation
        # that fails this deliberately conservative declaration check.
        if not declaration_prefix:
            continue

        if (
            re.fullmatch(
                r"(?:[A-Za-z_][A-Za-z0-9_]*|\*|\s)+",
                declaration_prefix,
            )
            is None
        ):
            continue

        prefix_words = declaration_prefix.replace(
            "*",
            " ",
        ).split()

        if not prefix_words:
            continue

        if prefix_words[0] in {
            "if",
            "else",
            "while",
            "for",
            "switch",
            "return",
            "case",
            "sizeof",
        }:
            continue

        open_paren = text.find(
            "(",
            match.start(),
            match.end(),
        )

        close_paren = _find_matching_paren(
            text,
            open_paren,
        )

        after = close_paren + 1

        while (
            after < len(text)
            and text[after].isspace()
        ):
            after += 1

        if (
            after >= len(text)
            or text[after] != "{"
        ):
            continue

        close_brace = _find_matching_brace(
            text,
            after,
        )

        candidates.append(
            (
                line_start,
                close_brace + 1,
            )
        )

    if len(candidates) != 1:
        raise RuntimeError(
            f"Could not uniquely locate {function_name}() definition in "
            f"src/wild_encounter.c. Found {len(candidates)} definition "
            f"candidate(s)."
        )

    return candidates[0]


def _find_matching_paren(text, open_index):
    depth = 0
    i = open_index

    in_string = False
    in_char = False
    escaped = False

    while i < len(text):
        ch = text[i]

        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_char = False
            i += 1
            continue

        if ch == '"':
            in_string = True
        elif ch == "'":
            in_char = True
        elif ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1

            if depth == 0:
                return i

        i += 1

    raise RuntimeError(
        "Could not find matching CreateWildMon closing parenthesis."
    )


def _split_top_level_arguments(argument_text):
    parts = []
    start = 0

    paren = 0
    bracket = 0
    brace = 0

    for i, ch in enumerate(argument_text):
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren -= 1
        elif ch == "[":
            bracket += 1
        elif ch == "]":
            bracket -= 1
        elif ch == "{":
            brace += 1
        elif ch == "}":
            brace -= 1
        elif (
            ch == ","
            and paren == 0
            and bracket == 0
            and brace == 0
        ):
            parts.append(
                argument_text[start:i]
            )
            start = i + 1

    parts.append(
        argument_text[start:]
    )

    return [
        part.strip()
        for part in parts
    ]


def _find_create_wild_mon_calls(function_text):
    """
    Return CreateWildMon call records from one function body.

    This does not care what expression is used for the species argument.
    """
    calls = []

    for match in re.finditer(
        r"\bCreateWildMon\s*\(",
        function_text,
    ):
        open_paren = function_text.find(
            "(",
            match.start(),
            match.end(),
        )
        close_paren = _find_matching_paren(
            function_text,
            open_paren,
        )

        semicolon = close_paren + 1

        while (
            semicolon < len(function_text)
            and function_text[semicolon].isspace()
        ):
            semicolon += 1

        if (
            semicolon >= len(function_text)
            or function_text[semicolon] != ";"
        ):
            continue

        args = _split_top_level_arguments(
            function_text[
                open_paren + 1:
                close_paren
            ]
        )

        if len(args) != 2:
            continue

        line_start = function_text.rfind(
            "\n",
            0,
            match.start(),
        ) + 1

        indent_match = re.match(
            r"[ \t]*",
            function_text[
                line_start:
                match.start()
            ],
        )

        indent = (
            indent_match.group(0)
            if indent_match
            else ""
        )

        calls.append(
            {
                "start": match.start(),
                "end": semicolon + 1,
                "species_arg": args[0],
                "level_arg": args[1],
                "indent": indent,
            }
        )

    return calls


def _function_create_call_count(
    text,
    function_name,
):
    start, end = _find_function_span(
        text,
        function_name,
    )

    return len(
        _find_create_wild_mon_calls(
            text[start:end]
        )
    )


def _replace_function_from_reference(
    current_text,
    reference_text,
    function_name,
):
    current_start, current_end = _find_function_span(
        current_text,
        function_name,
    )

    ref_start, ref_end = _find_function_span(
        reference_text,
        function_name,
    )

    return (
        current_text[:current_start]
        + reference_text[ref_start:ref_end]
        + current_text[current_end:]
    )


# ============================================================
# Trusted clean-reference helpers for one-time legacy repair
# ============================================================

def _read_baseline_reference():
    if not BASELINE_WILD_SOURCE.exists():
        return None

    try:
        return BASELINE_WILD_SOURCE.read_text(
            encoding="utf-8",
        )
    except OSError:
        return None


def _git_candidates():
    candidates = []

    host_git = shutil.which("git")

    if host_git:
        candidates.append(
            Path(host_git)
        )

    bundled_git = (
        WINDOWS_TOOLS_ROOT
        / "msys64"
        / "usr"
        / "bin"
        / "git.exe"
    )

    if bundled_git.exists():
        candidates.append(
            bundled_git
        )

    unique = []
    seen = set()

    for candidate in candidates:
        key = str(candidate).lower()

        if key not in seen:
            seen.add(key)
            unique.append(candidate)

    return unique


def _read_git_head_reference():
    if not (ROOT / ".git").exists():
        return None

    for git_exe in _git_candidates():
        try:
            result = subprocess.run(
                [
                    str(git_exe),
                    "-C",
                    str(ROOT),
                    "show",
                    "HEAD:src/wild_encounter.c",
                ],
                check=False,
                capture_output=True,
            )
        except OSError:
            continue

        if result.returncode != 0:
            continue

        try:
            return result.stdout.decode(
                "utf-8"
            )
        except UnicodeDecodeError:
            continue

    return None


def _get_trusted_reference():
    baseline = _read_baseline_reference()

    if baseline is not None:
        return (
            baseline,
            "the packaged clean baseline",
        )

    git_head = _read_git_head_reference()

    if git_head is not None:
        return (
            git_head,
            "this checkout's Git HEAD",
        )

    return None, None


def _repair_legacy_missing_generation_calls(text):
    """
    Repair the specific source damage caused by the first pre-approved runtime
    cleanup implementation.

    That implementation could delete the CreateWildMon call from
    TryGenerateWildMon and/or GenerateFishingWildMon.

    Only those two whole functions are restored, and only from a trusted exact
    baseline/Git reference.
    """
    needs = []

    for function_name in (
        "TryGenerateWildMon",
        "GenerateFishingWildMon",
    ):
        try:
            count = _function_create_call_count(
                text,
                function_name,
            )
        except RuntimeError:
            count = 0

        if count != 1:
            needs.append(
                function_name
            )

    legacy_markers_present = (
        TABLE_CALL_BEGIN in text
        or FISH_CALL_BEGIN in text
    )

    if not needs and not legacy_markers_present:
        return text, False

    reference, source_description = (
        _get_trusted_reference()
    )

    if reference is None:
        raise RuntimeError(
            "src/wild_encounter.c appears to contain an incomplete/legacy "
            "runtime patch, but no trusted clean reference is available. "
            "A packaged baseline copy or Git checkout is required for safe "
            "repair."
        )

    repaired = text

    # A reference function must itself contain exactly one CreateWildMon call
    # before we trust it for this repair.
    for function_name in (
        "TryGenerateWildMon",
        "GenerateFishingWildMon",
    ):
        if (
            function_name in needs
            or (
                function_name == "TryGenerateWildMon"
                and TABLE_CALL_BEGIN in repaired
            )
            or (
                function_name == "GenerateFishingWildMon"
                and FISH_CALL_BEGIN in repaired
            )
        ):
            if (
                _function_create_call_count(
                    reference,
                    function_name,
                )
                != 1
            ):
                raise RuntimeError(
                    f"Trusted reference does not contain the expected "
                    f"single CreateWildMon call in {function_name}()."
                )

            repaired = _replace_function_from_reference(
                repaired,
                reference,
                function_name,
            )

    print()
    print(
        "Runtime wild source repair: restored encounter-generation "
        f"function(s) from {source_description}."
    )

    return repaired, True


# ============================================================
# Runtime patch cleanup
# ============================================================

def remove_runtime_wild_patch():
    changed = False

    # --------------------------------------------------------
    # Migration cleanup for the broken backup location.
    #
    # This file lives under src/data and therefore gets compiled by make.
    # Restore it exactly, then remove it before doing anything else.
    # --------------------------------------------------------
    if LEGACY_SOURCE_BACKUP.exists():
        if not WILD_SOURCE.exists():
            raise RuntimeError(
                "Legacy runtime wild source backup exists, but "
                "src/wild_encounter.c is missing."
            )

        original = LEGACY_SOURCE_BACKUP.read_text(
            encoding="utf-8"
        )

        WILD_SOURCE.write_text(
            original,
            encoding="utf-8",
        )

        LEGACY_SOURCE_BACKUP.unlink()
        changed = True

        if GENERATED_HEADER.exists():
            GENERATED_HEADER.unlink()

        # A new-format backup should never coexist with the legacy one, but if
        # it does, remove it because the legacy copy is the exact source that
        # preceded the currently installed patch.
        if SOURCE_BACKUP.exists():
            SOURCE_BACKUP.unlink()

        return True

    # Current implementation: exact full-source rollback from outside src/.
    if SOURCE_BACKUP.exists():
        if not WILD_SOURCE.exists():
            raise RuntimeError(
                "Runtime wild source backup exists, but "
                "src/wild_encounter.c is missing."
            )

        original = SOURCE_BACKUP.read_text(
            encoding="utf-8"
        )

        WILD_SOURCE.write_text(
            original,
            encoding="utf-8",
        )

        SOURCE_BACKUP.unlink()
        changed = True

        if GENERATED_HEADER.exists():
            GENERATED_HEADER.unlink()

        # Remove the state directory when empty.
        try:
            RUNTIME_STATE_DIR.rmdir()
        except OSError:
            pass

        return True

    if not WILD_SOURCE.exists():
        if GENERATED_HEADER.exists():
            GENERATED_HEADER.unlink()
            return True

        return False

    text = WILD_SOURCE.read_text(
        encoding="utf-8"
    )

    cleaned = text

    # These two historical blocks were injected-only and are safe to remove.
    cleaned = _remove_marked_block(
        cleaned,
        INCLUDE_BEGIN,
        INCLUDE_END,
    )

    cleaned = _remove_marked_block(
        cleaned,
        OLD_CALL_BEGIN,
        OLD_CALL_END,
    )

    # Never delete legacy table/fishing replacement blocks. Restore the whole
    # affected function from a trusted reference instead.
    cleaned, repaired = (
        _repair_legacy_missing_generation_calls(
            cleaned
        )
    )

    if cleaned != text:
        WILD_SOURCE.write_text(
            cleaned,
            encoding="utf-8",
        )
        changed = True

    if repaired:
        changed = True

    if GENERATED_HEADER.exists():
        GENERATED_HEADER.unlink()
        changed = True

    return changed


# ============================================================
# Generated candidate-pool header
# ============================================================

def _build_generated_header(
    candidate_map,
    seed,
):
    if not candidate_map:
        raise RuntimeError(
            "Runtime wild encounter candidate map is empty."
        )

    pool_index_by_tuple = {}
    pools = []
    source_pool_index = {}

    for original in sorted(candidate_map):
        candidates = tuple(
            dict.fromkeys(
                candidate_map[original]
            )
        )

        if not candidates:
            candidates = (original,)

        if candidates not in pool_index_by_tuple:
            pool_index_by_tuple[
                candidates
            ] = len(pools)
            pools.append(
                candidates
            )

        source_pool_index[
            original
        ] = pool_index_by_tuple[
            candidates
        ]

    pool_blocks = []

    for index, candidates in enumerate(pools):
        species_lines = "\n".join(
            f"    {species},"
            for species in candidates
        )

        pool_blocks.append(
            f"""static const enum Species sRandomizerWildPool{index}[] =
{{
{species_lines}
}};"""
        )

    switch_cases = []

    for original in sorted(
        source_pool_index
    ):
        pool_index = source_pool_index[
            original
        ]

        switch_cases.append(
            f"""    case {original}:
        return sRandomizerWildPool{pool_index}[
            RandomizerWildRandomIndex(
                ARRAY_COUNT(sRandomizerWildPool{pool_index})
            )
        ];"""
        )

    return f"""#ifndef GUARD_RANDOMIZER_WILD_RUNTIME_H
#define GUARD_RANDOMIZER_WILD_RUNTIME_H

// Auto-generated by the randomizer. Do not edit by hand.
#include "random.h"

#define RANDOMIZER_WILD_SEED 0x{seed & 0xFFFFFFFF:08X}u

{chr(10).join(pool_blocks)}

static u32 RandomizerWildRandomIndex(u32 count)
{{
    return (
        Random()
        + (RANDOMIZER_WILD_SEED & 0xFFFFu)
    ) % count;
}}

static enum Species RandomizerChooseWildSpecies(
    enum Species originalSpecies
)
{{
    switch (originalSpecies)
    {{
{chr(10).join(switch_cases)}
    default:
        return originalSpecies;
    }}
}}

#endif // GUARD_RANDOMIZER_WILD_RUNTIME_H
"""


# ============================================================
# Function-local patching
# ============================================================

def _patch_table_function(text):
    start, end = _find_function_span(
        text,
        "TryGenerateWildMon",
    )

    function_text = text[start:end]
    calls = _find_create_wild_mon_calls(
        function_text
    )

    if len(calls) != 1:
        raise RuntimeError(
            "Could not uniquely locate CreateWildMon inside "
            "TryGenerateWildMon(). "
            f"Found {len(calls)} call(s)."
        )

    call = calls[0]
    indent = call["indent"]

    replacement = (
        f"{indent}{TABLE_CALL_BEGIN}\n"
        f"{indent}CreateWildMon(\n"
        f"{indent}    RandomizerChooseWildSpecies(\n"
        f"{indent}        {call['species_arg']}\n"
        f"{indent}    ),\n"
        f"{indent}    {call['level_arg']}\n"
        f"{indent});\n"
        f"{indent}{TABLE_CALL_END}"
    )

    patched_function = (
        function_text[:call["start"]]
        + replacement
        + function_text[call["end"]:]
    )

    return (
        text[:start]
        + patched_function
        + text[end:]
    )


def _patch_fishing_function(text):
    start, end = _find_function_span(
        text,
        "GenerateFishingWildMon",
    )

    function_text = text[start:end]
    calls = _find_create_wild_mon_calls(
        function_text
    )

    if len(calls) != 1:
        raise RuntimeError(
            "Could not uniquely locate CreateWildMon inside "
            "GenerateFishingWildMon(). "
            f"Found {len(calls)} call(s)."
        )

    call = calls[0]
    species_arg = call[
        "species_arg"
    ].strip()

    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*",
        species_arg,
    ):
        raise RuntimeError(
            "GenerateFishingWildMon() does not pass a simple species "
            "variable to CreateWildMon, so the runtime patch refuses to "
            "guess how its return value should be updated."
        )

    indent = call["indent"]

    replacement = (
        f"{indent}{FISH_CALL_BEGIN}\n"
        f"{indent}{species_arg} = RandomizerChooseWildSpecies(\n"
        f"{indent}    {species_arg}\n"
        f"{indent});\n"
        f"{indent}CreateWildMon(\n"
        f"{indent}    {species_arg},\n"
        f"{indent}    {call['level_arg']}\n"
        f"{indent});\n"
        f"{indent}{FISH_CALL_END}"
    )

    patched_function = (
        function_text[:call["start"]]
        + replacement
        + function_text[call["end"]:]
    )

    return (
        text[:start]
        + patched_function
        + text[end:]
    )


def _replace_token_in_function(
    text,
    function_name,
    old,
    new,
    expected_count,
):
    start, end = _find_function_span(
        text,
        function_name,
    )

    function_text = text[start:end]
    count = function_text.count(old)

    if count != expected_count:
        raise RuntimeError(
            f"Could not safely patch {function_name}(): expected "
            f"{expected_count} occurrence(s) of {old!r}, found {count}."
        )

    function_text = function_text.replace(
        old,
        new,
    )

    return (
        text[:start]
        + function_text
        + text[end:]
    )


def _patch_route_override_guards(text):
    """
    In runtime route-table mode, make ordinary map encounters actually use the
    ordinary map encounter table.

    Expansion checks roamers and mass outbreaks BEFORE TryGenerateWildMon().
    Fishing also checks the fixed Feebas special case before the fishing table.
    Those systems can therefore bypass the Python-approved BST pool entirely.

    We deliberately suppress only those override checks while runtime mode is
    installed. Static/scripted encounters remain separate, and the exact
    original source is restored from backup on the next randomizer run.

    The replacement changes only condition expressions, e.g.
    `if (TryStartRoamerEncounter())` becomes
    `if (FALSE && TryStartRoamerEncounter())`.

    No comment markers or extra statements are inserted into if/else chains.
    The exact original source is restored from the rollback backup on the next
    randomizer run.
    """
    guarded = text

    # Standard land/water encounters contain two roamer checks.
    #
    # Only change the condition itself. Do not inject comment-marker lines
    # around an if/else chain: doing so can accidentally comment out the if
    # statement and leave its following `else` orphaned.
    guarded = _replace_token_in_function(
        guarded,
        "StandardWildEncounter",
        "if (TryStartRoamerEncounter())",
        "if (FALSE && TryStartRoamerEncounter())",
        2,
    )

    # Standard land encounters contain one outbreak override.
    guarded = _replace_token_in_function(
        guarded,
        "StandardWildEncounter",
        "if (DoMassOutbreakEncounterTest() == TRUE && SetUpMassOutbreakEncounter(",
        (
            "if (FALSE && DoMassOutbreakEncounterTest() == TRUE "
            "&& SetUpMassOutbreakEncounter("
        ),
        1,
    )

    # Sweet Scent has one roamer check and one outbreak override.
    guarded = _replace_token_in_function(
        guarded,
        "SweetScentWildEncounter",
        "if (TryStartRoamerEncounter())",
        "if (FALSE && TryStartRoamerEncounter())",
        2,
    )

    guarded = _replace_token_in_function(
        guarded,
        "SweetScentWildEncounter",
        "if (DoMassOutbreakEncounterTest() == TRUE)",
        "if (FALSE && DoMassOutbreakEncounterTest() == TRUE)",
        1,
    )

    # Feebas fishing is a fixed species override that bypasses
    # GenerateFishingWildMon(). Runtime table mode should use the fishing table.
    guarded = _replace_token_in_function(
        guarded,
        "FishingWildEncounter",
        "if (CheckFeebasAtCoords(x, y) == TRUE)",
        "if (FALSE && CheckFeebasAtCoords(x, y) == TRUE)",
        1,
    )

    return guarded


def install_runtime_wild_patch(
    candidate_map,
    seed=0,
):
    if not WILD_SOURCE.exists():
        raise RuntimeError(
            "Could not find runtime wild encounter source:\n"
            f"{WILD_SOURCE}"
        )

    # First restore any previous runtime transformation. This also repairs the
    # known legacy deletion bug if necessary.
    remove_runtime_wild_patch()

    original_text = WILD_SOURCE.read_text(
        encoding="utf-8"
    )

    # One more source-integrity check before patching, useful if the checkout
    # was already damaged before this process started.
    original_text, repaired = (
        _repair_legacy_missing_generation_calls(
            original_text
        )
    )

    if repaired:
        WILD_SOURCE.write_text(
            original_text,
            encoding="utf-8",
        )

    include_anchor = (
        '#include "data/wild_encounters.h"'
    )

    if include_anchor not in original_text:
        raise RuntimeError(
            "Could not find wild encounter data include in "
            "src/wild_encounter.c."
        )

    patched = original_text

    include_block = (
        f"{include_anchor}\n"
        f"{INCLUDE_BEGIN}\n"
        '#include "data/randomizer_wild_runtime.h"\n'
        f"{INCLUDE_END}"
    )

    patched = patched.replace(
        include_anchor,
        include_block,
        1,
    )

    patched = _patch_table_function(
        patched
    )

    patched = _patch_fishing_function(
        patched
    )

    # Guarantee that normal-map runtime encounters cannot be replaced by
    # Expansion's roamer/outbreak/Feebas override paths before reaching the
    # approved route-table pools.
    patched = _patch_route_override_guards(
        patched
    )

    # Verify the finished source still contains the two expected game creation
    # calls, now inside our reversible marked sections.
    if TABLE_CALL_BEGIN not in patched:
        raise RuntimeError(
            "Runtime table hook was not installed."
        )

    if FISH_CALL_BEGIN not in patched:
        raise RuntimeError(
            "Runtime fishing hook was not installed."
        )

    # Build everything in memory first. Only after all validation succeeds do
    # we create the exact rollback backup and write the patched source.
    header_text = _build_generated_header(
        candidate_map,
        seed,
    )

    RUNTIME_STATE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    SOURCE_BACKUP.write_text(
        original_text,
        encoding="utf-8",
    )

    try:
        GENERATED_HEADER.write_text(
            header_text,
            encoding="utf-8",
        )

        WILD_SOURCE.write_text(
            patched,
            encoding="utf-8",
        )
    except Exception:
        # Best-effort rollback if the final filesystem write is interrupted.
        WILD_SOURCE.write_text(
            original_text,
            encoding="utf-8",
        )

        if GENERATED_HEADER.exists():
            GENERATED_HEADER.unlink()

        if SOURCE_BACKUP.exists():
            SOURCE_BACKUP.unlink()

        try:
            RUNTIME_STATE_DIR.rmdir()
        except OSError:
            pass

        raise

    return GENERATED_HEADER
