#!/usr/bin/env python3

import json
import re
import shutil
import subprocess
from pathlib import Path

from runtime_paths import (
    BASELINE_ROOT,
    ROOT,
    WINDOWS_TOOLS_ROOT,
)


HEAL_LOCATIONS_RELATIVE = Path(
    "src/data/heal_locations.json"
)

HEAL_LOCATIONS_FILE = (
    ROOT
    / HEAL_LOCATIONS_RELATIVE
)

BASELINE_HEAL_LOCATIONS_FILE = (
    BASELINE_ROOT
    / HEAL_LOCATIONS_RELATIVE
)


class SourceIntegrityError(RuntimeError):
    pass


def _normalize_newlines(text):
    return (
        text
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )


def _is_valid_json(text):
    try:
        json.loads(text)
        return True
    except json.JSONDecodeError:
        return False


def _repair_split_identifier_strings(text):
    """
    Repair physical line breaks inside identifier-only JSON strings.

    Only strings whose logical value starts with one of the known identifier
    prefixes and otherwise contains uppercase letters, digits, underscores,
    and whitespace are eligible.

    This repairs inserted line breaks, but it does NOT invent missing text.
    """
    prefixes = (
        "MAP_",
        "HEAL_LOCATION_",
        "LOCALID_",
    )

    chars = list(text)
    output = []
    i = 0
    changed = False

    while i < len(chars):
        if chars[i] != '"':
            output.append(chars[i])
            i += 1
            continue

        start = i
        i += 1
        content = []
        escaped = False
        closed = False

        while i < len(chars):
            ch = chars[i]

            if escaped:
                content.append(ch)
                escaped = False
                i += 1
                continue

            if ch == "\\":
                content.append(ch)
                escaped = True
                i += 1
                continue

            if ch == '"':
                closed = True
                break

            content.append(ch)
            i += 1

        if not closed:
            output.append(text[start:])
            break

        raw_content = "".join(content)

        logical = re.sub(
            r"[\r\n\t ]+",
            "",
            raw_content,
        )

        is_identifier = (
            logical.startswith(prefixes)
            and re.fullmatch(
                r"[A-Z0-9_]+",
                logical,
            )
            is not None
        )

        has_physical_break = (
            "\n" in raw_content
            or "\r" in raw_content
        )

        if (
            is_identifier
            and has_physical_break
        ):
            output.append('"')
            output.append(logical)
            output.append('"')
            changed = True
        else:
            output.append(
                text[start:i + 1]
            )

        i += 1

    repaired = "".join(output)

    return repaired if changed else text


def _looks_like_truncated_prefix(
    damaged_text,
    clean_text,
):
    """
    Return True only when the damaged file is literally the beginning of the
    clean file and then stops.

    Trailing whitespace/control line endings are ignored because the observed
    corruption ended immediately after a physical newline.

    This deliberately refuses to overwrite a file whose existing content
    differs from the clean reference before the truncation point.
    """
    damaged = _normalize_newlines(
        damaged_text
    ).rstrip(
        " \t\n"
    )

    clean = _normalize_newlines(
        clean_text
    )

    # Require a substantial matching prefix so a tiny malformed fragment can
    # never trigger a whole-file replacement.
    if len(damaged) < 256:
        return False

    if len(damaged) >= len(clean):
        return False

    return clean.startswith(
        damaged
    )


def _read_valid_reference(path):
    if not path.exists():
        return None

    try:
        text = path.read_text(
            encoding="utf-8",
            errors="strict",
        )
    except (OSError, UnicodeError):
        return None

    if not _is_valid_json(text):
        return None

    return text


def _git_candidates():
    candidates = []

    found = shutil.which("git")
    if found:
        candidates.append(
            Path(found)
        )

    bundled = (
        WINDOWS_TOOLS_ROOT
        / "msys64"
        / "usr"
        / "bin"
        / "git.exe"
    )

    if bundled.exists():
        candidates.append(
            bundled
        )

    unique = []
    seen = set()

    for candidate in candidates:
        key = str(candidate).lower()

        if key in seen:
            continue

        seen.add(key)
        unique.append(candidate)

    return unique


