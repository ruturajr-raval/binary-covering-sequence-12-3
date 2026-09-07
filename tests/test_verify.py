"""Tests for the exact cyclic covering-sequence verifier."""

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import verify  # noqa: E402


BASELINE_PATH = ROOT / "data" / "baseline-36.txt"


class ParseSequenceTests(unittest.TestCase):
    def test_accepts_one_word_with_ascii_whitespace(self):
        self.assertEqual(verify.parse_sequence("\n  010011\t"), "010011")

    def test_accepts_arbitrarily_grouped_bits(self):
        self.assertEqual(verify.parse_sequence("010\t10 1\n"), "010101")

    def test_rejects_malformed_input(self):
        malformed = (
            "",
            " \n\t",
            "0102",
            "# comment\n0101",
            "0,1,0",
            "0101 # comment",
            "01\u00a010",
        )
        for text in malformed:
            with self.subTest(text=text):
                with self.assertRaises(verify.SequenceFormatError):
                    verify.parse_sequence(text)


class ExactVerificationTests(unittest.TestCase):
    def test_public_length_36_baseline(self):
        # Source: C. D. Rosin, Constructive-Codes/CPro1,
        # designs/covering-sequence/result-12-3-36-seed1000.txt.
        # The public source repository is licensed under Apache-2.0.
        result = verify.verify_text(
            BASELINE_PATH.read_text(encoding="ascii"),
            n=12,
            radius=3,
            expected_length=36,
        )

        self.assertEqual(len(result.sequence), 36)
        self.assertEqual(len(result.distinct_windows), 36)
        self.assertEqual(result.covering_radius, 3)
        self.assertEqual(result.uncovered_words, ())
        self.assertTrue(result.is_covering)
        self.assertEqual(
            result.canonical_representative,
            "000001001110010011101011111011000101",
        )

    def test_cyclic_windows_wrap_at_every_position(self):
        self.assertEqual(
            verify.cyclic_windows("001", 4),
            ("0010", "0100", "1001"),
        )

    def test_covering_radius_and_uncovered_words_are_exact(self):
        result = verify.verify_sequence(
            "0", n=2, radius=1, expected_length=1
        )

        self.assertEqual(result.distinct_windows, ("00",))
        self.assertEqual(result.covering_radius, 2)
        self.assertEqual(result.uncovered_words, ("11",))
        self.assertFalse(result.is_covering)

    def test_zero_radius_de_bruijn_cycle_covers_every_word(self):
        result = verify.verify_sequence(
            "0011", n=2, radius=0, expected_length=4
        )

        self.assertEqual(
            result.distinct_windows,
            ("00", "01", "10", "11"),
        )
        self.assertEqual(result.covering_radius, 0)
        self.assertEqual(result.uncovered_words, ())

    def test_canonical_form_is_dihedral_and_complement_invariant(self):
        sequence = "0011"
        complement = sequence.translate(str.maketrans("01", "10"))
        bases = (sequence, sequence[::-1], complement, complement[::-1])
        variants = [
            base[index:] + base[:index]
            for base in bases
            for index in range(len(base))
        ]

        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(
                    verify.canonical_rotation_reversal_complement(variant),
                    "0011",
                )

    def test_rejects_invalid_parameters_and_direct_sequence(self):
        cases = (
            ("01 01", 2, 1),
            ("0101", 0, 0),
            ("0101", 2, -1),
            ("0101", 2, 3),
            ("0101", True, 1),
            ("0101", 2, False),
        )
        for sequence, n, radius in cases:
            with self.subTest(sequence=sequence, n=n, radius=radius):
                with self.assertRaises(ValueError):
                    verify.verify_sequence(
                        sequence,
                        n,
                        radius,
                        expected_length=len(sequence),
                    )

    def test_rejects_an_unexpected_sequence_length(self):
        with self.assertRaisesRegex(
            verify.SequenceFormatError,
            "sequence length 4 does not match expected length 3",
        ):
            verify.verify_sequence(
                "0101",
                n=2,
                radius=1,
                expected_length=3,
            )


class ReportAndCliTests(unittest.TestCase):
    def test_text_report_lists_windows_and_uncovered_words(self):
        result = verify.verify_sequence(
            "0", n=2, radius=1, expected_length=1
        )
        report = verify.format_report(result)

        self.assertIn("distinct_window_count: 1", report)
        self.assertIn("distinct_windows:\n  00", report)
        self.assertIn("covering_radius: 2", report)
        self.assertIn("uncovered_words:\n  11", report)
        self.assertIn(
            "canonical_rotation_reversal_complement_representative: 0",
            report,
        )

    def test_json_cli_reports_the_public_baseline(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = verify.main(
                [
                    str(BASELINE_PATH),
                    "--n",
                    "12",
                    "--radius",
                    "3",
                    "--expected-length",
                    "36",
                    "--json",
                ]
            )

        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertTrue(payload["is_covering"])
        self.assertEqual(payload["covering_radius"], 3)
        self.assertEqual(payload["cyclic_window_count"], 36)
        self.assertEqual(payload["expected_sequence_length"], 36)
        self.assertEqual(payload["distinct_window_count"], 36)
        self.assertEqual(payload["uncovered_words"], [])

    def test_file_option_reads_the_public_baseline(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = verify.main(
                [
                    "--n",
                    "12",
                    "--radius",
                    "3",
                    "--expected-length",
                    "36",
                    "--file",
                    str(BASELINE_PATH),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("covering_radius: 3", stdout.getvalue())

    def test_noncovering_cli_returns_one(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("0\n")):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = verify.main(
                    [
                        "-",
                        "--n",
                        "2",
                        "--radius",
                        "1",
                        "--expected-length",
                        "1",
                    ]
                )

        self.assertEqual(exit_code, 1)
        self.assertEqual(stderr.getvalue(), "")
        self.assertIn("is_covering: false", stdout.getvalue())
        self.assertIn("uncovered_words:\n  11", stdout.getvalue())

    def test_malformed_cli_input_returns_two(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with mock.patch.object(sys, "stdin", io.StringIO("0102\n")):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = verify.main(
                    [
                        "-",
                        "--n",
                        "2",
                        "--radius",
                        "1",
                        "--expected-length",
                        "4",
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("error: invalid character '2'", stderr.getvalue())

    def test_cli_rejects_a_length_mismatch(self):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = verify.main(
                [
                    "--sequence",
                    "0011",
                    "--n",
                    "2",
                    "--radius",
                    "0",
                    "--expected-length",
                    "3",
                ]
            )

        self.assertEqual(exit_code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn(
            "sequence length 4 does not match expected length 3",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
