#!/usr/bin/env python3
"""Validate retained Rust exhaustive-search output and source binding."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Optional


ROOT = Path(__file__).resolve().parents[1]
RUST_SOURCES = (
    "rust-exhaustive/Cargo.toml",
    "rust-exhaustive/Cargo.lock",
    "rust-exhaustive/src/lib.rs",
    "rust-exhaustive/src/main.rs",
)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def orbit_count(length: int) -> int:
    rotation_fixed = 0
    complemented_rotation_fixed = 0
    for shift in range(length):
        cycles = math.gcd(length, shift)
        rotation_fixed += 1 << cycles
        if (length // cycles) % 2 == 0:
            complemented_rotation_fixed += 1 << cycles

    if length % 2 == 1:
        reflection_fixed = length * (1 << ((length + 1) // 2))
        complemented_reflection_fixed = 0
    else:
        reflection_fixed = (length // 2) * (
            (1 << (length // 2 + 1)) + (1 << (length // 2))
        )
        complemented_reflection_fixed = (
            length // 2
        ) * (1 << (length // 2))

    fixed_sum = (
        rotation_fixed
        + complemented_rotation_fixed
        + reflection_fixed
        + complemented_reflection_fixed
    )
    group_size = 4 * length
    if fixed_sum % group_size != 0:
        raise AssertionError("Burnside sum is not divisible by group size")
    return fixed_sum // group_size


def check_output(path: Path, minimum_length: int, maximum_length: int) -> None:
    payload = json.loads(path.read_text(encoding="ascii"))
    problem = payload.get("problem")
    if problem != {
        "alphabet": "binary",
        "window_length": 12,
        "radius": 3,
    }:
        raise ValueError("unexpected problem metadata")
    if payload.get("range") != {
        "start": minimum_length,
        "end": maximum_length,
    }:
        raise ValueError("unexpected length range")
    threads = payload.get("threads")
    if not isinstance(threads, int) or threads < 1:
        raise ValueError("unexpected thread count")

    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("results must be a list")
    expected_lengths = list(range(minimum_length, maximum_length + 1))
    observed_lengths = [row.get("length") for row in results]
    if observed_lengths != expected_lengths:
        raise ValueError(
            "observed lengths {}, expected {}".format(
                observed_lengths, expected_lengths
            )
        )

    for row in results:
        length = row["length"]
        if row.get("total_sequences") != 1 << length:
            raise ValueError(
                "length {} has an incomplete raw count".format(length)
            )
        expected_orbits = orbit_count(length)
        if row.get("symmetry_representatives") != expected_orbits:
            raise ValueError(
                "length {} has an incorrect orbit count".format(length)
            )
        if row.get("covering_representatives") != 0:
            raise ValueError(
                "length {} reports a covering representative".format(length)
            )
        if row.get("covering_sequences") != 0:
            raise ValueError(
                "length {} reports a covering sequence".format(length)
            )
        if row.get("witness") is not None:
            raise ValueError(
                "length {} reports an unexpected witness".format(length)
            )
        elapsed = row.get("elapsed_millis")
        if not isinstance(elapsed, int) or elapsed < 0:
            raise ValueError(
                "length {} has an invalid elapsed time".format(length)
            )


def check_metadata(
    path: Path,
    log_path: Path,
    minimum_length: int,
    maximum_length: int,
    binary_path: Optional[Path] = None,
) -> None:
    metadata = json.loads(path.read_text(encoding="ascii"))
    if metadata.get("schema_version") != 1:
        raise ValueError("unexpected metadata schema")
    if metadata.get("status_date") != "2026-09-07":
        raise ValueError("unexpected metadata status date")
    if metadata.get("log_sha256") != sha256(log_path):
        raise ValueError("metadata log hash does not match")
    if metadata.get("log") != log_path.relative_to(ROOT).as_posix():
        raise ValueError("metadata log path does not match")
    if metadata.get("minimum_length") != minimum_length:
        raise ValueError("metadata minimum length does not match")
    if metadata.get("maximum_length") != maximum_length:
        raise ValueError("metadata maximum length does not match")

    observed_sources: Dict[str, str] = {
        relative: sha256(ROOT / relative) for relative in RUST_SOURCES
    }
    if metadata.get("source_sha256") != observed_sources:
        raise ValueError("metadata source hashes do not match")
    if any(
        SHA256_RE.fullmatch(value) is None
        for value in observed_sources.values()
    ):
        raise ValueError("metadata contains an invalid source hash")
    expected_binary = (
        "rust-exhaustive/target/release/"
        "binary-covering-sequence-exhaustive"
    )
    if metadata.get("binary") != expected_binary:
        raise ValueError("metadata binary path does not match")
    binary_hash = str(metadata.get("binary_sha256"))
    if SHA256_RE.fullmatch(binary_hash) is None:
        raise ValueError("metadata binary hash is invalid")
    if binary_path is not None and sha256(binary_path) != binary_hash:
        raise ValueError("metadata binary hash does not match")

    threads = metadata.get("threads")
    if not isinstance(threads, int) or threads < 1:
        raise ValueError("metadata has an invalid thread count")
    expected_build_command = [
        "cargo",
        "build",
        "--release",
        "--manifest-path",
        "rust-exhaustive/Cargo.toml",
    ]
    if metadata.get("build_command") != expected_build_command:
        raise ValueError("metadata build command does not match")
    expected_run_command = [
        "rust-exhaustive/target/release/"
        "binary-covering-sequence-exhaustive",
        "--range",
        "{}:{}".format(minimum_length, maximum_length),
        "--threads",
        str(threads),
    ]
    if metadata.get("run_command") != expected_run_command:
        raise ValueError("metadata run command does not match")
    if not isinstance(metadata.get("cargo"), str):
        raise ValueError("metadata cargo version is missing")
    if not isinstance(metadata.get("rustc"), str):
        raise ValueError("metadata rustc version is missing")

    payload = json.loads(log_path.read_text(encoding="ascii"))
    if payload.get("threads") != threads:
        raise ValueError("metadata thread count does not match the log")
    if metadata.get("result_count") != len(payload["results"]):
        raise ValueError("metadata result count does not match")
    if metadata.get("covering_representatives") != 0:
        raise ValueError("metadata unexpectedly reports a cover")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", required=True)
    parser.add_argument("--metadata")
    parser.add_argument("--binary")
    parser.add_argument("--min-length", required=True, type=int)
    parser.add_argument("--max-length", required=True, type=int)
    arguments = parser.parse_args()

    try:
        log_path = (ROOT / arguments.log).resolve()
        log_path.relative_to(ROOT.resolve())
        check_output(
            log_path, arguments.min_length, arguments.max_length
        )
        if arguments.metadata is not None:
            metadata_path = (ROOT / arguments.metadata).resolve()
            metadata_path.relative_to(ROOT.resolve())
            binary_path = None
            if arguments.binary is not None:
                binary_path = (ROOT / arguments.binary).resolve()
                binary_path.relative_to(ROOT.resolve())
            check_metadata(
                metadata_path,
                log_path,
                arguments.min_length,
                arguments.max_length,
                binary_path,
            )
    except (KeyError, OSError, UnicodeError, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 1

    print(
        "verified Rust exhaustive exclusion for lengths {} through {}".format(
            arguments.min_length, arguments.max_length
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
