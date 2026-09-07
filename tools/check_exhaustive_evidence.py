#!/usr/bin/env python3
"""Validate retained exhaustive-search output and its source binding."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[1]
VERIFY_PATH = ROOT / "src" / "verify.py"
VERIFY_SPEC = importlib.util.spec_from_file_location(
    "covering_sequence_verify", VERIFY_PATH
)
if VERIFY_SPEC is None or VERIFY_SPEC.loader is None:
    raise RuntimeError("could not load src/verify.py")
verify_module = importlib.util.module_from_spec(VERIFY_SPEC)
sys.modules[VERIFY_SPEC.name] = verify_module
VERIFY_SPEC.loader.exec_module(verify_module)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SOURCE_RELATIVE = "src/exhaustive.cpp"
KNOWN_EVENTS = {
    "progress",
    "length_summary",
    "summary",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def orbit_count(length: int) -> int:
    fixed_sum = 0
    for reverse in (False, True):
        for offset in range(length):
            permutation = [
                (offset - index) % length
                if reverse
                else (offset + index) % length
                for index in range(length)
            ]
            seen = [False] * length
            cycle_lengths = []
            for start in range(length):
                if seen[start]:
                    continue
                position = start
                cycle_length = 0
                while not seen[position]:
                    seen[position] = True
                    cycle_length += 1
                    position = permutation[position]
                cycle_lengths.append(cycle_length)

            ordinary = 1 << len(cycle_lengths)
            fixed_sum += ordinary
            if all(cycle_length % 2 == 0 for cycle_length in cycle_lengths):
                fixed_sum += ordinary

    group_size = 4 * length
    if fixed_sum % group_size != 0:
        raise AssertionError("Burnside sum is not divisible by group size")
    return fixed_sum // group_size


def load_rows(path: Path) -> List[Dict[str, object]]:
    rows = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="ascii").splitlines(), start=1
    ):
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(
                "invalid JSON at {}:{}: {}".format(
                    path, line_number, error
                )
            )
        if not isinstance(row, dict):
            raise ValueError(
                "JSON row at {}:{} is not an object".format(
                    path, line_number
                )
            )
        rows.append(row)
    return rows


def length_rows(
    rows: Iterable[Dict[str, object]]
) -> Dict[int, Dict[str, object]]:
    result = {}
    for row in rows:
        if row.get("event") != "length_summary":
            continue
        length = row.get("length")
        if not isinstance(length, int):
            raise ValueError("length summary has no integer length")
        if length in result:
            raise ValueError("duplicate length summary {}".format(length))
        result[length] = row
    return result


def check_output(path: Path, minimum_length: int, maximum_length: int) -> None:
    rows = load_rows(path)
    if not rows:
        raise ValueError("evidence log is empty")
    for row in rows:
        event = row.get("event")
        if event not in KNOWN_EVENTS:
            raise ValueError("unexpected evidence event {!r}".format(event))

    summaries = length_rows(rows)
    expected_lengths = set(range(minimum_length, maximum_length + 1))
    if set(summaries) != expected_lengths:
        raise ValueError(
            "length summaries differ: observed {}, expected {}".format(
                sorted(summaries), sorted(expected_lengths)
            )
        )

    expected_scanned = 0
    expected_canonical = 0
    progress_by_length: Dict[int, int] = {}
    for row in rows:
        if row.get("event") != "progress":
            continue
        length = row.get("length")
        scanned = row.get("scanned")
        total = row.get("total")
        elapsed = row.get("elapsed_seconds")
        if length not in expected_lengths:
            raise ValueError("progress row has an unexpected length")
        if total != 1 << length:
            raise ValueError("progress row has an incorrect total")
        if not isinstance(scanned, int) or not 0 <= scanned <= total:
            raise ValueError("progress row has an invalid scanned count")
        if not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise ValueError("progress row has an invalid elapsed time")
        if scanned < progress_by_length.get(length, 0):
            raise ValueError("progress counts are not monotone")
        progress_by_length[length] = scanned

    for length in range(minimum_length, maximum_length + 1):
        row = summaries[length]
        scanned = row.get("scanned")
        canonical = row.get("canonical")
        found_cover = row.get("found_cover")
        best_uncovered = row.get("best_uncovered")
        best_sequence = row.get("best_sequence")

        if scanned != 1 << length:
            raise ValueError(
                "length {} scanned {}, expected {}".format(
                    length, scanned, 1 << length
                )
            )
        expected_orbits = orbit_count(length)
        if canonical != expected_orbits:
            raise ValueError(
                "length {} has {} representatives, expected {}".format(
                    length, canonical, expected_orbits
                )
            )
        if found_cover is not False:
            raise ValueError(
                "length {} unexpectedly reports a cover".format(length)
            )
        if (
            not isinstance(best_uncovered, int)
            or not 1 <= best_uncovered <= 4096
        ):
            raise ValueError(
                "length {} has invalid best-uncovered count".format(length)
            )
        if (
            not isinstance(best_sequence, str)
            or len(best_sequence) != length
            or any(bit not in "01" for bit in best_sequence)
        ):
            raise ValueError(
                "length {} has an invalid best sequence".format(length)
            )
        for key in ("hash_sum", "hash_xor"):
            value = row.get(key)
            if not isinstance(value, int) or not 0 <= value < 1 << 64:
                raise ValueError(
                    "length {} has an invalid {}".format(length, key)
                )
        elapsed = row.get("elapsed_seconds")
        if not isinstance(elapsed, (int, float)) or elapsed < 0:
            raise ValueError(
                "length {} has an invalid elapsed time".format(length)
            )

        verification = verify_module.verify_sequence(
            best_sequence, 12, 3, length
        )
        observed_uncovered = len(verification.uncovered_words)
        if observed_uncovered != best_uncovered:
            raise ValueError(
                "length {} best sequence has {} uncovered words, expected {}".format(
                    length, observed_uncovered, best_uncovered
                )
            )

        expected_scanned += 1 << length
        expected_canonical += expected_orbits

    final_rows = [row for row in rows if row.get("event") == "summary"]
    if len(final_rows) != 1:
        raise ValueError("expected exactly one final summary")
    if rows[-1] is not final_rows[0]:
        raise ValueError("final summary is not the last evidence row")
    final = final_rows[0]
    expected_final = {
        "minimum_length": minimum_length,
        "maximum_length": maximum_length,
        "scanned": expected_scanned,
        "canonical": expected_canonical,
    }
    for key, value in expected_final.items():
        if final.get(key) != value:
            raise ValueError(
                "final {} is {}, expected {}".format(
                    key, final.get(key), value
                )
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
    if metadata.get("source") != SOURCE_RELATIVE:
        raise ValueError("unexpected metadata source path")
    source_path = ROOT / SOURCE_RELATIVE
    if metadata.get("source_sha256") != sha256(source_path):
        raise ValueError("metadata source hash does not match")
    if metadata.get("log_sha256") != sha256(log_path):
        raise ValueError("metadata log hash does not match")
    if metadata.get("log") != log_path.relative_to(ROOT).as_posix():
        raise ValueError("metadata log path does not match")
    if metadata.get("minimum_length") != minimum_length:
        raise ValueError("metadata minimum length does not match")
    if metadata.get("maximum_length") != maximum_length:
        raise ValueError("metadata maximum length does not match")
    if metadata.get("found_cover") is not False:
        raise ValueError("metadata unexpectedly reports a cover")
    threads = metadata.get("threads")
    if not isinstance(threads, int) or threads < 1:
        raise ValueError("metadata has an invalid thread count")
    expected_run_command = [
        "build/exhaustive",
        str(minimum_length),
        str(maximum_length),
        str(threads),
    ]
    if metadata.get("run_command") != expected_run_command:
        raise ValueError("metadata run command does not match")
    expected_compile_command = [
        "c++",
        "-std=c++20",
        "-O3",
        "-DNDEBUG",
        "-Wall",
        "-Wextra",
        "-Wpedantic",
        "-Werror",
        "-pthread",
        SOURCE_RELATIVE,
        "-o",
        "build/exhaustive",
    ]
    if metadata.get("compile_command") != expected_compile_command:
        raise ValueError("metadata compile command does not match")
    if not isinstance(metadata.get("compiler"), str):
        raise ValueError("metadata compiler is missing")
    if metadata.get("binary") != "build/exhaustive":
        raise ValueError("metadata binary path does not match")
    binary_hash = str(metadata.get("binary_sha256"))
    if SHA256_RE.fullmatch(binary_hash) is None:
        raise ValueError("metadata binary hash is invalid")
    if binary_path is not None and sha256(binary_path) != binary_hash:
        raise ValueError("metadata binary hash does not match")

    rows = load_rows(log_path)
    final = next(row for row in rows if row.get("event") == "summary")
    if metadata.get("scanned") != final.get("scanned"):
        raise ValueError("metadata scanned total does not match")
    if metadata.get("canonical") != final.get("canonical"):
        raise ValueError("metadata canonical total does not match")
    expected_checksums = [
        {
            "length": row["length"],
            "hash_sum": row["hash_sum"],
            "hash_xor": row["hash_xor"],
        }
        for row in rows
        if row.get("event") == "length_summary"
    ]
    if metadata.get("length_checksums") != expected_checksums:
        raise ValueError("metadata length checksums do not match")


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
        "verified exhaustive exclusion for lengths {} through {}".format(
            arguments.min_length, arguments.max_length
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
