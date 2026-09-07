#!/usr/bin/env python3
"""Exact verifier for cyclic binary covering sequences."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple


class SequenceFormatError(ValueError):
    """Raised when sequence text is empty, ambiguous, or nonbinary."""


@dataclass(frozen=True)
class VerificationResult:
    """Complete exact verification result for one cyclic sequence."""

    sequence: str
    expected_length: int
    n: int
    radius: int
    distinct_windows: Tuple[str, ...]
    covering_radius: int
    uncovered_words: Tuple[str, ...]
    canonical_representative: str

    @property
    def is_covering(self) -> bool:
        return not self.uncovered_words

    def to_dict(self) -> Dict[str, object]:
        return {
            "ambient_word_count": 1 << self.n,
            "canonical_rotation_reversal_complement_representative": (
                self.canonical_representative
            ),
            "covering_radius": self.covering_radius,
            "cyclic_window_count": len(self.sequence),
            "distinct_window_count": len(self.distinct_windows),
            "distinct_windows": list(self.distinct_windows),
            "is_covering": self.is_covering,
            "n": self.n,
            "requested_radius": self.radius,
            "sequence": self.sequence,
            "expected_sequence_length": self.expected_length,
            "sequence_length": len(self.sequence),
            "uncovered_word_count": len(self.uncovered_words),
            "uncovered_words": list(self.uncovered_words),
        }


def parse_sequence(text: str) -> str:
    """Parse bits separated by optional ASCII whitespace."""

    if not isinstance(text, str):
        raise SequenceFormatError("sequence input must be text")

    bits = []
    ascii_whitespace = " \t\n\r\v\f"
    for index, character in enumerate(text):
        if character in ("0", "1"):
            bits.append(character)
        elif character not in ascii_whitespace:
            raise SequenceFormatError(
                "invalid character {!r} at position {}".format(
                    character, index + 1
                )
            )

    if not bits:
        raise SequenceFormatError("sequence input contains no bits")
    return "".join(bits)


def cyclic_windows(sequence: str, n: int) -> Tuple[str, ...]:
    """Return the length-n cyclic window beginning at every sequence position."""

    _require_binary_word(sequence)
    _require_positive_integer(n, "n")
    length = len(sequence)
    return tuple(
        "".join(sequence[(start + offset) % length] for offset in range(n))
        for start in range(length)
    )


def canonical_rotation_reversal_complement(sequence: str) -> str:
    """Return the least rotation under reversal and bit complement."""

    _require_binary_word(sequence)
    complement = sequence.translate(str.maketrans("01", "10"))
    length = len(sequence)
    variants = (
        sequence,
        sequence[::-1],
        complement,
        complement[::-1],
    )
    return min(
        variant[index:] + variant[:index]
        for variant in variants
        for index in range(length)
    )


def verify_sequence(
    sequence: str,
    n: int,
    radius: int,
    expected_length: int,
) -> VerificationResult:
    """Exhaustively verify a cyclic binary ``(n, radius)`` sequence."""

    _require_binary_word(sequence)
    _validate_parameters(n, radius)
    _require_positive_integer(expected_length, "expected_length")
    if len(sequence) != expected_length:
        raise SequenceFormatError(
            "sequence length {} does not match expected length {}".format(
                len(sequence), expected_length
            )
        )

    distinct_windows = tuple(sorted(set(cyclic_windows(sequence, n))))
    window_values = tuple(int(window, 2) for window in distinct_windows)

    covering_radius = 0
    uncovered_words = []
    for value in range(1 << n):
        distance = min(
            _population_count(value ^ window_value)
            for window_value in window_values
        )
        covering_radius = max(covering_radius, distance)
        if distance > radius:
            uncovered_words.append(format(value, "0{}b".format(n)))

    return VerificationResult(
        sequence=sequence,
        expected_length=expected_length,
        n=n,
        radius=radius,
        distinct_windows=distinct_windows,
        covering_radius=covering_radius,
        uncovered_words=tuple(uncovered_words),
        canonical_representative=canonical_rotation_reversal_complement(
            sequence
        ),
    )


def verify_text(
    text: str,
    n: int,
    radius: int,
    expected_length: int,
) -> VerificationResult:
    """Parse and exactly verify one sequence."""

    return verify_sequence(
        parse_sequence(text),
        n,
        radius,
        expected_length,
    )


def format_report(result: VerificationResult) -> str:
    """Format a deterministic, complete human-readable report."""

    lines = [
        "sequence: {}".format(result.sequence),
        "sequence_length: {}".format(len(result.sequence)),
        "expected_sequence_length: {}".format(result.expected_length),
        "n: {}".format(result.n),
        "requested_radius: {}".format(result.radius),
        "is_covering: {}".format(str(result.is_covering).lower()),
        "covering_radius: {}".format(result.covering_radius),
        "cyclic_window_count: {}".format(len(result.sequence)),
        "distinct_window_count: {}".format(len(result.distinct_windows)),
        "ambient_word_count: {}".format(1 << result.n),
        "distinct_windows:",
    ]
    lines.extend("  {}".format(window) for window in result.distinct_windows)
    lines.extend(
        [
            "uncovered_word_count: {}".format(len(result.uncovered_words)),
            "uncovered_words:",
        ]
    )
    if result.uncovered_words:
        lines.extend("  {}".format(word) for word in result.uncovered_words)
    else:
        lines.append("  (none)")
    lines.append(
        "canonical_rotation_reversal_complement_representative: {}".format(
            result.canonical_representative
        )
    )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Exactly verify a cyclic binary covering sequence."
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="sequence file, or - for standard input",
    )
    parser.add_argument("--n", required=True, type=int, help="window length")
    parser.add_argument(
        "-R",
        "--radius",
        required=True,
        type=int,
        help="requested covering radius",
    )
    parser.add_argument(
        "--expected-length",
        required=True,
        type=int,
        help="required cyclic sequence length",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="write the complete report as JSON",
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument("-f", "--file", help="sequence file")
    source_group.add_argument(
        "-s",
        "--sequence",
        help="sequence supplied directly on the command line",
    )
    args = parser.parse_args(argv)

    try:
        if args.input is not None and (
            args.file is not None or args.sequence is not None
        ):
            raise SequenceFormatError(
                "supply only one positional input, --file, or --sequence"
            )
        if args.sequence is not None:
            text = args.sequence
        elif args.file is not None:
            text = Path(args.file).read_text(encoding="ascii")
        elif args.input in (None, "-"):
            text = sys.stdin.read()
        else:
            text = Path(args.input).read_text(encoding="ascii")
        result = verify_text(
            text,
            args.n,
            args.radius,
            args.expected_length,
        )
    except (OSError, UnicodeError, SequenceFormatError, ValueError) as error:
        print("error: {}".format(error), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(format_report(result))
    return 0 if result.is_covering else 1


def _require_binary_word(sequence: str) -> None:
    if not isinstance(sequence, str):
        raise SequenceFormatError("sequence must be text")
    if not sequence:
        raise SequenceFormatError("sequence must not be empty")
    if any(bit not in ("0", "1") for bit in sequence):
        raise SequenceFormatError("sequence must contain only 0 and 1")


def _require_positive_integer(value: int, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("{} must be a positive integer".format(name))


def _validate_parameters(n: int, radius: int) -> None:
    _require_positive_integer(n, "n")
    if isinstance(radius, bool) or not isinstance(radius, int):
        raise ValueError("radius must be an integer")
    if radius < 0 or radius > n:
        raise ValueError("radius must satisfy 0 <= radius <= n")


def _population_count(value: int) -> int:
    # int.bit_count is unavailable on some supported Python 3.9 installations.
    return bin(value).count("1")


if __name__ == "__main__":
    sys.exit(main())
