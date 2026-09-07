"""Tests for the guarded compact covering-sequence SAT encoding."""

import importlib.util
import io
import itertools
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "encode_sat_guarded.py"
SPEC = importlib.util.spec_from_file_location("encode_sat_guarded", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load encode_sat_guarded.py")
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
        elif len(targets) == 1:
            target_clauses[targets.pop()].append(clause)
        else:
            raise AssertionError("clause crosses independent target blocks")
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


def _range_accepts(encoding, start):
    assignment = {
        encoding.variables.choice_var(0, bit_index): bool(
            (start >> bit_index) & 1
        )
        for bit_index in range(encoding.variables.choice_width)
    }
    return all(
        any(
            assignment[abs(literal)] == (literal > 0)
            for literal in clause
        )
        for clause in encoding._range_clauses(0)
    )


class ProjectionExactnessTests(unittest.TestCase):
    def test_fixed_primary_projection_matches_direct_semantics(self):
        checked = 0
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 5):
                    encoding = ENCODING.GuardedSATEncoding(
                        n, radius, length, symmetry_breaking=False
                    )
                    clauses = tuple(encoding.iter_clauses())
                    components = _partition_target_clauses(
                        encoding, clauses
                    )
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
                            self.assertEqual(
                                projected,
                                ENCODING.is_covering_sequence(
                                    sequence, n, radius
                                ),
                            )
                            checked += 1
        self.assertEqual(checked, 270)

    def test_canonical_auxiliary_assignment_matches_each_sequence(self):
        checked = 0
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 5):
                    encoding = ENCODING.GuardedSATEncoding(
                        n, radius, length, symmetry_breaking=False
                    )
                    for sequence in itertools.product(
                        (0, 1), repeat=length
                    ):
                        assignment = encoding.assignment_for_sequence(
                            sequence
                        )
                        self.assertEqual(
                            encoding.assignment_satisfies_cnf(assignment),
                            ENCODING.is_covering_sequence(
                                sequence, n, radius
                            ),
                        )
                        checked += 1
        self.assertEqual(checked, 270)

    def test_symmetry_breaking_is_complete(self):
        checked = 0
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 5):
                    encoding = ENCODING.GuardedSATEncoding(
                        n, radius, length, symmetry_breaking=True
                    )
                    components = _partition_target_clauses(
                        encoding, tuple(encoding.iter_clauses())
                    )
                    for sequence in itertools.product(
                        (0, 1), repeat=length
                    ):
                        if not ENCODING.is_covering_sequence(
                            sequence, n, radius
                        ):
                            continue
                        representative = (
                            sequence
                            if sequence[0] == 0
                            else tuple(1 - bit for bit in sequence)
                        )
                        self.assertEqual(representative[0], 0)
                        self.assertTrue(
                            ENCODING.is_covering_sequence(
                                representative, n, radius
                            )
                        )
                        self.assertTrue(
                            _fixed_primary_projection_satisfiable(
                                encoding, components, representative
                            )
                        )
                        checked += 1
        self.assertGreater(checked, 0)


