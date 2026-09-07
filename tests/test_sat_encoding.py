"""Tests for the cyclic binary covering-sequence SAT encoding."""

import importlib.util
import io
import itertools
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_ROOT / "src" / "encode_sat.py"
SPEC = importlib.util.spec_from_file_location("encode_sat", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("could not load encode_sat.py")
ENCODE_SAT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ENCODE_SAT
SPEC.loader.exec_module(ENCODE_SAT)


def _literal_is_true(literal, assignment):
    value = assignment.get(abs(literal))
    return value is not None and value == (literal > 0)


def _brute_force_cnf_satisfiable(num_variables, clauses):
    """Small DPLL enumerator used only as an independent test oracle."""

    def propagate(assignment):
        while True:
            changed = False
            for clause in clauses:
                if any(_literal_is_true(literal, assignment) for literal in clause):
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
                    if variable in assignment and assignment[variable] != value:
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
                _literal_is_true(literal, assignment) for literal in clause
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

    if any(abs(literal) > num_variables for clause in clauses for literal in clause):
        raise AssertionError("clause references a variable above the header bound")
    return search({})


def _direct_exists(n, radius, length, first_bit_zero=False):
    for sequence in itertools.product((0, 1), repeat=length):
        if first_bit_zero and sequence[0] != 0:
            continue
        if ENCODE_SAT.is_covering_sequence(sequence, n, radius):
            return True
    return False


class DirectSemanticsTests(unittest.TestCase):
    def test_known_small_sequences(self):
        self.assertTrue(
            ENCODE_SAT.is_covering_sequence((0, 1), n=1, radius=0)
        )
        self.assertFalse(
            ENCODE_SAT.is_covering_sequence((0,), n=1, radius=0)
        )
        self.assertTrue(
            ENCODE_SAT.is_covering_sequence((0, 0, 1, 1), n=2, radius=0)
        )
        self.assertTrue(
            ENCODE_SAT.is_covering_sequence((0, 1), n=3, radius=1)
        )

    def test_windows_repeat_positions_when_length_is_shorter_than_n(self):
        self.assertEqual(
            ENCODE_SAT.cyclic_window((0, 1), start=0, n=5),
            (0, 1, 0, 1, 0),
        )
        self.assertEqual(
            ENCODE_SAT.cyclic_window((0, 1), start=1, n=5),
            (1, 0, 1, 0, 1),
        )

    def test_word_bit_order(self):
        self.assertEqual(ENCODE_SAT.word_bits(0, 3), (0, 0, 0))
        self.assertEqual(ENCODE_SAT.word_bits(5, 3), (1, 0, 1))
        self.assertEqual(ENCODE_SAT.word_bits(7, 3), (1, 1, 1))


class ExhaustiveEquivalenceTests(unittest.TestCase):
    def test_cnf_satisfiability_matches_direct_semantics(self):
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 5):
                    with self.subTest(n=n, radius=radius, length=length):
                        encoding = ENCODE_SAT.SATEncoding(n, radius, length)
                        clauses = tuple(encoding.iter_clauses())
                        cnf_satisfiable = _brute_force_cnf_satisfiable(
                            encoding.num_variables, clauses
                        )
                        direct_satisfiable = _direct_exists(
                            n, radius, length
                        )
                        direct_with_symmetry = _direct_exists(
                            n, radius, length, first_bit_zero=True
                        )
                        self.assertEqual(
                            direct_satisfiable, direct_with_symmetry
                        )
                        self.assertEqual(
                            cnf_satisfiable, direct_satisfiable
                        )

    def test_semantic_auxiliary_assignment_matches_every_tiny_sequence(self):
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 5):
                    encoding = ENCODE_SAT.SATEncoding(n, radius, length)
                    for sequence in itertools.product((0, 1), repeat=length):
                        with self.subTest(
                            n=n,
                            radius=radius,
                            length=length,
                            sequence=sequence,
                        ):
                            assignment = encoding.assignment_for_sequence(
                                sequence
                            )
                            expected = (
                                sequence[0] == 0
                                and ENCODE_SAT.is_covering_sequence(
                                    sequence, n, radius
                                )
                            )
                            self.assertEqual(
                                encoding.assignment_satisfies_cnf(assignment),
                                expected,
                            )

    def test_encoding_without_symmetry_matches_each_sequence_exactly(self):
        for n in range(1, 4):
            for radius in range(0, n + 1):
                for length in range(1, 4):
                    encoding = ENCODE_SAT.SATEncoding(
                        n, radius, length, symmetry_breaking=False
                    )
                    for sequence in itertools.product((0, 1), repeat=length):
                        assignment = encoding.assignment_for_sequence(sequence)
                        self.assertEqual(
                            encoding.assignment_satisfies_cnf(assignment),
                            ENCODE_SAT.is_covering_sequence(
                                sequence, n, radius
                            ),
                        )


