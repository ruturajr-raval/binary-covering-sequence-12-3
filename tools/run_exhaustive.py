#!/usr/bin/env python3
"""Compile, run, validate, and bind the C++ exhaustive search."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import check_exhaustive_evidence


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src" / "exhaustive.cpp"
BUILD = ROOT / "build" / "exhaustive"
FLAGS = (
    "-std=c++20",
    "-O3",
    "-DNDEBUG",
    "-Wall",
    "-Wextra",
    "-Wpedantic",
    "-Werror",
    "-pthread",
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
    compiler = "c++"
    compile_command = [
        compiler,
        *FLAGS,
        str(SOURCE),
        "-o",
        str(BUILD),
    ]
    subprocess.run(compile_command, cwd=ROOT, check=True)
    compiler_version = subprocess.run(
        [compiler, "--version"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout.splitlines()[0]

    run_command = [
        str(BUILD),
        str(arguments.min_length),
        str(arguments.max_length),
        str(arguments.threads),
    ]
    with tempfile.TemporaryDirectory(
        prefix="cpp-exhaustive-", dir=BUILD.parent
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
        check_exhaustive_evidence.check_output(
            temporary_log, arguments.min_length, arguments.max_length
        )
        temporary_log.replace(log_path)
        rows = check_exhaustive_evidence.load_rows(log_path)
        final = next(row for row in rows if row.get("event") == "summary")

        metadata = {
            "schema_version": 1,
            "status_date": "2026-09-07",
            "source": SOURCE.relative_to(ROOT).as_posix(),
            "source_sha256": sha256(SOURCE),
            "binary": BUILD.relative_to(ROOT).as_posix(),
            "binary_sha256": sha256(BUILD),
            "compiler": compiler_version,
            "compile_command": [
                "c++",
                *FLAGS,
                "src/exhaustive.cpp",
                "-o",
                "build/exhaustive",
            ],
            "run_command": [
                "build/exhaustive",
                str(arguments.min_length),
                str(arguments.max_length),
                str(arguments.threads),
            ],
            "threads": arguments.threads,
            "log": log_path.relative_to(ROOT).as_posix(),
            "log_sha256": sha256(log_path),
            "minimum_length": arguments.min_length,
            "maximum_length": arguments.max_length,
            "scanned": final["scanned"],
            "canonical": final["canonical"],
            "found_cover": False,
            "length_checksums": [
                {
                    "length": row["length"],
                    "hash_sum": row["hash_sum"],
                    "hash_xor": row["hash_xor"],
                }
                for row in rows
                if row.get("event") == "length_summary"
            ],
        }
        temporary_metadata = staging / metadata_path.name
        temporary_metadata.write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n",
            encoding="ascii",
        )
        check_exhaustive_evidence.check_metadata(
            temporary_metadata,
            log_path,
            arguments.min_length,
            arguments.max_length,
            BUILD,
        )
        temporary_metadata.replace(metadata_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-length", type=int, default=1)
    parser.add_argument("--max-length", type=int, default=35)
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument(
        "--log", default="evidence/cpp-exhaustive-1-35.jsonl"
    )
    parser.add_argument(
        "--metadata", default="evidence/cpp-exhaustive-1-35.json"
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
    BUILD.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    lock_path = BUILD.parent / "run-exhaustive.lock"
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