def _read_git_head_reference():
    """
    Read the exact heal_locations.json stored in this checkout's Git HEAD.

    This is only a development fallback. Frozen releases do not include .git;
    their clean copy comes from the packaged baseline instead.
    """
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
                    "HEAD:src/data/heal_locations.json",
                ],
                check=False,
                capture_output=True,
            )
        except OSError:
            continue

        if result.returncode != 0:
            continue

        try:
            text = result.stdout.decode(
                "utf-8"
            )
        except UnicodeDecodeError:
            continue

        if _is_valid_json(text):
            return text

    return None


def _restore_if_truncated(
    damaged_text,
    clean_text,
    source_description,
):
    if clean_text is None:
        return False

    if not _looks_like_truncated_prefix(
        damaged_text,
        clean_text,
    ):
        return False

    HEAL_LOCATIONS_FILE.write_text(
        clean_text,
        encoding="utf-8",
    )

    print()
    print(
        "Source integrity: restored truncated "
        "src/data/heal_locations.json from "
        f"{source_description}."
    )

    return True


def _nearby_error_lines(
    text,
    error,
):
    lines = text.splitlines()

    start = max(
        0,
        error.lineno - 3,
    )
    stop = min(
        len(lines),
        error.lineno + 2,
    )

    return "\n".join(
        f"{index + 1}: {lines[index]!r}"
        for index in range(
            start,
            stop,
        )
    )


def ensure_heal_locations_json_valid():
    """
    Validate heal_locations.json before building.

    Recovery order:
      1. Already-valid JSON: do nothing.
      2. Repair a physical line break inside a complete uppercase identifier.
      3. If the file is genuinely truncated, restore it from the exact packaged
         baseline copy, but only when the damaged file is a literal prefix.
      4. In a development Git checkout, try the same prefix-safe recovery from
         Git HEAD.

    Arbitrary malformed JSON is never silently replaced.
    """
    if not HEAL_LOCATIONS_FILE.exists():
        raise SourceIntegrityError(
            "Missing required source file:\n"
            f"{HEAL_LOCATIONS_FILE}"
        )

    text = HEAL_LOCATIONS_FILE.read_text(
        encoding="utf-8",
        errors="strict",
    )

    try:
        json.loads(text)
        return False
    except json.JSONDecodeError as exc:
        original_error = exc

    repaired = _repair_split_identifier_strings(
        text
    )

    if (
        repaired != text
        and _is_valid_json(repaired)
    ):
        HEAL_LOCATIONS_FILE.write_text(
            repaired,
            encoding="utf-8",
        )

        print()
        print(
            "Source integrity: repaired a split identifier in "
            "src/data/heal_locations.json."
        )

        return True

    baseline_text = _read_valid_reference(
        BASELINE_HEAL_LOCATIONS_FILE
    )

    if _restore_if_truncated(
        text,
        baseline_text,
        "the packaged clean baseline",
    ):
        return True

    git_text = _read_git_head_reference()

    if _restore_if_truncated(
        text,
        git_text,
        "this checkout's Git HEAD",
    ):
        return True

    nearby = _nearby_error_lines(
        text,
        original_error,
    )

    baseline_status = (
        "available"
        if baseline_text is not None
        else "not available"
    )

    git_status = (
        "available"
        if git_text is not None
        else "not available"
    )

    raise SourceIntegrityError(
        "src/data/heal_locations.json is invalid JSON and could not be "
        "recovered safely.\n\n"
        f"JSON error: {original_error}\n\n"
        "Nearby source lines:\n"
        f"{nearby}\n\n"
        "Trusted recovery sources:\n"
        f"  Packaged baseline: {baseline_status}\n"
        f"  Git HEAD: {git_status}\n\n"
        "Automatic restore is intentionally refused unless the damaged file "
        "matches a trusted clean copy exactly up to its truncation point."
    ) from original_error
