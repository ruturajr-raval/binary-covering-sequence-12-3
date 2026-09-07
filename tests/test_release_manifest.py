#!/usr/bin/env python3
"""Regression tests for release-manifest package boundaries."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "release_manifest.py"
SPEC = importlib.util.spec_from_file_location("release_manifest", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load release_manifest module")
release_manifest = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_manifest)


class PackageBoundaryTests(unittest.TestCase):
    def test_local_toolchains_and_build_artifacts_are_excluded(self) -> None:
        paths = {
            path.relative_to(ROOT).as_posix()
            for path in release_manifest.package_files()
        }

        self.assertFalse(any(path.startswith(".tools/") for path in paths))
        self.assertFalse(
            any(path.startswith(".search-sanitize-bin.dSYM/") for path in paths)
        )
        self.assertFalse(any("/target/" in "/{}/".format(path) for path in paths))
        self.assertFalse(any(path.startswith("build/") for path in paths))
        self.assertFalse(any(path.endswith(".tmp") for path in paths))

    def test_release_sources_remain_included(self) -> None:
        paths = {
            path.relative_to(ROOT).as_posix()
            for path in release_manifest.package_files()
        }

        self.assertIn("README.md", paths)
        self.assertIn(".github/workflows/full-replay.yml", paths)
        self.assertIn("LICENSES/Apache-2.0.txt", paths)
        self.assertIn("evidence/cpp-exhaustive-1-35.jsonl", paths)
        self.assertIn("evidence/result-summary.json", paths)
        self.assertIn("evidence/rust-exhaustive-1-35.json", paths)
        self.assertIn("paper/main.tex", paths)
        self.assertIn("rust-exhaustive/src/lib.rs", paths)
        self.assertIn("src/exhaustive.cpp", paths)
        self.assertIn("src/verify.py", paths)
        self.assertIn("tools/check_exhaustive_evidence.py", paths)
        self.assertIn("tools/check_result_summary.py", paths)
        self.assertIn("tools/check_rust_exhaustive_evidence.py", paths)
        self.assertIn("tools/release_manifest.py", paths)


if __name__ == "__main__":
    unittest.main()
