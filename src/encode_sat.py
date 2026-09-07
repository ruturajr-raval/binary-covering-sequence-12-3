#!/usr/bin/env python3
"""SAT encoding for cyclic binary covering sequences.

A cyclic binary (n, R) covering sequence of length L is a binary sequence
whose L cyclic windows of length n place every binary n-word within Hamming
distance R of at least one window.

The CNF uses:

* one variable for each sequence bit;
* one coverage variable for each target word and window start; and
* threshold-counter variables for each target and start.

For a fixed target and start, ``ge(i, j)`` is true exactly when at least j of
the first i window positions differ from the target. The coverage variable is
therefore equivalent to ``not ge(n, R + 1)``.

Variables and clauses are allocated in a deterministic order. DIMACS output
is streamed so production instances need not be retained as Python objects.
"""

import argparse
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Mapping, Optional, Sequence
from typing import TextIO, Tuple, Union


Clause = Tuple[int, ...]
Assignment = Mapping[int, bool]
PathLike = Union[str, Path]


def _validate_parameters(n: int, radius: int, length: int) -> None:
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be at least 1")
    if (
        isinstance(radius, bool)
        or not isinstance(radius, int)
        or radius < 0
        or radius > n
    ):
        raise ValueError("radius must satisfy 0 <= radius <= n")
    if isinstance(length, bool) or not isinstance(length, int) or length < 1:
        raise ValueError("length must be at least 1")


def word_bits(word: int, n: int) -> Tuple[int, ...]:
    """Return the n-bit, most-significant-bit-first representation of word."""
    if n < 1:
        raise ValueError("n must be at least 1")
    if word < 0 or word >= (1 << n):
        raise ValueError("word is outside the n-bit range")
    return tuple((word >> (n - 1 - index)) & 1 for index in range(n))


def bits_to_string(bits: Sequence[int]) -> str:
    return "".join(str(bit) for bit in bits)


def parse_sequence(text: str, expected_length: Optional[int] = None) -> Tuple[int, ...]:
    ascii_whitespace = " \t\n\r\v\f"
    stripped = "".join(
        character for character in text if character not in ascii_whitespace
    )
    if not stripped or any(character not in "01" for character in stripped):
        raise ValueError("sequence must contain only binary digits")
    sequence = tuple(int(character) for character in stripped)
    if expected_length is not None and len(sequence) != expected_length:
        raise ValueError(
            "sequence length is {}, expected {}".format(
                len(sequence), expected_length
            )
        )
    return sequence


def _normalized_sequence(sequence: Sequence[int]) -> Tuple[int, ...]:
    normalized = tuple(sequence)
    if not normalized:
        raise ValueError("sequence must be nonempty")
    if any(bit not in (0, 1) for bit in normalized):
        raise ValueError("sequence entries must be 0 or 1")
    return normalized


def cyclic_window(
    sequence: Sequence[int], start: int, n: int
) -> Tuple[int, ...]:
    normalized = _normalized_sequence(sequence)
    if n < 1:
        raise ValueError("n must be at least 1")
    length = len(normalized)
    return tuple(normalized[(start + offset) % length] for offset in range(n))


def hamming_distance(left: Sequence[int], right: Sequence[int]) -> int:
    if len(left) != len(right):
        raise ValueError("Hamming distance requires equal lengths")
    return sum(left_bit != right_bit for left_bit, right_bit in zip(left, right))


def uncovered_word_ids(
    sequence: Sequence[int], n: int, radius: int
) -> Tuple[int, ...]:
    normalized = _normalized_sequence(sequence)
    _validate_parameters(n, radius, len(normalized))
    if radius >= n:
        return ()

    windows = [
        cyclic_window(normalized, start, n) for start in range(len(normalized))
    ]
    uncovered: List[int] = []
    for target in range(1 << n):
        target_bits = word_bits(target, n)
        if not any(
            hamming_distance(window, target_bits) <= radius for window in windows
        ):
            uncovered.append(target)
    return tuple(uncovered)


def is_covering_sequence(sequence: Sequence[int], n: int, radius: int) -> bool:
    return not uncovered_word_ids(sequence, n, radius)


