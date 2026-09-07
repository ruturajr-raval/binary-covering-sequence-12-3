#!/usr/bin/env python3
"""Write or verify the deterministic project checksum manifest."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Dict, Iterable


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "release-manifest.sha256"
EXCLUDED_PARTS = {
    ".git",
    ".search-sanitize-bin.dSYM",
    ".tools",
    "build",
    "dist",
    "target",
    "__pycache__",
}
EXCLUDED_NAMES = {
    ".DS_Store",
    ".search-test-bin",
    MANIFEST.name,
}
LINE_RE = re.compile(r"^([0-9a-f]{64})  (.+)$")


def package_files() -> Iterable[Path]:
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES:
            continue
        yield path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def current_entries() -> Dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): digest(path)
        for path in package_files()
    }


def write_manifest() -> int:
    entries = current_entries()
    text = "".join(
        "{}  {}\n".format(entries[path], path)
        for path in sorted(entries)
    )
    with MANIFEST.open("w", encoding="ascii", newline="\n") as stream:
        stream.write(text)
    print("wrote {} entries".format(len(entries)))
    return 0


def read_manifest() -> Dict[str, str]:
    if not MANIFEST.is_file():
        raise ValueError("release-manifest.sha256 is missing")
    entries: Dict[str, str] = {}
    for line_number, raw_line in enumerate(
        MANIFEST.read_text(encoding="ascii").splitlines(), start=1
    ):
        match = LINE_RE.fullmatch(raw_line)
        if match is None:
            raise ValueError(
                "invalid manifest line {}".format(line_number)
            )
        expected, relative = match.groups()
        if relative in entries:
            raise ValueError("duplicate manifest path {}".format(relative))
        path = ROOT / relative
        resolved = path.resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError:
            raise ValueError("manifest path escapes project: {}".format(relative))
        if not path.is_file() or path.is_symlink():
            raise ValueError(
                "manifest path is not a regular file: {}".format(relative)
            )
        entries[relative] = expected
    return entries


def check_manifest() -> int:
    expected = read_manifest()
    observed = current_entries()
    errors = []
    missing = sorted(set(observed) - set(expected))
    stale = sorted(set(expected) - set(observed))
    if missing:
        errors.append("manifest is missing: {}".format(", ".join(missing)))
    if stale:
        errors.append("manifest has stale paths: {}".format(", ".join(stale)))
    for relative in sorted(set(expected) & set(observed)):
        if expected[relative] != observed[relative]:
            errors.append("hash mismatch: {}".format(relative))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("verified {} entries".format(len(expected)))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    try:
        if arguments.write:
            return write_manifest()
        return check_manifest()
    except (OSError, UnicodeError, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
