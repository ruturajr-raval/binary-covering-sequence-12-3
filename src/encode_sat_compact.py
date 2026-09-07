#!/usr/bin/env python3
"""Compact SAT construction encoding for cyclic binary covering sequences.

For every target word, the encoding selects one cyclic window by a binary
start index. Target-local multiplexer variables are constrained to equal that
actual window, and one sequential counter requires at most ``radius``
mismatches with the target.

This is an exact existential encoding:

* every satisfying assignment selects a real covering window for each target;
* without symmetry breaking, every covering sequence extends to a satisfying
  auxiliary assignment; and
* with complement symmetry breaking, one sequence from each complement pair
  extends to a satisfying auxiliary assignment.

Variables and clauses are allocated deterministically. DIMACS output is
streamed so production instances do not need to be retained in memory.
"""

import argparse
import io
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Mapping, Optional, Sequence, TextIO
from typing import Tuple, Union


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
    if n < 1:
        raise ValueError("n must be at least 1")
    if word < 0 or word >= (1 << n):
        raise ValueError("word is outside the n-bit range")
    return tuple((word >> (n - 1 - index)) & 1 for index in range(n))


def bits_to_string(bits: Sequence[int]) -> str:
    return "".join(str(bit) for bit in bits)


def parse_sequence(
    text: str, expected_length: Optional[int] = None
) -> Tuple[int, ...]:
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
    return sum(
        left_bit != right_bit
        for left_bit, right_bit in zip(left, right)
    )


def uncovered_word_ids(
    sequence: Sequence[int], n: int, radius: int
) -> Tuple[int, ...]:
    normalized = _normalized_sequence(sequence)
    _validate_parameters(n, radius, len(normalized))
    if radius >= n:
        return ()

    windows = [
        cyclic_window(normalized, start, n)
        for start in range(len(normalized))
    ]
    uncovered: List[int] = []
    for target in range(1 << n):
        target_bits = word_bits(target, n)
        if not any(
            hamming_distance(window, target_bits) <= radius
            for window in windows
        ):
            uncovered.append(target)
    return tuple(uncovered)


def is_covering_sequence(
    sequence: Sequence[int], n: int, radius: int
) -> bool:
    return not uncovered_word_ids(sequence, n, radius)