class VariableMap:
    """Compact, reversible description of every DIMACS variable."""

    def __init__(
        self, n: int, radius: int, length: int, symmetry_breaking: bool = True
    ) -> None:
        _validate_parameters(n, radius, length)
        self.n = n
        self.radius = radius
        self.length = length
        self.symmetry_breaking = symmetry_breaking
        self.num_words = 1 << n
        self.threshold = radius + 1

        if radius < n:
            layout: List[Tuple[int, int]] = []
            for prefix_length in range(1, n + 1):
                for threshold in range(
                    1, min(prefix_length, self.threshold) + 1
                ):
                    layout.append((prefix_length, threshold))
            self.counter_layout = tuple(layout)
        else:
            self.counter_layout = ()

        self._counter_offsets = {
            position: offset
            for offset, position in enumerate(self.counter_layout, start=1)
        }
        self.block_size = (
            1 + len(self.counter_layout) if self.counter_layout else 0
        )

    @property
    def num_pair_blocks(self) -> int:
        if not self.counter_layout:
            return 0
        return self.num_words * self.length

    @property
    def num_variables(self) -> int:
        return self.length + self.num_pair_blocks * self.block_size

    def sequence_var(self, index: int) -> int:
        if index < 0 or index >= self.length:
            raise IndexError("sequence index is outside the valid range")
        return index + 1

    def _pair_base(self, target: int, start: int) -> int:
        if not self.counter_layout:
            raise ValueError("distance blocks are not needed when radius >= n")
        if target < 0 or target >= self.num_words:
            raise IndexError("target is outside the n-bit range")
        if start < 0 or start >= self.length:
            raise IndexError("start is outside the sequence range")
        pair_index = target * self.length + start
        return self.length + pair_index * self.block_size

    def cover_var(self, target: int, start: int) -> int:
        return self._pair_base(target, start) + 1

    def counter_var(
        self, target: int, start: int, prefix_length: int, threshold: int
    ) -> int:
        try:
            offset = self._counter_offsets[(prefix_length, threshold)]
        except KeyError:
            raise IndexError("counter position is outside the encoded layout")
        return self._pair_base(target, start) + 1 + offset

    def describe(self, variable: int) -> Dict[str, object]:
        if variable < 1 or variable > self.num_variables:
            raise IndexError("variable is outside the DIMACS range")

        if variable <= self.length:
            index = variable - 1
            return {
                "id": variable,
                "kind": "sequence",
                "index": index,
                "name": "sequence[{}]".format(index),
            }

        relative = variable - self.length - 1
        pair_index, block_offset = divmod(relative, self.block_size)
        target, start = divmod(pair_index, self.length)
        target_text = format(target, "0{}b".format(self.n))

        if block_offset == 0:
            return {
                "id": variable,
                "kind": "cover",
                "target": target,
                "target_bits": target_text,
                "start": start,
                "name": "cover[target={},start={}]".format(target_text, start),
            }

        prefix_length, threshold = self.counter_layout[block_offset - 1]
        return {
            "id": variable,
            "kind": "counter",
            "target": target,
            "target_bits": target_text,
            "start": start,
            "prefix_length": prefix_length,
            "threshold": threshold,
            "name": (
                "ge[target={},start={},prefix={},threshold={}]".format(
                    target_text, start, prefix_length, threshold
                )
            ),
        }

    def to_dict(self) -> Dict[str, object]:
        pair_blocks: Optional[Dict[str, object]]
        if self.counter_layout:
            pair_blocks = {
                "first_variable": self.length + 1,
                "count": self.num_pair_blocks,
                "block_size": self.block_size,
                "pair_index": "target * length + start",
                "target_order": "integer order, bits are most-significant first",
                "window_position": "sequence[(start + position) mod length]",
                "cover_meaning": (
                    "the cyclic window at start has Hamming distance at most "
                    "radius from target"
                ),
                "counter_meaning": (
                    "ge(prefix_length, threshold) is true exactly when the "
                    "prefix has at least threshold mismatches"
                ),
                "offsets": {
                    "cover": 0,
                    "counters": [
                        {
                            "offset": offset,
                            "prefix_length": prefix_length,
                            "threshold": threshold,
                        }
                        for offset, (prefix_length, threshold) in enumerate(
                            self.counter_layout, start=1
                        )
                    ],
                },
            }
        else:
            pair_blocks = None

        return {
            "format": "binary-covering-sequence-variable-map-v1",
            "parameters": {
                "n": self.n,
                "radius": self.radius,
                "length": self.length,
                "symmetry_breaking": self.symmetry_breaking,
            },
            "num_variables": self.num_variables,
            "sequence": {
                "first_variable": 1,
                "count": self.length,
                "formula": "sequence[i] = 1 + i",
            },
            "pair_blocks": pair_blocks,
            "symmetry": (
                {
                    "clause": [-self.sequence_var(0)],
                    "reason": "binary complement maps every cover to a cover",
                }
                if self.symmetry_breaking
                else None
            ),
        }


