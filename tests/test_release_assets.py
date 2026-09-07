from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_release_assets.py"
SPEC = importlib.util.spec_from_file_location("build_release_assets", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load release asset module")
release_assets = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release_assets)


class ReleaseAssetTests(unittest.TestCase):
    def test_asset_names_include_version_and_platform(self) -> None:
        names = release_assets.asset_names("1.2.3")
        self.assertEqual(
            names["paper"],
            "binary-covering-sequence-12-3-paper-v1.2.3.pdf",
        )
        self.assertEqual(
            names["source"],
            "binary-covering-sequence-12-3-source-v1.2.3.tar.gz",
        )
        self.assertTrue(names["cpp"].endswith("-macos-arm64"))
        self.assertTrue(names["rust"].endswith("-macos-arm64"))

    def test_checksum_parser_rejects_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            path = Path(directory_text) / "SHA256SUMS"
            digest = "0" * 64
            path.write_text(
                f"{digest}  asset\n{digest}  asset\n",
                encoding="ascii",
            )
            with self.assertRaisesRegex(ValueError, "duplicate"):
                release_assets.read_checksums(path)

    def test_checksum_writer_is_sorted_and_exact(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            directory = Path(directory_text)
            names = {
                "second": "z.bin",
                "first": "a.bin",
            }
            (directory / "z.bin").write_bytes(b"z")
            (directory / "a.bin").write_bytes(b"a")
            release_assets.write_checksums(directory, names)
            lines = (directory / "SHA256SUMS").read_text(
                encoding="ascii"
            ).splitlines()
            expected_a = hashlib.sha256(b"a").hexdigest()
            expected_z = hashlib.sha256(b"z").hexdigest()
            self.assertEqual(
                lines,
                [
                    f"{expected_a}  a.bin",
                    f"{expected_z}  z.bin",
                ],
            )

    def test_project_version_matches_candidate_metadata(self) -> None:
        self.assertEqual(release_assets.project_version(), "0.1.0")


if __name__ == "__main__":
    unittest.main()
