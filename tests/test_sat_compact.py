"""Tests for the compact cyclic covering-sequence SAT encoding."""

import importlib.util
import io
import itertools
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "encode_sat_compact.py"
SPEC = importlib.util.spec_from_file_location("encode_sat_compact", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load encode_sat_compact.py")
ENCODING = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENCODING
SPEC.loader.exec_module(ENCODING)


def _literal_is_true(literal, assignment):
    value = assignment.get(abs(literal))
    return value is not None and value == (literal > 0)


def _brute_force_cnf_satisfiable(num_variables, clauses, assumptions=()):
    """Small DPLL solver used only as an independent semantic oracle."""

    initial = {}
    for literal in assumptions:
        variable = abs(literal)
        value = literal > 0
        if variable in initial and initial[variable] != value:
            return False
        initial[variable] = value

    def propagate(assignment):
        while True:
            changed = False
            for clause in clauses:
                if any(
                    _literal_is_true(literal, assignment)
                    for literal in clause
                ):
                    continue
                unassigned = [
                    literal
                    for literal in clause
                    if abs(literal) not in assignment
                ]
                if not unassigned:
                    return False
                if len(unassigned) == 1:
                    literal = unassigned[0]
                    variable = abs(literal)
                    value = literal > 0
                    if (
                        variable in assignment
                        and assignment[variable] != value
                    ):
                        return False
                    if variable not in assignment:
                        assignment[variable] = value
                        changed = True
            if not changed:
                return True

    def search(assignment):
        assignment = dict(assignment)
        if not propagate(assignment):
            return False
        unresolved = [
            clause
            for clause in clauses
            if not any(
                _literal_is_true(literal, assignment)
                for literal in clause
            )
        ]
        if not unresolved:
            return True
        variable = min(
            abs(literal)
            for clause in unresolved
            for literal in clause
            if abs(literal) not in assignment
        )
        for value in (False, True):
            branch = dict(assignment)
            branch[variable] = value
            if search(branch):
                return True
        return False

    if any(
        abs(literal) > num_variables
        for clause in clauses
        for literal in clause
    ):
        raise AssertionError("clause references variable above header bound")
    return search(initial)


def _direct_exists(n, radius, length, first_bit_zero=False):
    for sequence in itertools.product((0, 1), repeat=length):
        if first_bit_zero and sequence[0] != 0:
            continue
        if ENCODING.is_covering_sequence(sequence, n, radius):
            return True
    return False


def _sequence_assumptions(encoding, sequence):
    return tuple(
        (
            encoding.variables.sequence_var(index)
            if bit
            else -encoding.variables.sequence_var(index)
        )
        for index, bit in enumerate(sequence)
    )


def _choice_assumptions(encoding, target, start):
    return tuple(
        (
            encoding.variables.choice_var(target, bit_index)
            if (start >> bit_index) & 1
            else -encoding.variables.choice_var(target, bit_index)
        )
        for bit_index in range(encoding.variables.choice_width)
    )


def _partition_target_clauses(encoding, clauses):
    """Separate clauses by target after checking the block decomposition."""
    global_clauses = []
    target_clauses = [
        [] for _ in range(encoding.variables.num_words)
    ]
    for clause in clauses:
        targets = set()
        for literal in clause:
            variable = abs(literal)
            if variable <= encoding.length:
                continue
            relative = variable - encoding.length - 1
            target = relative // encoding.variables.block_size
            if target >= encoding.variables.num_words:
                raise AssertionError("variable lies outside target blocks")
            targets.add(target)
        if not targets:
            global_clauses.append(clause)
            continue
        if len(targets) != 1:
            raise AssertionError("clause crosses independent target blocks")
        target_clauses[targets.pop()].append(clause)
    return (
        tuple(global_clauses),
        tuple(tuple(block) for block in target_clauses),
    )


def _target_projection_satisfiable(
    encoding,
    components,
    sequence,
    target,
    extra_assumptions=(),
):
    global_clauses, target_clauses = components
    assumptions = (
        _sequence_assumptions(encoding, sequence)
        + tuple(extra_assumptions)
    )
    return (
        _brute_force_cnf_satisfiable(
            encoding.num_variables, global_clauses, assumptions
        )
        and _brute_force_cnf_satisfiable(
            encoding.num_variables,
            target_clauses[target],
            assumptions,
        )
    )


def _fixed_primary_projection_satisfiable(
    encoding, components, sequence
):
    global_clauses, target_clauses = components
    assumptions = _sequence_assumptions(encoding, sequence)
    if not _brute_force_cnf_satisfiable(
        encoding.num_variables, global_clauses, assumptions
    ):
        return False
    return all(
        _brute_force_cnf_satisfiable(
            encoding.num_variables, clauses, assumptions
        )
        for clauses in target_clauses
    )


class ExactSemanticTests(unittest.TestCase):
    def test_fixed_primary_projection_matches_direct_enumeration(self):
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 5):
                    encoding = ENCODING.CompactSATEncoding(
                        n, radius, length, symmetry_breaking=False
                    )
                    clauses = tuple(encoding.iter_clauses())
                    components = _partition_target_clauses(
                        encoding, clauses
                    )
                    projected_results = []
                    for sequence in itertools.product(
                        (0, 1), repeat=length
                    ):
                        with self.subTest(
                            n=n,
                            radius=radius,
                            length=length,
                            sequence=sequence,
                        ):
                            projected = (
                                _fixed_primary_projection_satisfiable(
                                    encoding, components, sequence
                                )
                            )
                            projected_results.append(projected)
                            self.assertEqual(
                                projected,
                                ENCODING.is_covering_sequence(
                                    sequence, n, radius
                                ),
                            )
                    self.assertEqual(
                        any(projected_results),
                        _direct_exists(n, radius, length),
                    )

    def test_constructed_assignment_matches_every_tiny_sequence(self):
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 5):
                    encoding = ENCODING.CompactSATEncoding(
                        n, radius, length
                    )
                    for sequence in itertools.product(
                        (0, 1), repeat=length
                    ):
                        assignment = encoding.assignment_for_sequence(
                            sequence
                        )
                        expected = (
                            sequence[0] == 0
                            and ENCODING.is_covering_sequence(
                                sequence, n, radius
                            )
                        )
                        self.assertEqual(
                            encoding.assignment_satisfies_cnf(assignment),
                            expected,
                        )