@dataclass(frozen=True)
class SemanticCheck:
    sequence: Tuple[int, ...]
    covers_all_words: bool
    symmetry_ok: bool
    uncovered_words: Tuple[int, ...]
    cnf_status: str

    @property
    def semantic_valid(self) -> bool:
        return self.covers_all_words and self.symmetry_ok

    @property
    def valid(self) -> bool:
        return self.semantic_valid and self.cnf_status == "satisfied"

    def to_dict(self, n: int) -> Dict[str, object]:
        return {
            "sequence": bits_to_string(self.sequence),
            "covers_all_words": self.covers_all_words,
            "symmetry_ok": self.symmetry_ok,
            "cnf_status": self.cnf_status,
            "uncovered_words": [
                format(word, "0{}b".format(n)) for word in self.uncovered_words
            ],
            "semantic_valid": self.semantic_valid,
            "valid": self.valid,
        }


class SATEncoding:
    """Deterministic CNF encoding and its semantic support functions."""

    def __init__(
        self, n: int, radius: int, length: int, symmetry_breaking: bool = True
    ) -> None:
        self.variables = VariableMap(n, radius, length, symmetry_breaking)
        self.n = n
        self.radius = radius
        self.length = length
        self.symmetry_breaking = symmetry_breaking

        counter_clause_count = 0
        for prefix_length, threshold in self.variables.counter_layout:
            if prefix_length == 1:
                counter_clause_count += 2
            elif threshold == 1 or threshold == prefix_length:
                counter_clause_count += 3
            else:
                counter_clause_count += 4
        self._counter_clause_count = counter_clause_count

    @property
    def num_variables(self) -> int:
        return self.variables.num_variables

    @property
    def num_clauses(self) -> int:
        symmetry_clauses = 1 if self.symmetry_breaking else 0
        if self.radius >= self.n:
            return symmetry_clauses
        clauses_per_pair = self._counter_clause_count + 2
        return symmetry_clauses + (1 << self.n) * (
            self.length * clauses_per_pair + 1
        )

    def _mismatch_literal(
        self, target_bits: Sequence[int], start: int, position: int
    ) -> int:
        sequence_variable = self.variables.sequence_var(
            (start + position) % self.length
        )
        return sequence_variable if target_bits[position] == 0 else -sequence_variable

    def _counter_clauses(
        self, target: int, start: int, target_bits: Sequence[int]
    ) -> Iterator[Clause]:
        for prefix_length, threshold in self.variables.counter_layout:
            current = self.variables.counter_var(
                target, start, prefix_length, threshold
            )
            mismatch = self._mismatch_literal(
                target_bits, start, prefix_length - 1
            )

            if prefix_length == 1:
                # current <-> mismatch
                yield (-current, mismatch)
                yield (current, -mismatch)
                continue

            if threshold == 1:
                previous = self.variables.counter_var(
                    target, start, prefix_length - 1, 1
                )
                # current <-> (previous or mismatch)
                yield (-previous, current)
                yield (-mismatch, current)
                yield (-current, previous, mismatch)
                continue

            previous_lower = self.variables.counter_var(
                target, start, prefix_length - 1, threshold - 1
            )
            if threshold == prefix_length:
                # current <-> (previous_lower and mismatch)
                yield (-current, previous_lower)
                yield (-current, mismatch)
                yield (-previous_lower, -mismatch, current)
                continue

            previous_same = self.variables.counter_var(
                target, start, prefix_length - 1, threshold
            )
            # current <-> (previous_same or (previous_lower and mismatch))
            yield (-previous_same, current)
            yield (-previous_lower, -mismatch, current)
            yield (-current, previous_same, previous_lower)
            yield (-current, previous_same, mismatch)

    def iter_clauses(self) -> Iterator[Clause]:
        if self.symmetry_breaking:
            # Complementing every bit preserves all Hamming covering constraints.
            yield (-self.variables.sequence_var(0),)

        if self.radius >= self.n:
            return

        overflow_threshold = self.radius + 1
        for target in range(1 << self.n):
            target_bits = word_bits(target, self.n)
            target_cover_clause: List[int] = []
            for start in range(self.length):
                cover = self.variables.cover_var(target, start)
                target_cover_clause.append(cover)
                yield from self._counter_clauses(target, start, target_bits)

                overflow = self.variables.counter_var(
                    target, start, self.n, overflow_threshold
                )
                # cover <-> not overflow
                yield (-cover, -overflow)
                yield (cover, overflow)

            yield tuple(target_cover_clause)

    def assignment_for_sequence(self, sequence: Sequence[int]) -> Dict[int, bool]:
        normalized = _normalized_sequence(sequence)
        if len(normalized) != self.length:
            raise ValueError(
                "sequence length is {}, expected {}".format(
                    len(normalized), self.length
                )
            )

        assignment: Dict[int, bool] = {
            self.variables.sequence_var(index): bool(bit)
            for index, bit in enumerate(normalized)
        }
        if self.radius >= self.n:
            return assignment

        for target in range(1 << self.n):
            target_bits = word_bits(target, self.n)
            for start in range(self.length):
                mismatch_count = 0
                for prefix_length in range(1, self.n + 1):
                    sequence_bit = normalized[
                        (start + prefix_length - 1) % self.length
                    ]
                    mismatch_count += (
                        sequence_bit != target_bits[prefix_length - 1]
                    )
                    for threshold in range(
                        1, min(prefix_length, self.radius + 1) + 1
                    ):
                        variable = self.variables.counter_var(
                            target, start, prefix_length, threshold
                        )
                        assignment[variable] = mismatch_count >= threshold

                assignment[self.variables.cover_var(target, start)] = (
                    mismatch_count <= self.radius
                )

        return assignment

    def cnf_status(self, assignment: Assignment) -> str:
        if (
            self.symmetry_breaking
            and self.variables.sequence_var(0) in assignment
            and assignment[self.variables.sequence_var(0)]
        ):
            return "violated"

        if len(assignment) < self.num_variables:
            return "undetermined"
        for variable in range(1, self.num_variables + 1):
            if variable not in assignment:
                return "undetermined"

        for clause in self.iter_clauses():
            clause_satisfied = False
            for literal in clause:
                variable = abs(literal)
                value = assignment[variable]
                if value == (literal > 0):
                    clause_satisfied = True
                    break
            if clause_satisfied:
                continue
            return "violated"
        return "satisfied"

    def assignment_satisfies_cnf(self, assignment: Assignment) -> bool:
        missing = next(
            (
                variable
                for variable in range(1, self.num_variables + 1)
                if variable not in assignment
            ),
            None,
        )
        if missing is not None:
            raise ValueError(
                "assignment is incomplete; first missing variable is {}".format(
                    missing
                )
            )
        return self.cnf_status(assignment) == "satisfied"

    def decode_sequence(self, assignment: Assignment) -> Tuple[int, ...]:
        bits: List[int] = []
        for index in range(self.length):
            variable = self.variables.sequence_var(index)
            if variable not in assignment:
                raise ValueError(
                    "assignment does not contain sequence variable {}".format(
                        variable
                    )
                )
            bits.append(1 if assignment[variable] else 0)
        return tuple(bits)

    def check_assignment(self, assignment: Assignment) -> SemanticCheck:
        sequence = self.decode_sequence(assignment)
        uncovered = uncovered_word_ids(sequence, self.n, self.radius)
        symmetry_ok = not self.symmetry_breaking or sequence[0] == 0
        return SemanticCheck(
            sequence=sequence,
            covers_all_words=not uncovered,
            symmetry_ok=symmetry_ok,
            uncovered_words=uncovered,
            cnf_status=self.cnf_status(assignment),
        )

    def write_dimacs(self, stream: TextIO, include_comments: bool = True) -> None:
        if include_comments:
            stream.write("c cyclic binary covering sequence SAT encoding\n")
            stream.write(
                "c n={} radius={} length={}\n".format(
                    self.n, self.radius, self.length
                )
            )
            stream.write("c sequence variable i is 1+i for zero-based i\n")
            if self.symmetry_breaking:
                stream.write(
                    "c symmetry: sequence[0]=0 by global binary complement\n"
                )
        stream.write(
            "p cnf {} {}\n".format(self.num_variables, self.num_clauses)
        )
        clause_count = 0
        for clause in self.iter_clauses():
            stream.write("{} 0\n".format(" ".join(str(literal) for literal in clause)))
            clause_count += 1
        if clause_count != self.num_clauses:
            raise AssertionError(
                "clause count mismatch: generated {}, expected {}".format(
                    clause_count, self.num_clauses
                )
            )

    def to_dimacs(self, include_comments: bool = True) -> str:
        stream = io.StringIO()
        self.write_dimacs(stream, include_comments=include_comments)
        return stream.getvalue()