class CounterAndMapTests(unittest.TestCase):
    def test_counter_and_cover_values_have_their_stated_meanings(self):
        encoding = ENCODE_SAT.SATEncoding(3, 1, 2)
        sequence = (0, 1)
        assignment = encoding.assignment_for_sequence(sequence)

        for target in range(1 << encoding.n):
            target_bits = ENCODE_SAT.word_bits(target, encoding.n)
            for start in range(encoding.length):
                mismatch_count = 0
                for prefix_length in range(1, encoding.n + 1):
                    sequence_bit = sequence[
                        (start + prefix_length - 1) % encoding.length
                    ]
                    mismatch_count += (
                        sequence_bit != target_bits[prefix_length - 1]
                    )
                    for threshold in range(
                        1, min(prefix_length, encoding.radius + 1) + 1
                    ):
                        variable = encoding.variables.counter_var(
                            target, start, prefix_length, threshold
                        )
                        self.assertEqual(
                            assignment[variable],
                            mismatch_count >= threshold,
                        )

                cover = encoding.variables.cover_var(target, start)
                self.assertEqual(
                    assignment[cover], mismatch_count <= encoding.radius
                )

    def test_variable_map_is_complete_compact_and_reversible(self):
        encoding = ENCODE_SAT.SATEncoding(2, 0, 2)
        descriptions = [
            encoding.variables.describe(variable)
            for variable in range(1, encoding.num_variables + 1)
        ]
        names = [description["name"] for description in descriptions]
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(descriptions[0]["name"], "sequence[0]")
        self.assertEqual(descriptions[1]["name"], "sequence[1]")

        exported = encoding.variables.to_dict()
        self.assertEqual(
            exported["format"],
            "binary-covering-sequence-variable-map-v1",
        )
        self.assertEqual(
            exported["num_variables"], encoding.num_variables
        )
        self.assertEqual(exported["pair_blocks"]["block_size"], 3)
        self.assertNotIn("variables", exported)

    def test_radius_at_least_n_needs_no_distance_auxiliaries(self):
        encoding = ENCODE_SAT.SATEncoding(3, 3, 4)
        self.assertEqual(encoding.num_variables, 4)
        self.assertEqual(encoding.num_clauses, 1)
        self.assertIsNone(encoding.variables.to_dict()["pair_blocks"])
        self.assertEqual(tuple(encoding.iter_clauses()), ((-1,),))


class DimacsAndDecoderTests(unittest.TestCase):
    def test_dimacs_header_and_body_match(self):
        encoding = ENCODE_SAT.SATEncoding(2, 1, 2)
        stream = io.StringIO()
        encoding.write_dimacs(stream)
        lines = [
            line
            for line in stream.getvalue().splitlines()
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

    def test_parse_decode_and_semantic_check(self):
        encoding = ENCODE_SAT.SATEncoding(2, 0, 4)
        sequence = (0, 0, 1, 1)
        assignment = encoding.assignment_for_sequence(sequence)
        literals = [
            variable if value else -variable
            for variable, value in sorted(assignment.items())
        ]
        midpoint = len(literals) // 2
        text = "\n".join(
            [
                "s SATISFIABLE",
                "v {} 0".format(
                    " ".join(str(literal) for literal in literals[:midpoint])
                ),
                "v {} 0".format(
                    " ".join(str(literal) for literal in literals[midpoint:])
                ),
            ]
        )
        parsed = ENCODE_SAT.parse_dimacs_assignment(text)
        check = encoding.check_assignment(parsed)
        self.assertEqual(check.sequence, sequence)
        self.assertTrue(check.valid)
        self.assertEqual(check.cnf_status, "satisfied")
        self.assertEqual(check.uncovered_words, ())

        payload = check.to_dict(encoding.n)
        self.assertEqual(payload["sequence"], "0011")
        self.assertTrue(payload["covers_all_words"])

    def test_partial_assignment_can_be_semantically_checked(self):
        encoding = ENCODE_SAT.SATEncoding(2, 0, 4)
        assignment = {
            encoding.variables.sequence_var(index): bool(bit)
            for index, bit in enumerate((0, 0, 1, 1))
        }
        check = encoding.check_assignment(assignment)
        self.assertTrue(check.covers_all_words)
        self.assertTrue(check.symmetry_ok)
        self.assertEqual(check.cnf_status, "undetermined")
        self.assertTrue(check.semantic_valid)
        self.assertFalse(check.valid)

    def test_conflicting_assignment_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "conflicting values"):
            ENCODE_SAT.parse_dimacs_assignment("s SATISFIABLE\nv 1 -1 0\n")

    def test_variable_map_exports_as_ascii_json(self):
        encoding = ENCODE_SAT.SATEncoding(2, 1, 2)
        text = json.dumps(
            encoding.variables.to_dict(), sort_keys=True, ensure_ascii=True
        )
        text.encode("ascii")
        self.assertIn('"pair_blocks"', text)

    def test_cli_sequence_check_does_not_apply_generation_symmetry(self):
        stream = io.StringIO()
        with redirect_stdout(stream):
            status = ENCODE_SAT.main(
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
                    ENCODE_SAT.SATEncoding(n, radius, length)

    def test_bad_sequences(self):
        with self.assertRaises(ValueError):
            ENCODE_SAT.parse_sequence("")
        with self.assertRaises(ValueError):
            ENCODE_SAT.parse_sequence("0102")
        with self.assertRaises(ValueError):
            ENCODE_SAT.parse_sequence("01\u00a001")
        with self.assertRaises(ValueError):
            ENCODE_SAT.parse_sequence("010", expected_length=2)

    def test_incomplete_assignment_cannot_be_claimed_as_full_cnf_witness(self):
        encoding = ENCODE_SAT.SATEncoding(2, 0, 4)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            encoding.assignment_satisfies_cnf({1: False})


if __name__ == "__main__":
    unittest.main()
