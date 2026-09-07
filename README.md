# Exact Binary Covering-Sequence Length `L(12,3)`

## Project Overview

### Project Metadata

| Field | Value |
| --- | --- |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981) |
| Field | Coding theory, de Bruijn graphs, and exhaustive combinatorial search |
| Problem | Determine the binary cyclic covering-sequence length `L(12,3)` |
| Current result | Exact computer-assisted theorem `L(12,3) = 36` |
| Result type | Complete finite exclusion through length 35 plus a verified length-36 witness |
| Release | not yet released |
| Version DOI | not yet assigned |
| Concept DOI | not yet assigned |
| License | MIT for project-original material; Apache-2.0 for the attributed witness fixture |

### Problem And Context

An `(n,R)` binary covering sequence is a positive-length cyclic binary
sequence whose length-`n` cyclic windows cover every word in `{0,1}^n`
within Hamming distance `R`. Chung and Cooper introduced the subject in
2004. Chee, Etzion, Ta, and Vu recorded `34 <= L(12,3) <= 40` in their 2025
table, and Rosin's CPro1 project later supplied a public 36-bit construction.
This left the finite gap `34 <= L(12,3) <= 36`, which remained unresolved
for about one year from the 2025 construction into the 2026-09-07 audit.
That public-source audit located no earlier public exclusion of lengths 34
and 35 or exact determination of this cell.

### Work And Verified Outcome

The project exhaustively enumerated every binary sequence of every positive
length from 1 through 35. Rotation, reversal, and bit complement reduce
`68,719,476,734` raw sequences to `506,526,514` representatives. A C++
implementation and a separately written Rust implementation both found zero
covering representatives. Their per-length orbit counts agree with each other
and with independent Burnside calculations. The attributed 36-bit sequence

```text
010100011011000110111110101110010000
```

has 36 distinct cyclic windows, covering radius exactly 3, and no uncovered
target. Python, Rust, and C++ verifiers agree. Together these results establish

```text
L(12,3) = 36.
```

### Claim Boundary

The repository claims the exact value under the explicit convention that
sequence lengths are positive and window indices are reduced modulo the
sequence length, including when the sequence is shorter than 12. The
length-36 witness is prior art and is not claimed as original. Formal
verification is not claimed. The project does not claim a complete
classification of all optimal sequences or external mathematical review. It
does not claim priority over unpublished or unindexed work. Nearcovers,
heuristic search, and solver timeouts are not used in the theorem.

### Verification And Reproduction

The lower-bound computation has two independently implemented enumeration
paths. Each traverses the complete raw space, tests one
rotation-reversal-complement representative per orbit, constructs exact
cyclic windows, and unions exact radius-3 Hamming balls over all 4,096
targets. Independent evidence checkers verify the raw counts, two separately
implemented Burnside formulas, source and log hashes, metadata, and the
reported closest noncovers. The upper witness has three independent verifier
paths. Retained evidence is documented in `evidence/README.md` and bound by
`release-manifest.sha256`. The complete traversals are CPU-bound, use a
configurable multicore worker count, require no GPU, and are suitable for a
commodity multicore workstation. The retained 12-thread runs completed in
under ten minutes per implementation on the recorded macOS arm64 system.

### Significance, Limitations, And Future Work

The result closes a finite coding-theory table entry by excluding both
remaining shorter lengths. The same raw-space, symmetry, bitset, and
cross-implementation method can be applied to nearby covering-sequence cells.
The principal limitation is computational trust: the programs are tested,
sanitized, source-bound, and independently reproduced, but are not formally
verified. Next work includes a proof-assistant reconstruction of the symmetry
and coverage kernels, compressed certificates for exhaustive traversals,
classification of optimal length-36 sequences, and exact work on adjacent
unresolved parameters.

### Release, Citation, And Author