def encode_covering_sequence(
    n: int, radius: int, length: int, symmetry_breaking: bool = True
) -> SATEncoding:
    return SATEncoding(n, radius, length, symmetry_breaking)


def parse_dimacs_assignment(text: str) -> Dict[int, bool]:
    """Parse a SAT-solver assignment in DIMACS ``v`` or plain-literal form."""
    assignment: Dict[int, bool] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("c"):
            continue
        upper = line.upper()
        if upper in ("UNSAT", "UNSATISFIABLE") or upper.startswith(
            "S UNSATISFIABLE"
        ):
            raise ValueError("solver output reports UNSATISFIABLE")
        if upper in ("SAT", "SATISFIABLE") or upper.startswith("S SATISFIABLE"):
            continue
        if line.startswith("v") or line.startswith("V"):
            line = line[1:].strip()

        for token in line.split():
            try:
                literal = int(token)
            except ValueError:
                continue
            if literal == 0:
                continue
            variable = abs(literal)
            value = literal > 0
            if variable in assignment and assignment[variable] != value:
                raise ValueError(
                    "conflicting values for variable {}".format(variable)
                )
            assignment[variable] = value
    return assignment


def write_variable_map(variable_map: VariableMap, destination: PathLike) -> None:
    with Path(destination).open("w", encoding="ascii", newline="\n") as stream:
        json.dump(variable_map.to_dict(), stream, indent=2, sort_keys=True)
        stream.write("\n")


