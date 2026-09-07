from __future__ import annotations

import hashlib
import io
import importlib.util
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "tools" / "build_release_assets.py"
SPEC = importlib.util.spec_from_file_location("build_release_assets", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load release asset module")
release_assets = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = release_assets
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
        self.assertTrue(names["cpp"].endswith("-v1.2.3-macos-arm64"))
        self.assertTrue(names["rust"].endswith("-v1.2.3-macos-arm64"))

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
        self.assertEqual(release_assets.project_version("HEAD"), "0.1.0")

    def test_source_archive_is_deterministic_and_ref_bound(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            directory = Path(directory_text)
            first = directory / "first.tar.gz"
            second = directory / "second.tar.gz"
            version = release_assets.project_version("HEAD")
            release_assets.build_source_archive(
                first,
                version,
                "HEAD",
            )
            release_assets.build_source_archive(
                second,
                version,
                "HEAD",
            )
            self.assertEqual(
                release_assets.sha256(first),
                release_assets.sha256(second),
            )
            release_assets.verify_source_archive(first, version, "HEAD")

    def test_source_archive_rejects_duplicate_members(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            path = Path(directory_text) / "duplicate.tar.gz"
            version = release_assets.project_version("HEAD")
            name = f"{release_assets.PROJECT}-v{version}/duplicate"
            with tarfile.open(path, mode="w:gz") as archive:
                for _ in range(2):
                    info = tarfile.TarInfo(name)
                    info.size = 1
                    archive.addfile(info, io.BytesIO(b"x"))
            with self.assertRaisesRegex(ValueError, "duplicate"):
                release_assets.verify_source_archive(path, version, "HEAD")

    def test_tag_name_must_match_version(self) -> None:
        version = release_assets.project_version("HEAD")
        with self.assertRaisesRegex(ValueError, "does not match"):
            release_assets.validate_tag("HEAD", "v9.9.9", version)

    def test_correct_tag_name_must_point_to_selected_commit(self) -> None:
        with mock.patch.object(
            release_assets,
            "resolve_ref",
            side_effect=["a" * 40, "b" * 40],
        ):
            with self.assertRaisesRegex(ValueError, "expected"):
                release_assets.validate_tag("HEAD", "v0.1.0", "0.1.0")

    def test_paper_binding_rejects_different_pdf(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            directory = Path(directory_text)
            release_paper = directory / "release.pdf"
            expected_paper = directory / "expected.pdf"
            release_paper.write_bytes(b"%PDF-release")
            expected_paper.write_bytes(b"%PDF-expected")
            with self.assertRaisesRegex(ValueError, "does not match"):
                release_assets.verify_paper_binding(
                    release_paper,
                    expected_paper,
                )

    def test_pdf_signature_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            path = Path(directory_text) / "not-a-pdf"
            path.write_bytes(b"plain text")
            with self.assertRaisesRegex(ValueError, "not a PDF"):
                release_assets.verify_pdf(path)

    def test_remote_release_requires_exact_uploaded_asset_set(self) -> None:
        expected = {"one", "two"}
        payload = {
            "tagName": "v0.1.0",
            "isDraft": True,
            "isImmutable": False,
            "assets": [
                {
                    "name": name,
                    "state": "uploaded",
                    "digest": f"sha256:{'0' * 64}",
                    "size": 0,
                }
                for name in sorted(expected)
            ],
        }
        release_assets.validate_remote_release_payload(
            payload,
            "v0.1.0",
            expected,
            "draft",
        )
        payload["assets"].pop()
        with self.assertRaisesRegex(ValueError, "exact asset set"):
            release_assets.validate_remote_release_payload(
                payload,
                "v0.1.0",
                expected,
                "draft",
            )

    def test_remote_release_digests_match_local_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory_text:
            directory = Path(directory_text)
            path = directory / "asset"
            path.write_bytes(b"release asset")
            payload = {
                "tagName": "v0.1.0",
                "isDraft": False,
                "isImmutable": True,
                "assets": [
                    {
                        "name": path.name,
                        "state": "uploaded",
                        "digest": f"sha256:{release_assets.sha256(path)}",
                        "size": path.stat().st_size,
                    }
                ],
            }
            release_assets.validate_remote_release_payload(
                payload,
                "v0.1.0",
                {path.name},
                "published",
                directory,
                require_immutable=True,
            )
            payload["assets"][0]["digest"] = f"sha256:{'0' * 64}"
            with self.assertRaisesRegex(ValueError, "digest mismatch"):
                release_assets.validate_remote_release_payload(
                    payload,
                    "v0.1.0",
                    {path.name},
                    "published",
                    directory,
                    require_immutable=True,
                )


if __name__ == "__main__":
    unittest.main()
