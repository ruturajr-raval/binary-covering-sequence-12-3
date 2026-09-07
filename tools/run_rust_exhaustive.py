#!/usr/bin/env python3
"""Build, run, validate, and bind the Rust exhaustive search."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import check_rust_exhaustive_evidence


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "rust-exhaustive" / "Cargo.toml"
BINARY = (
    ROOT
    / "rust-exhaustive"
    / "target"
    / "release"
    / "binary-covering-sequence-exhaustive"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def project_path(text: str) -> Path:
    path = (ROOT / text).resolve()
    path.relative_to(ROOT.resolve())
    return path


def execute(arguments: argparse.Namespace, log_path: Path, metadata_path: Path) -> None:
    build_command = [
        "cargo",
        "build",
        "--release",
        "--manifest-path",
        str(MANIFEST),
    ]
    subprocess.run(build_command, cwd=ROOT, check=True)
    cargo_version = subprocess.run(
        ["cargo", "--version"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()
    rustc_version = subprocess.run(
        ["rustc", "--version"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.strip()

    run_command = [
        str(BINARY),
        "--range",
        "{}:{}".format(
            arguments.min_length, arguments.max_length
        ),
        "--threads",
        str(arguments.threads),
    ]
    with tempfile.TemporaryDirectory(
        prefix="rust-exhaustive-", dir=ROOT / "build"
    ) as staging_text:
        staging = Path(staging_text)
        temporary_log = staging / log_path.name
        with temporary_log.open(
            "w", encoding="ascii", newline="\n"
        ) as stream:
            subprocess.run(
                run_command,
                cwd=ROOT,
                check=True,
                stdout=stream,
            )
        check_rust_exhaustive_evidence.check_output(
            temporary_log, arguments.min_length, arguments.max_length
        )
        temporary_log.replace(log_path)
        payload = json.loads(log_path.read_text(encoding="ascii"))

        source_hashes = {
            relative: sha256(ROOT / relative)
            for relative in check_rust_exhaustive_evidence.RUST_SOURCES
        }
        metadata = {
            "schema_version": 1,
            "status_date": "2026-09-07",
            "source_sha256": source_hashes,
            "binary": BINARY.relative_to(ROOT).as_posix(),
            "binary_sha256": sha256(BINARY),
            "cargo": cargo_version,
            "rustc": rustc_version,
            "build_command": [
                "cargo",
                "build",
                "--release",
                "--manifest-path",
                "rust-exhaustive/Cargo.toml",
            ],
            "run_command": [
                "rust-exhaustive/target/release/"
                "binary-covering-sequence-exhaustive",
                "--range",
                "{}:{}".format(
                    arguments.min_length, arguments.max_length
                ),
                "--threads",
                str(arguments.threads),
            ],
            "threads": arguments.threads,
            "log": log_path.relative_to(ROOT).as_posix(),
            "log_sha256": sha256(log_path),
            "minimum_length": arguments.min_length,
            "maximum_length": arguments.max_length,
            "result_count": len(payload["results"]),
            "covering_representatives": 0,
        }
        temporary_metadata = staging / metadata_path.name
        temporary_metadata.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        check_rust_exhaustive_evidence.check_metadata(
            temporary_metadata,
            log_path,
            arguments.min_length,
            arguments.max_length,
            BINARY,
        )
        temporary_metadata.replace(metadata_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-length", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=35)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument(
        "--log", default="evidence/rust-exhaustive-1-35.json"
    )
    parser.add_argument(
        "--metadata", default="evidence/rust-exhaustive-1-35.metadata.json"
    )
    arguments = parser.parse_args()

    if (
        arguments.min_length < 1
        or arguments.max_length < arguments.min_length
        or arguments.max_length > 35
    ):
        print("error: invalid length range", file=sys.stderr)
        return 2
    if arguments.threads < 1:
        print("error: threads must be positive", file=sys.stderr)
        return 2

    log_path = project_path(arguments.log)
    metadata_path = project_path(arguments.metadata)
    if log_path == metadata_path:
        print("error: log and metadata paths must differ", file=sys.stderr)
        return 2
    (ROOT / "build").mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = ROOT / "build" / "run-rust-exhaustive.lock"
    with lock_path.open("a", encoding="ascii") as lock_stream:
        fcntl.flock(lock_stream.fileno(), fcntl.LOCK_EX)
        execute(arguments, log_path, metadata_path)
    print(
        "wrote {} and {}".format(
            log_path.relative_to(ROOT),
            metadata_path.relative_to(ROOT),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