This package is not yet released or archived. The planned canonical
repository is
[`ruturajr-raval/binary-covering-sequence-12-3`](https://github.com/ruturajr-raval/binary-covering-sequence-12-3).
Release and archive identifiers will be recorded only after publication.
Citation metadata is in `CITATION.cff`, the release dossier is in
`PUBLICATION.md`, and release history is in `RELEASE_NOTES.md`.

Project-original code, evidence tooling, and documentation are MIT licensed.
The attributed CPro1 witness fixture remains under Apache-2.0; its provenance
and full license text are retained in `THIRD_PARTY_NOTICES.md` and
`LICENSES/Apache-2.0.txt`. The author is Ruturaj R Raval, with affiliation
Independent Researcher and ORCID `0000-0003-4930-8981`.

## Theorem

Let `x = x_0 x_1 ... x_(L-1)` be a positive-length cyclic binary sequence.
For every start `i`, define

```text
W_i = x_i x_(i+1) ... x_(i+11),
```

with every subscript reduced modulo `L`. The sequence is a binary `(12,3)`
covering sequence when

```text
for every y in {0,1}^12, min_i d_H(y, W_i) <= 3.
```

The minimum possible positive length is `L(12,3)`.

**Main theorem.**

```text
L(12,3) = 36.
```

## Starting Frontier

| Date | Result | Role |
| --- | --- | --- |
| 2004 | Covering de Bruijn sequences introduced | General origin |
| 2025 | `34 <= L(12,3) <= 40` | Published table |
| 2025 | Explicit length-36 construction | Public upper bound |
| 2026-09-07 | `34 <= L(12,3) <= 36` | Audited starting frontier |
| 2026-09-07 | `L(12,3) = 36` | Result of this project |

The lower endpoint from the earlier table is not needed for the final theorem
because the exhaustive traversal directly excludes every positive length
from 1 through 35.

## Proof Architecture

### Symmetry

Coverage is invariant under:

1. cyclic rotation of the sequence;
2. reversal of the sequence; and
3. complementing every bit.

For a fixed length `L`, these operations give at most `4L` transformed
sequences. The exhaustive programs retain a sequence only when no transformed
sequence is lexicographically smaller under their stated bit convention.

Independent Burnside calculations determine the exact number of orbits at
each length. Equality between the predicted and observed counts checks that
the traversal retained exactly one representative from every orbit.

### Exact Coverage

For each 12-bit window, the programs precompute its radius-3 Hamming ball as
a 4,096-bit set. The coverage of a candidate sequence is the bitwise union of
the balls centered at its cyclic windows. A candidate covers if and only if
all 4,096 bits are set.

### Complete Enumeration

The two complete runs independently report:

| Quantity | C++ | Rust |
| --- | ---: | ---: |
| Lengths | `1..35` | `1..35` |
| Raw sequences | 68,719,476,734 | 68,719,476,734 |
| Symmetry representatives | 506,526,514 | 506,526,514 |
| Covering representatives | 0 | 0 |

Selected final rows are:

| Length | Representatives | Best uncovered count |
| ---: | ---: | ---: |
| 28 | 2,405,236 | 16 |
| 29 | 4,636,390 | 16 |
| 30 | 8,964,800 | 8 |
| 31 | 17,334,801 | 13 |
| 32 | 33,588,234 | 7 |
| 33 | 65,108,062 | 6 |
| 34 | 126,390,032 | 4 |
| 35 | 245,492,244 | 2 |

The best-uncovered column is diagnostic only. The lower bound follows from
complete traversal and exact zero-cover tests, not from the nearcover scores.

### Upper Witness

The attributed witness is retained at `data/baseline-36.txt`. Exact replay
gives:

```text
length: 36
cyclic windows: 36
distinct cyclic windows: 36
ambient targets: 4096
covering radius: 3
uncovered targets at radius 3: 0
```

The exclusion through 35 and this witness prove the theorem.

## Reproduction

Build and run all deterministic checks:

```bash
make
make test
make verify-exact-result
make verify-release-manifest
```

Recompute the C++ exclusion:

```bash
python3 tools/run_exhaustive.py \
  --min-length 1 --max-length 35 --threads 12
```

Recompute the Rust exclusion:

```bash
python3 tools/run_rust_exhaustive.py \
  --min-length 1 --max-length 35 --threads 12
```

Validate retained evidence without rerunning the full searches:

```bash
make test-evidence
```

Full recomputation is CPU-bound. Runtime depends on the machine and current
load. The retained logs record the actual build and run metadata for the
published computations.

The `full-replay` workflow runs both complete traversals on manual dispatch
and on every version tag. The two original macOS arm64 evidence binaries are
planned as GitHub release assets so their SHA-256 values can be checked
against the retained metadata.

## Repository Layout

```text
data/              attributed length-36 witness fixture
docs/              claims, prior art, reproducibility, and research record
evidence/          exhaustive logs, metadata, hashes, and result summary
LICENSES/          complete third-party license texts
paper/             technical report source and submission metadata
research/          machine-readable claim and release-gate records
rust-exhaustive/   independent exhaustive implementation
rust-verifier/     independent exact witness verifier
src/               C++ exhaustive/search code, Python verifier, SAT encoders
tests/             semantic, regression, and release-boundary tests
tools/             evidence runners, checkers, and release tooling
```

## Evidence

The central machine-readable record is
`evidence/result-summary.json`. Its checker validates:

1. all listed artifact hashes;
2. both complete enumeration logs and metadata files;
3. independent per-length Burnside counts;
4. agreement of all 35 C++ and Rust orbit totals;
5. the full raw and representative totals;
6. the length-36 witness; and
7. the reported length-34 and length-35 nearcovers.

Run:

```bash
python3 tools/check_result_summary.py
```

## Licensing And Provenance

The root MIT License covers project-original software and documentation.
`data/baseline-36.txt` is an attributed normalized copy of the public CPro1
result and remains under Apache License 2.0. No CPro1 implementation source is
copied. See `THIRD_PARTY_NOTICES.md` for commit, path, source hash, normalized
hash, and modification details.

## References

1. F. Chung and J. N. Cooper, "De Bruijn cycles for covering codes",
   Random Structures and Algorithms 25 (2004), 421-431.
2. Y. M. Chee, T. Etzion, H. Ta, and V. K. Vu, "Constructions of Covering
   Sequences and 2D-Sequences", Designs, Codes and Cryptography 93 (2025),
   5445-5471, DOI `10.1007/s10623-025-01726-5`.
3. C. D. Rosin, arXiv:2505.23881 (2025).
4. T. Etzion, "Covering Sequences and Covering-Sequences Codes",
   arXiv:2607.14840.
5. H. Ta and V. K. Vu, "Near-Optimal Covering Sequences",
   arXiv:2606.29236.