def _write_encoding(encoding: SATEncoding, destination: str) -> None:
    if destination == "-":
        encoding.write_dimacs(sys.stdout)
        return
    with Path(destination).open("w", encoding="ascii", newline="\n") as stream:
        encoding.write_dimacs(stream)


def _read_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="ascii")


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Encode a cyclic binary covering-sequence instance as CNF."
    )
    parser.add_argument("--n", type=int, required=True, help="window length")
    parser.add_argument(
        "--radius", "-R", type=int, required=True, help="covering radius"
    )
    parser.add_argument(
        "--length", "-L", type=int, required=True, help="cyclic sequence length"
    )
    parser.add_argument(
        "--no-symmetry",
        action="store_true",
        help="do not fix sequence[0] to zero in generated CNF or decoded models",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="DIMACS output path, or - for standard output",
    )
    parser.add_argument(
        "--map",
        dest="map_path",
        help="write the compact variable map as JSON",
    )
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument(
        "--decode-model",
        metavar="PATH",
        help="decode and semantically check a SAT assignment",
    )
    action_group.add_argument(
        "--check-sequence",
        metavar="BITS",
        help="check a binary sequence directly without symmetry reduction",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_argument_parser()
    arguments = parser.parse_args(argv)
    try:
        apply_symmetry = (
            not arguments.no_symmetry
            and arguments.check_sequence is None
        )
        encoding = SATEncoding(
            arguments.n,
            arguments.radius,
            arguments.length,
            symmetry_breaking=apply_symmetry,
        )

        if arguments.map_path:
            write_variable_map(encoding.variables, arguments.map_path)

        if arguments.decode_model:
            assignment = parse_dimacs_assignment(
                _read_text(arguments.decode_model)
            )
            check = encoding.check_assignment(assignment)
            json.dump(check.to_dict(encoding.n), sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
            return 0 if check.valid else 1

        if arguments.check_sequence is not None:
            sequence = parse_sequence(
                arguments.check_sequence, expected_length=encoding.length
            )
            assignment = encoding.assignment_for_sequence(sequence)
            check = encoding.check_assignment(assignment)
            json.dump(check.to_dict(encoding.n), sys.stdout, indent=2, sort_keys=True)
            sys.stdout.write("\n")
            return 0 if check.valid else 1

        _write_encoding(encoding, arguments.output)
        return 0
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