class VariableMap:
    """Compact, reversible description of every DIMACS variable."""

    def __init__(
        self,
        n: int,
        radius: int,
        length: int,
        symmetry_breaking: bool = True,
    ) -> None:
        _validate_parameters(n, radius, length)
        self.n = n
        self.radius = radius
        self.length = length
        self.symmetry_breaking = symmetry_breaking
        self.num_words = 1 << n
        self.active = radius < n
        self.choice_width = (length - 1).bit_length() if self.active else 0

        if self.active and radius > 0:
            self.counter_layout = tuple(
                (prefix_length, threshold)
                for prefix_length in range(1, n)
                for threshold in range(
                    1, min(prefix_length, radius) + 1
                )
            )
        else:
            self.counter_layout = ()
        self._counter_offsets = {
            position: offset
            for offset, position in enumerate(self.counter_layout, start=1)
        }
        self.block_size = (
            self.choice_width + n + len(self.counter_layout)
            if self.active
            else 0
        )

    @property
    def num_variables(self) -> int:
        return self.length + self.num_words * self.block_size

    def sequence_var(self, index: int) -> int:
        if index < 0 or index >= self.length:
            raise IndexError("sequence index is outside the valid range")
        return index + 1

    def _target_base(self, target: int) -> int:
        if not self.active:
            raise ValueError("target blocks are not needed when radius >= n")
        if target < 0 or target >= self.num_words:
            raise IndexError("target is outside the n-bit range")
        return self.length + target * self.block_size

    def choice_var(self, target: int, bit_index: int) -> int:
        if bit_index < 0 or bit_index >= self.choice_width:
            raise IndexError("choice bit is outside the valid range")
        return self._target_base(target) + bit_index + 1

    def selected_var(self, target: int, position: int) -> int:
        if position < 0 or position >= self.n:
            raise IndexError("window position is outside the valid range")
        return self._target_base(target) + self.choice_width + position + 1

    def counter_var(
        self, target: int, prefix_length: int, threshold: int
    ) -> int:
        try:
            offset = self._counter_offsets[(prefix_length, threshold)]
        except KeyError:
            raise IndexError("counter position is outside the encoded layout")
        return (
            self._target_base(target)
            + self.choice_width
            + self.n
            + offset
        )

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
        target, block_offset = divmod(relative, self.block_size)
        target_text = format(target, "0{}b".format(self.n))
        if block_offset < self.choice_width:
            bit_index = block_offset
            return {
                "id": variable,
                "kind": "choice",
                "target": target,
                "target_bits": target_text,
                "bit_index": bit_index,
                "name": "start[target={},bit={}]".format(
                    target_text, bit_index
                ),
            }

        selected_offset = block_offset - self.choice_width
        if selected_offset < self.n:
            position = selected_offset
            return {
                "id": variable,
                "kind": "selected",
                "target": target,
                "target_bits": target_text,
                "position": position,
                "name": "window[target={},position={}]".format(
                    target_text, position
                ),
            }

        counter_offset = selected_offset - self.n
        prefix_length, threshold = self.counter_layout[counter_offset]
        return {
            "id": variable,
            "kind": "counter",
            "target": target,
            "target_bits": target_text,
            "prefix_length": prefix_length,
            "threshold": threshold,
            "name": "ge[target={},prefix={},threshold={}]".format(
                target_text, prefix_length, threshold
            ),
        }

    def to_dict(self) -> Dict[str, object]:
        target_blocks: Optional[Dict[str, object]]
        if self.active:
            target_blocks = {
                "first_variable": self.length + 1,
                "count": self.num_words,
                "block_size": self.block_size,
                "target_order": (
                    "integer order, target bits are most-significant first"
                ),
                "choice": {
                    "offset": 0,
                    "count": self.choice_width,
                    "bit_order": "least-significant first",
                    "meaning": "selected cyclic window start",
                },
                "selected_window": {
                    "offset": self.choice_width,
                    "count": self.n,
                    "meaning": (
                        "actual sequence bits at the selected cyclic start"
                    ),
                },
                "counter": {
                    "offset": self.choice_width + self.n,
                    "count": len(self.counter_layout),
                    "meaning": (
                        "ge(prefix_length, threshold) records that the "
                        "selected window prefix has at least threshold "
                        "mismatches"
                    ),
                    "layout": [
                        {
                            "offset": offset - 1,
                            "prefix_length": prefix_length,
                            "threshold": threshold,
                        }
                        for offset, (
                            prefix_length,
                            threshold,
                        ) in enumerate(self.counter_layout, start=1)
                    ],
                },
            }
        else:
            target_blocks = None

        return {
            "format": "binary-covering-sequence-compact-variable-map-v1",
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
            "target_blocks": target_blocks,
            "symmetry": (
                {
                    "clause": [-self.sequence_var(0)],
                    "reason": "binary complement preserves covering",
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
                format(word, "0{}b".format(n))
                for word in self.uncovered_words
            ],
            "semantic_valid": self.semantic_valid,
            "valid": self.valid,
        }


class CompactSATEncoding:
    """Deterministic exact CNF encoding with binary window selection."""

    def __init__(
        self,
        n: int,
        radius: int,
        length: int,
        symmetry_breaking: bool = True,
    ) -> None:
        self.variables = VariableMap(
            n, radius, length, symmetry_breaking
        )
        self.n = n
        self.radius = radius
        self.length = length
        self.symmetry_breaking = symmetry_breaking
        self._invalid_choice_count = (
            (1 << self.variables.choice_width) - length
            if self.variables.active
            else 0
        )
        self._cardinality_clause_count = self._count_cardinality_clauses()

    @property
    def num_variables(self) -> int:
        return self.variables.num_variables

    @property
    def num_clauses(self) -> int:
        symmetry_clauses = 1 if self.symmetry_breaking else 0
        if not self.variables.active:
            return symmetry_clauses
        clauses_per_target = (
            self._invalid_choice_count
            + 2 * self.length * self.n
            + self._cardinality_clause_count
        )
        return symmetry_clauses + (1 << self.n) * clauses_per_target

    def _choice_mismatch_clause(
        self, target: int, start: int
    ) -> Clause:
        return tuple(
            (
                -self.variables.choice_var(target, bit_index)
                if (start >> bit_index) & 1
                else self.variables.choice_var(target, bit_index)
            )
            for bit_index in range(self.variables.choice_width)
        )

    def _mismatch_literal(
        self, target_bits: Sequence[int], target: int, position: int
    ) -> int:
        selected = self.variables.selected_var(target, position)
        return selected if target_bits[position] == 0 else -selected

    def _count_cardinality_clauses(self) -> int:
        if not self.variables.active:
            return 0
        if self.radius == 0:
            return self.n

        introductions = self.n - 1
        carries = sum(
            min(prefix_length - 1, self.radius)
            for prefix_length in range(2, self.n)
        )
        increments = sum(
            min(prefix_length, self.radius) - 1
            for prefix_length in range(2, self.n)
        )
        overflows = self.n - self.radius
        return introductions + carries + increments + overflows

    def _cardinality_clauses(
        self, target: int, target_bits: Sequence[int]
    ) -> Iterator[Clause]:
        mismatch = [
            self._mismatch_literal(target_bits, target, position)
            for position in range(self.n)
        ]
        if self.radius == 0:
            for literal in mismatch:
                yield (-literal,)
            return

        for prefix_length in range(1, self.n):
            current = self.variables.counter_var(
                target, prefix_length, 1
            )
            yield (-mismatch[prefix_length - 1], current)

        for prefix_length in range(2, self.n):
            for threshold in range(
                1, min(prefix_length - 1, self.radius) + 1
            ):
                previous = self.variables.counter_var(
                    target, prefix_length - 1, threshold
                )
                current = self.variables.counter_var(
                    target, prefix_length, threshold
                )
                yield (-previous, current)

            for threshold in range(
                2, min(prefix_length, self.radius) + 1
            ):
                previous_lower = self.variables.counter_var(
                    target, prefix_length - 1, threshold - 1
                )
                current = self.variables.counter_var(
                    target, prefix_length, threshold
                )
                yield (
                    -mismatch[prefix_length - 1],
                    -previous_lower,
                    current,
                )

        for prefix_length in range(self.radius + 1, self.n + 1):
            previous_limit = self.variables.counter_var(
                target, prefix_length - 1, self.radius
            )
            yield (-mismatch[prefix_length - 1], -previous_limit)

    def iter_clauses(self) -> Iterator[Clause]:
        if self.symmetry_breaking:
            yield (-self.variables.sequence_var(0),)
        if not self.variables.active:
            return

        choice_limit = 1 << self.variables.choice_width
        for target in range(1 << self.n):
            for invalid_start in range(self.length, choice_limit):
                yield self._choice_mismatch_clause(target, invalid_start)

            for start in range(self.length):
                guard = self._choice_mismatch_clause(target, start)
                for position in range(self.n):
                    selected = self.variables.selected_var(target, position)
                    sequence = self.variables.sequence_var(
                        (start + position) % self.length
                    )
                    yield guard + (-selected, sequence)
                    yield guard + (selected, -sequence)

            yield from self._cardinality_clauses(
                target, word_bits(target, self.n)
            )

    def _best_start(
        self, sequence: Sequence[int], target_bits: Sequence[int]
    ) -> int:
        return min(
            range(self.length),
            key=lambda start: (
                hamming_distance(
                    cyclic_window(sequence, start, self.n), target_bits
                ),
                start,
            ),
        )

    def assignment_for_sequence(
        self, sequence: Sequence[int]
    ) -> Dict[int, bool]:
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
        if not self.variables.active:
            return assignment

        for target in range(1 << self.n):
            target_bits = word_bits(target, self.n)
            start = self._best_start(normalized, target_bits)
            for bit_index in range(self.variables.choice_width):
                assignment[
                    self.variables.choice_var(target, bit_index)
                ] = bool((start >> bit_index) & 1)

            selected_window = cyclic_window(normalized, start, self.n)
            mismatch_count = 0
            for position, bit in enumerate(selected_window):
                assignment[
                    self.variables.selected_var(target, position)
                ] = bool(bit)
                mismatch_count += bit != target_bits[position]
                if position + 1 >= self.n:
                    continue
                for threshold in range(
                    1, min(position + 1, self.radius) + 1
                ):
                    assignment[
                        self.variables.counter_var(
                            target, position + 1, threshold
                        )
                    ] = mismatch_count >= threshold
        return assignment

    def cnf_status(self, assignment: Assignment) -> str:
        if len(assignment) < self.num_variables:
            return "undetermined"
        for variable in range(1, self.num_variables + 1):
            if variable not in assignment:
                return "undetermined"
        for clause in self.iter_clauses():
            if any(
                assignment[abs(literal)] == (literal > 0)
                for literal in clause
            ):
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

    def decode_starts(self, assignment: Assignment) -> Tuple[int, ...]:
        if not self.variables.active:
            return ()
        starts: List[int] = []
        for target in range(1 << self.n):
            value = 0
            for bit_index in range(self.variables.choice_width):
                variable = self.variables.choice_var(target, bit_index)
                if variable not in assignment:
                    raise ValueError(
                        "assignment does not contain choice variable {}".format(
                            variable
                        )
                    )
                if assignment[variable]:
                    value |= 1 << bit_index
            if value >= self.length:
                raise ValueError(
                    "assignment selects invalid start {} for target {}".format(
                        value, target
                    )
                )
            starts.append(value)
        return tuple(starts)

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

    def write_dimacs(
        self, stream: TextIO, include_comments: bool = True
    ) -> None:
        if include_comments:
            stream.write(
                "c compact cyclic binary covering sequence SAT encoding\n"
            )
            stream.write(
                "c n={} radius={} length={}\n".format(
                    self.n, self.radius, self.length
                )
            )
            stream.write("c sequence variable i is 1+i for zero-based i\n")
            stream.write(
                "c each target selects one actual cyclic window in binary\n"
            )
            if self.symmetry_breaking:
                stream.write(
                    "c symmetry: sequence[0]=0 by global binary complement\n"
                )
        stream.write(
            "p cnf {} {}\n".format(self.num_variables, self.num_clauses)
        )
        clause_count = 0
        for clause in self.iter_clauses():
            stream.write(
                "{} 0\n".format(" ".join(str(literal) for literal in clause))
            )
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
    n: int,
    radius: int,
    length: int,
    symmetry_breaking: bool = True,
) -> CompactSATEncoding:
    return CompactSATEncoding(n, radius, length, symmetry_breaking)