class EncodingStructureTests(unittest.TestCase):
    def test_selected_window_and_start_have_stated_meanings(self):
        encoding = ENCODING.CompactSATEncoding(
            3, 1, 4, symmetry_breaking=False
        )
        sequence = (1, 0, 0, 1)
        assignment = encoding.assignment_for_sequence(sequence)
        starts = encoding.decode_starts(assignment)
        for target, start in enumerate(starts):
            self.assertLess(start, encoding.length)
            selected = tuple(
                int(
                    assignment[
                        encoding.variables.selected_var(target, position)
                    ]
                )
                for position in range(encoding.n)
            )
            self.assertEqual(
                selected,
                ENCODING.cyclic_window(sequence, start, encoding.n),
            )

    def test_variable_map_is_complete_compact_and_reversible(self):
        encoding = ENCODING.CompactSATEncoding(3, 1, 3)
        descriptions = [
            encoding.variables.describe(variable)
            for variable in range(1, encoding.num_variables + 1)
        ]
        names = [description["name"] for description in descriptions]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(descriptions[0]["name"], "sequence[0]")
        exported = encoding.variables.to_dict()
        self.assertEqual(
            exported["format"],
            "binary-covering-sequence-compact-variable-map-v1",
        )
        self.assertEqual(
            exported["num_variables"], encoding.num_variables
        )
        self.assertEqual(
            exported["target_blocks"]["choice"]["bit_order"],
            "least-significant first",
        )
        json.dumps(exported, ensure_ascii=True).encode("ascii")

    def test_radius_at_least_n_needs_no_target_blocks(self):
        encoding = ENCODING.CompactSATEncoding(3, 3, 4)
        self.assertEqual(encoding.num_variables, 4)
        self.assertEqual(encoding.num_clauses, 1)
        self.assertEqual(tuple(encoding.iter_clauses()), ((-1,),))
        self.assertIsNone(
            encoding.variables.to_dict()["target_blocks"]
        )

    def test_valid_and_invalid_binary_start_codes(self):
        encoding = ENCODING.CompactSATEncoding(
            3, 2, 3, symmetry_breaking=False
        )
        clauses = tuple(encoding.iter_clauses())
        components = _partition_target_clauses(encoding, clauses)
        sequence = (0, 0, 1)
        target = 0
        for start in range(encoding.length):
            with self.subTest(start=start):
                self.assertTrue(
                    _target_projection_satisfiable(
                        encoding,
                        components,
                        sequence,
                        target,
                        _choice_assumptions(encoding, target, start),
                    )
                )
        self.assertFalse(
            _target_projection_satisfiable(
                encoding,
                components,
                sequence,
                target,
                _choice_assumptions(encoding, target, 3),
            )
        )

    def test_selected_window_wraps_cyclically(self):
        encoding = ENCODING.CompactSATEncoding(
            5, 0, 3, symmetry_breaking=False
        )
        clauses = tuple(encoding.iter_clauses())
        components = _partition_target_clauses(encoding, clauses)
        sequence = (0, 1, 1)
        start = 2
        wrapped = (1, 0, 1, 1, 0)
        self.assertEqual(
            ENCODING.cyclic_window(sequence, start, encoding.n),
            wrapped,
        )
        matching_target = int("".join(str(bit) for bit in wrapped), 2)
        differing_target = matching_target ^ 1
        self.assertTrue(
            _target_projection_satisfiable(
                encoding,
                components,
                sequence,
                matching_target,
                _choice_assumptions(
                    encoding, matching_target, start
                ),
            )
        )
        self.assertFalse(
            _target_projection_satisfiable(
                encoding,
                components,
                sequence,
                differing_target,
                _choice_assumptions(
                    encoding, differing_target, start
                ),
            )
        )

    def test_zero_through_radius_mismatches_pass_and_next_fails(self):
        encoding = ENCODING.CompactSATEncoding(
            5, 2, 5, symmetry_breaking=False
        )
        clauses = tuple(encoding.iter_clauses())
        components = _partition_target_clauses(encoding, clauses)
        target = 0
        start = 0
        choice = _choice_assumptions(encoding, target, start)
        for mismatch_count in range(encoding.radius + 2):
            sequence = tuple(
                1 if index < mismatch_count else 0
                for index in range(encoding.length)
            )
            with self.subTest(mismatch_count=mismatch_count):
                self.assertEqual(
                    _target_projection_satisfiable(
                        encoding,
                        components,
                        sequence,
                        target,
                        choice,
                    ),
                    mismatch_count <= encoding.radius,
                )


