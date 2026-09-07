#!/usr/bin/env python3
"""Reject repository text that violates publication hygiene rules."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
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
    "release-manifest.sha256",
}
EMAIL_RE = re.compile(
    r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+\b"
)


def repository_files() -> Iterable[Path]:
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.name in EXCLUDED_NAMES:
            continue
        yield path


def main() -> int:
    errors = []
    for path in repository_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT)
        if "\u2014" in text:
            errors.append("{}: contains an em dash".format(relative))
        if EMAIL_RE.search(text) is not None:
            errors.append("{}: contains an email address".format(relative))
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("repository text checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