def parse_dimacs_assignment(text: str) -> Dict[int, bool]:
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
        if upper in ("SAT", "SATISFIABLE") or upper.startswith(
            "S SATISFIABLE"
        ):
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


def write_variable_map(
    variable_map: VariableMap, destination: PathLike
) -> None:
    with Path(destination).open(
        "w", encoding="ascii", newline="\n"
    ) as stream:
        json.dump(
            variable_map.to_dict(),
            stream,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
        )
        stream.write("\n")


def _read_text(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    return Path(source).read_text(encoding="ascii")


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Encode a cyclic binary covering-sequence instance as compact CNF."
        )
    )
    parser.add_argument("--n", type=int, required=True, help="window length")
    parser.add_argument(
        "--radius", "-R", type=int, required=True, help="covering radius"
    )
    parser.add_argument(
        "--length", "-L", type=int, required=True, help="sequence length"
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
        "--map", dest="map_path", help="write variable map as JSON"
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
        encoding = CompactSATEncoding(
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
            json.dump(
                check.to_dict(encoding.n),
                sys.stdout,
                indent=2,
                sort_keys=True,
            )
            sys.stdout.write("\n")
            return 0 if check.valid else 1

        if arguments.check_sequence is not None:
            sequence = parse_sequence(
                arguments.check_sequence,
                expected_length=encoding.length,
            )
            assignment = encoding.assignment_for_sequence(sequence)
            check = encoding.check_assignment(assignment)
            json.dump(
                check.to_dict(encoding.n),
                sys.stdout,
                indent=2,
                sort_keys=True,
            )
            sys.stdout.write("\n")
            return 0 if check.valid else 1

        if arguments.output == "-":
            encoding.write_dimacs(sys.stdout)
        else:
            with Path(arguments.output).open(
                "w", encoding="ascii", newline="\n"
            ) as stream:
                encoding.write_dimacs(stream)
        return 0
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