class CountAndDimacsTests(unittest.TestCase):
    def test_production_counts_are_substantially_smaller(self):
        encoding = ENCODING.CompactSATEncoding(12, 3, 35)
        old_variables = 6164515
        old_clauses = 22081537
        self.assertEqual(encoding.num_variables, 196643)
        self.assertEqual(encoding.num_clauses, 3829761)
        self.assertLess(encoding.num_variables, old_variables // 20)
        self.assertLess(encoding.num_clauses, old_clauses // 5)

    def test_dimacs_is_deterministic_and_header_matches_body(self):
        encoding = ENCODING.CompactSATEncoding(2, 1, 3)
        first = encoding.to_dimacs()
        second = encoding.to_dimacs()
        self.assertEqual(first, second)
        lines = [
            line
            for line in first.splitlines()
            if line and not line.startswith("c")
        ]
        header = lines[0].split()
        self.assertEqual(header[:2], ["p", "cnf"])
        self.assertEqual(int(header[2]), encoding.num_variables)
        self.assertEqual(int(header[3]), encoding.num_clauses)
        self.assertEqual(len(lines) - 1, encoding.num_clauses)
        for line in lines[1:]:
            literals = [int(token) for token in line.split()]
            self.assertEqual(literals[-1], 0)
            self.assertTrue(literals[:-1])
            self.assertLessEqual(
                max(abs(literal) for literal in literals[:-1]),
                encoding.num_variables,
            )

    def test_assignment_parser_decoder_and_semantic_check(self):
        encoding = ENCODING.CompactSATEncoding(2, 0, 4)
        assignment = encoding.assignment_for_sequence((0, 0, 1, 1))
        literals = [
            variable if value else -variable
            for variable, value in sorted(assignment.items())
        ]
        midpoint = len(literals) // 2
        text = "\n".join(
            [
                "s SATISFIABLE",
                "v {} 0".format(
                    " ".join(str(value) for value in literals[:midpoint])
                ),
                "v {} 0".format(
                    " ".join(str(value) for value in literals[midpoint:])
                ),
            ]
        )
        parsed = ENCODING.parse_dimacs_assignment(text)
        check = encoding.check_assignment(parsed)
        self.assertEqual(check.sequence, (0, 0, 1, 1))
        self.assertTrue(check.valid)
        self.assertEqual(check.cnf_status, "satisfied")
        self.assertEqual(check.uncovered_words, ())

    def test_map_json_is_ascii_and_stream_helpers_are_consistent(self):
        encoding = ENCODING.CompactSATEncoding(2, 1, 2)
        stream = io.StringIO()
        encoding.write_dimacs(stream)
        self.assertEqual(stream.getvalue(), encoding.to_dimacs())
        text = json.dumps(
            encoding.variables.to_dict(),
            sort_keys=True,
            ensure_ascii=True,
        )
        text.encode("ascii")

    def test_cli_sequence_check_does_not_apply_generation_symmetry(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            status = ENCODING.main(
                [
                    "--n",
                    "2",
                    "--radius",
                    "0",
                    "--length",
                    "4",
                    "--check-sequence",
                    "1100",
                ]
            )
        payload = json.loads(stream.getvalue())
        self.assertEqual(status, 0)
        self.assertEqual(payload["sequence"], "1100")
        self.assertTrue(payload["valid"])
        self.assertTrue(payload["symmetry_ok"])


class ValidationTests(unittest.TestCase):
    def test_invalid_parameters(self):
        invalid = (
            (0, 0, 1),
            (1, -1, 1),
            (1, 2, 1),
            (1, 0, 0),
            (True, 0, 1),
            (1, False, 1),
            (1, 0, True),
        )
        for n, radius, length in invalid:
            with self.subTest(n=n, radius=radius, length=length):
                with self.assertRaises(ValueError):
                    ENCODING.CompactSATEncoding(n, radius, length)

    def test_conflicting_assignment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting values"):
            ENCODING.parse_dimacs_assignment(
                "s SATISFIABLE\nv 1 -1 0\n"
            )

    def test_incomplete_assignment_is_not_a_full_witness(self):
        encoding = ENCODING.CompactSATEncoding(2, 0, 4)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            encoding.assignment_satisfies_cnf({1: False})


if __name__ == "__main__":
    unittest.main()
