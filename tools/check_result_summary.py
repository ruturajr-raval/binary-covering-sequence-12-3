#!/usr/bin/env python3
"""Validate the exact-result summary against retained evidence."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import check_exhaustive_evidence
import check_rust_exhaustive_evidence


ROOT = Path(__file__).resolve().parents[1]
SUMMARY = ROOT / "evidence" / "result-summary.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_path(relative: str) -> Path:
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def check_file(record: dict, path_key: str, hash_key: str) -> Path:
    path = project_path(record[path_key])
    if sha256(path) != record[hash_key]:
        raise ValueError("{} hash does not match".format(record[path_key]))
    return path


def run_checked(command: list[str]) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise ValueError(
            "{} failed: {}".format(command[0], result.stderr.strip())
        )
    return result.stdout


def verify_native_witness_paths(witness_path: Path, witness: str) -> None:
    cpp_output = run_checked(
        [
            str(ROOT / "build" / "search"),
            "--length",
            "36",
            "--verify",
            witness,
        ]
    )
    cpp_payload = json.loads(cpp_output)
    if (
        cpp_payload.get("valid") is not True
        or cpp_payload.get("covered") != 4096
        or cpp_payload.get("uncovered") != 0
    ):
        raise ValueError("C++ witness verification does not match")

    rust_output = run_checked(
        [
            str(
                ROOT
                / "rust-verifier"
                / "target"
                / "release"
                / "binary-covering-sequence-verifier"
            ),
            "--n",
            "12",
            "--radius",
            "3",
            "--expected-length",
            "36",
            "--file",
            str(witness_path),
        ]
    )
    rust_values = dict(
        line.split("=", 1)
        for line in rust_output.splitlines()
        if "=" in line
    )
    if (
        rust_values.get("result") != "PASS"
        or rust_values.get("covering_radius") != "3"
        or rust_values.get("uncovered_count") != "0"
    ):
        raise ValueError("Rust witness verification does not match")


def main() -> int:
    try:
        summary = json.loads(SUMMARY.read_text(encoding="ascii"))
        if summary.get("schema_version") != 1:
            raise ValueError("unexpected result-summary schema")
        if summary.get("status_date") != "2026-09-07":
            raise ValueError("unexpected result-summary status date")
        if summary.get("theorem") != "L(12,3) = 36":
            raise ValueError("unexpected theorem statement")
        if summary.get("problem") != {
            "alphabet": "binary",
            "window_length": 12,
            "radius": 3,
        }:
            raise ValueError("unexpected problem statement")

        lower = summary["lower_bound"]
        minimum_length = lower["minimum_excluded_length"]
        maximum_length = lower["maximum_excluded_length"]
        if (minimum_length, maximum_length) != (1, 35):
            raise ValueError("unexpected excluded range")

        cpp = summary["implementations"]["cpp"]
        cpp_source = check_file(cpp, "source", "source_sha256")
        cpp_log = check_file(cpp, "log", "log_sha256")
        cpp_metadata = check_file(cpp, "metadata", "metadata_sha256")
        if cpp_source != ROOT / "src" / "exhaustive.cpp":
            raise ValueError("unexpected C++ source path")
        check_exhaustive_evidence.check_output(
            cpp_log, minimum_length, maximum_length
        )
        check_exhaustive_evidence.check_metadata(
            cpp_metadata,
            cpp_log,
            minimum_length,
            maximum_length,
        )

        rust = summary["implementations"]["rust"]
        rust_log = check_file(rust, "log", "log_sha256")
        rust_metadata = check_file(rust, "metadata", "metadata_sha256")
        if rust.get("source") != "rust-exhaustive":
            raise ValueError("unexpected Rust source path")
        check_rust_exhaustive_evidence.check_output(
            rust_log, minimum_length, maximum_length
        )
        check_rust_exhaustive_evidence.check_metadata(
            rust_metadata,
            rust_log,
            minimum_length,
            maximum_length,
        )

        cpp_rows = check_exhaustive_evidence.length_rows(
            check_exhaustive_evidence.load_rows(cpp_log)
        )
        rust_payload = json.loads(rust_log.read_text(encoding="ascii"))
        rust_rows = {
            row["length"]: row for row in rust_payload["results"]
        }
        for length in range(minimum_length, maximum_length + 1):
            if (
                cpp_rows[length]["canonical"]
                != rust_rows[length]["symmetry_representatives"]
            ):
                raise ValueError(
                    "implementation orbit counts differ at length {}".format(
                        length
                    )
                )

        raw_total = sum(1 << length for length in cpp_rows)
        representative_total = sum(
            row["canonical"] for row in cpp_rows.values()
        )
        if lower.get("raw_sequences") != raw_total:
            raise ValueError("raw sequence total does not match")
        if lower.get("symmetry_representatives") != representative_total:
            raise ValueError("representative total does not match")
        if lower.get("covering_representatives") != 0:
            raise ValueError("summary unexpectedly reports a cover")

        upper = summary["upper_bound"]
        witness_path = check_file(
            upper, "sequence_file", "sequence_file_sha256"
        )
        witness = witness_path.read_text(encoding="ascii").strip()
        if witness != upper.get("sequence") or len(witness) != 36:
            raise ValueError("upper-bound witness does not match")
        verification = check_exhaustive_evidence.verify_module.verify_sequence(
            witness, 12, 3, 36
        )
        if (
            verification.covering_radius != upper.get("covering_radius")
            or len(verification.uncovered_words)
            != upper.get("uncovered_targets")
        ):
            raise ValueError("upper-bound verification does not match")
        verify_native_witness_paths(witness_path, witness)

        for record in summary["closest_noncovering_representatives"]:
            row = cpp_rows[record["length"]]
            if (
                record["uncovered_targets"] != row["best_uncovered"]
                or record["sequence"] != row["best_sequence"]
            ):
                raise ValueError(
                    "closest noncover does not match at length {}".format(
                        record["length"]
                    )
                )

        cross_checks = summary["cross_checks"]
        if cross_checks.get("matching_per_length_orbit_counts") != 35:
            raise ValueError("orbit-count cross-check total does not match")
        if cross_checks.get("burnside_counts_match") is not True:
            raise ValueError("Burnside cross-check is not recorded")
        if cross_checks.get("witness_verifiers") != [
            "Python",
            "Rust",
            "C++",
        ]:
            raise ValueError("witness verifier list does not match")
    except (KeyError, OSError, UnicodeError, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1

    print("verified exact-result summary for L(12,3) = 36")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