class GuardAndCounterTests(unittest.TestCase):
    def test_every_binary_start_code_has_correct_range_status(self):
        checked = 0
        for length in range(1, 36):
            encoding = ENCODING.GuardedSATEncoding(
                3, 1, length, symmetry_breaking=False
            )
            for start in range(1 << encoding.variables.choice_width):
                with self.subTest(length=length, start=start):
                    self.assertEqual(
                        _range_accepts(encoding, start),
                        start < length,
                    )
                    checked += 1
        self.assertEqual(checked, 875)

    def test_length_35_boundary_codes_and_compact_range_clauses(self):
        encoding = ENCODING.GuardedSATEncoding(
            12, 3, 35, symmetry_breaking=False
        )
        clauses = tuple(encoding._range_clauses(0))
        self.assertEqual(len(clauses), 4)
        for start in range(64):
            self.assertEqual(_range_accepts(encoding, start), start <= 34)
        self.assertTrue(_range_accepts(encoding, 32))
        self.assertTrue(_range_accepts(encoding, 33))
        self.assertTrue(_range_accepts(encoding, 34))
        self.assertFalse(_range_accepts(encoding, 35))
        self.assertFalse(_range_accepts(encoding, 36))
        self.assertFalse(_range_accepts(encoding, 63))

    def test_guarded_window_wraps_and_counts_repeated_positions(self):
        encoding = ENCODING.GuardedSATEncoding(
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

    def test_all_up_to_radius_patterns_extend_and_radius_plus_one_fails(self):
        encoding = ENCODING.GuardedSATEncoding(
            6, 3, 6, symmetry_breaking=False
        )
        components = _partition_target_clauses(
            encoding, tuple(encoding.iter_clauses())
        )
        target = 0
        choice = _choice_assumptions(encoding, target, 0)
        checked = 0
        for mismatch_count in range(encoding.radius + 2):
            expected = mismatch_count <= encoding.radius
            for positions in itertools.combinations(
                range(encoding.n), mismatch_count
            ):
                sequence = tuple(
                    int(position in positions)
                    for position in range(encoding.length)
                )
                self.assertEqual(
                    _target_projection_satisfiable(
                        encoding,
                        components,
                        sequence,
                        target,
                        choice,
                    ),
                    expected,
                )
                checked += 1
        self.assertEqual(checked, 57)

    def test_extra_y_values_only_make_cardinality_harder(self):
        encoding = ENCODING.GuardedSATEncoding(
            6, 3, 6, symmetry_breaking=False
        )
        target_clauses = tuple(encoding._cardinality_clauses(0))
        for true_count in range(5):
            for positions in itertools.combinations(range(6), true_count):
                assumptions = tuple(
                    (
                        encoding.variables.mismatch_var(0, position)
                        if position in positions
                        else -encoding.variables.mismatch_var(0, position)
                    )
                    for position in range(6)
                )
                self.assertEqual(
                    _brute_force_cnf_satisfiable(
                        encoding.num_variables,
                        target_clauses,
                        assumptions,
                    ),
                    true_count <= encoding.radius,
                )


class MappingDecoderAndDimacsTests(unittest.TestCase):
    def test_variable_map_is_complete_compact_and_reversible(self):
        encoding = ENCODING.GuardedSATEncoding(4, 2, 5)
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
            "binary-covering-sequence-guarded-variable-map-v1",
        )
        self.assertEqual(
            exported["num_variables"], encoding.num_variables
        )
        self.assertEqual(
            exported["target_blocks"]["choice"]["bit_order"],
            "least-significant first",
        )
        json.dumps(exported, ensure_ascii=True).encode("ascii")

    def test_assignment_parser_decoder_and_semantic_check(self):
        encoding = ENCODING.GuardedSATEncoding(2, 0, 4)
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
        self.assertTrue(check.starts_valid)
        self.assertEqual(len(check.selected_starts), 4)
        self.assertEqual(check.cnf_status, "satisfied")

    def test_dimacs_is_deterministic_and_header_matches_body(self):
        encoding = ENCODING.GuardedSATEncoding(3, 1, 3)
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

    def test_radius_at_least_n_needs_no_target_blocks(self):
        encoding = ENCODING.GuardedSATEncoding(3, 3, 4)
        self.assertEqual(encoding.num_variables, 4)
        self.assertEqual(encoding.num_clauses, 1)
        self.assertEqual(tuple(encoding.iter_clauses()), ((-1,),))
        self.assertIsNone(
            encoding.variables.to_dict()["target_blocks"]
        )

    def test_new_files_are_ascii(self):
        for path in (MODULE_PATH, Path(__file__)):
            path.read_bytes().decode("ascii")

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


class ProductionCountTests(unittest.TestCase):
    def test_exact_length_35_counts_and_generated_clause_total(self):
        encoding = ENCODING.GuardedSATEncoding(12, 3, 35)
        self.assertEqual(encoding.variables.choice_width, 6)
        self.assertEqual(len(encoding.variables.counter_layout), 27)
        self.assertEqual(encoding.variables.block_size, 45)
        self.assertEqual(encoding._range_clause_count, 4)
        self.assertEqual(encoding._cardinality_clause_count, 60)
        self.assertEqual(encoding.num_variables, 184355)
        self.assertEqual(encoding.num_clauses, 1982465)
        self.assertEqual(
            sum(1 for _ in encoding.iter_clauses()),
            encoding.num_clauses,
        )


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
                    ENCODING.GuardedSATEncoding(n, radius, length)

    def test_conflicting_and_incomplete_assignments_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting values"):
            ENCODING.parse_dimacs_assignment(
                "s SATISFIABLE\nv 1 -1 0\n"
            )
        encoding = ENCODING.GuardedSATEncoding(2, 0, 4)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            encoding.assignment_satisfies_cnf({1: False})

    def test_bad_sequences(self):
        with self.assertRaises(ValueError):
            ENCODING.parse_sequence("")
        with self.assertRaises(ValueError):
            ENCODING.parse_sequence("0102")
        with self.assertRaises(ValueError):
            ENCODING.parse_sequence("010", expected_length=2)


if __name__ == "__main__":
    unittest.main()
