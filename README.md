# Exact Binary Covering-Sequence Length `L(12,3)`

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22639691.svg)](https://doi.org/10.5281/zenodo.22639691)

## Project Overview

| Field | Value |
| --- | --- |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981) |
| Field | Coding theory, de Bruijn graphs, and exhaustive combinatorial search |
| Problem | Determine the binary cyclic covering-sequence length `L(12,3)` |
| Current result | Exact computer-assisted theorem `L(12,3) = 36` |
| Result type | Complete finite exclusion through length 35 plus a verified length-36 witness |
| Release | `v0.1.0` |
| Version DOI | [`10.5281/zenodo.22639692`](https://doi.org/10.5281/zenodo.22639692) |
| Concept DOI | [`10.5281/zenodo.22639691`](https://doi.org/10.5281/zenodo.22639691) |
| License | MIT for project-original material; Apache-2.0 for the attributed witness fixture |

This repository gives the complete computational record, independently
implemented exhaustive exclusions, exact witness verification, retained
evidence, technical report, and archival metadata for the determination of
`L(12,3)`.

## Problem And Background

An `(n,R)` binary covering sequence is a positive-length cyclic binary
sequence whose length-`n` cyclic windows cover every word in `{0,1}^n`
within Hamming distance `R`. Chung and Cooper introduced the subject in
2004.

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

The minimum possible positive length is denoted by `L(12,3)`.

## Starting Frontier And Longstanding Gap

Chee, Etzion, Ta, and Vu recorded `34 <= L(12,3) <= 40` in their 2025
table. Rosin's CPro1 project later supplied a public 36-bit construction,
leaving the finite gap

```text
34 <= L(12,3) <= 36.
```

That gap remained unresolved for about one year from the 2025 construction
to the public-source audit on 2026-09-07. The audit located no earlier public
exclusion of lengths 34 and 35 and no earlier exact determination of this
cell.

| Date | Result | Role |
| --- | --- | --- |
| 2004 | Covering de Bruijn sequences introduced | General origin |
| 2025 | `34 <= L(12,3) <= 40` | Published table |
| 2025 | Explicit length-36 construction | Public upper bound |
| 2026-09-07 | `34 <= L(12,3) <= 36` | Audited starting frontier |
| 2026-09-07 | `L(12,3) = 36` | Result of this project |

The earlier lower endpoint is not needed for the final theorem because the
exhaustive traversal directly excludes every positive length from 1 through
35.

## Main Result

**Main theorem.**

```text
L(12,3) = 36.
```

The project exhaustively enumerated every binary sequence of every positive
length from 1 through 35. Rotation, reversal, and bit complement reduce
`68,719,476,734` raw sequences to `506,526,514` representatives. A C++
implementation and a separately written Rust implementation both found zero
covering representatives. Their per-length orbit counts agree with each
other and with independent Burnside calculations.

The attributed 36-bit sequence

```text
010100011011000110111110101110010000
```

has 36 distinct cyclic windows, covering radius exactly 3, and no uncovered
target. Python and Rust reproduce every listed value. C++ independently
confirms all 4,096 targets covered and zero uncovered targets at radius 3.
The complete exclusion through length 35 and this verified witness prove the
theorem.

## Method And Proof Architecture

### Symmetry Reduction

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

## Verification And Evidence

The lower-bound computation has two independently implemented enumeration
paths. Each traverses the complete raw space, tests one
rotation-reversal-complement representative per orbit, constructs exact
cyclic windows, and unions exact radius-3 Hamming balls over all 4,096
targets.

Direct target-based and full-orbit oracles check the optimized C++ and Rust
kernels on complete small instances. Independent evidence checkers verify
the raw counts, two separately implemented Burnside formulas, source and log
hashes, metadata, and the reported closest noncovers. Retained evidence
validation also executes the Python, Rust, and C++ witness paths.

The central machine-readable record is `evidence/result-summary.json`. Its
checker validates:

1. all listed artifact hashes;
2. both complete enumeration logs and metadata files;
3. independent per-length Burnside counts;
4. agreement of all 35 C++ and Rust orbit totals;
5. the full raw and representative totals;
6. the length-36 witness; and
7. the reported length-34 and length-35 nearcovers.

The evidence is documented in `evidence/README.md` and bound by
`release-manifest.sha256`. The complete traversals are CPU-bound, use a
configurable multicore worker count, require no GPU, and are suitable for a
commodity multicore workstation. The retained 12-thread runs completed in
under ten minutes per implementation on the recorded macOS arm64 system.

Public tag CI `34102838139` rebuilt and checked the tagged package. Full
replay and release workflow `34102838143` independently recomputed the C++
and Rust exclusions, rebuilt the report from the tag, verified all staged
asset digests, and published the release only after every gate passed.

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
python3 tools/check_result_summary.py
```

Full recomputation is CPU-bound. Runtime depends on the machine and current
load. The retained logs record the actual build and run metadata for the
published computations.

The `full-replay` workflow runs both complete traversals on manual dispatch
and on every version tag. For a tag, it verifies a staged draft release
against the immutable tag tree, rebuilds the report from that tree and checks
the staged PDF byte-for-byte, and publishes the release only after the C++
and Rust full replays succeed. It requires the exact remote asset set, checks
GitHub's SHA-256 digests before and after publication, and requires release
immutability after publication. The two original macOS arm64 evidence
binaries are published as versioned GitHub release assets so their SHA-256
values can be checked against the retained metadata.

## Claims

The repository claims the exact value `L(12,3) = 36` under the explicit
convention that sequence lengths are positive and window indices are reduced
modulo the sequence length, including when the sequence is shorter than 12.

The lower bound is a complete exclusion of every positive length through 35.
The upper bound is the exact verification of an attributed prior-art
length-36 witness. Nearcovers, heuristic search, and solver timeouts are not
used in the theorem.

## Limitations And Nonclaims

The length-36 witness is prior art and is not claimed as original. The
project does not claim a complete classification of all optimal sequences,
formal verification in a proof assistant, or external mathematical review.
It does not claim priority over unpublished, inaccessible, or unindexed
work.

The principal limitation is computational trust. The programs are tested,
sanitized, source-bound, and independently reproduced, but they are not
formally verified.

## Significance And Use

The result closes a finite coding-theory table entry by excluding both
remaining shorter lengths. It supplies an exact reference value, a
reproducible exhaustive-search design, and independently checked evidence
that can support future covering-sequence tables and comparisons.

The same raw-space traversal, symmetry reduction, bitset coverage, Burnside
audit, and cross-implementation method form a reusable framework for nearby
covering-sequence cells.

## Remaining Work And Future Directions

Natural extensions include:

- reconstructing the symmetry and coverage kernels in a proof assistant;
- developing compressed certificates for exhaustive traversals;
- classifying all optimal length-36 sequences; and
- applying the exact method to adjacent unresolved parameters.

The main limitation is that the computational proof has not been reconstructed
in a proof assistant. The next route is therefore a formally checked version
of the symmetry and coverage kernels, followed by classification of all
optimal length-36 sequences. These directions do not affect the completed
theorem or the archived release.

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

## Publication Citation And Archive

The public repository is
[`ruturajr-raval/binary-covering-sequence-12-3`](https://github.com/ruturajr-raval/binary-covering-sequence-12-3).
The immutable tagged release is
[`v0.1.0`](https://github.com/ruturajr-raval/binary-covering-sequence-12-3/releases/tag/v0.1.0)
at audited release commit
`4a0475571637634067e68b4ab80cb972833c48b4`.

The release is archived at version DOI
[`10.5281/zenodo.22639692`](https://doi.org/10.5281/zenodo.22639692). The
stable all-versions DOI is
[`10.5281/zenodo.22639691`](https://doi.org/10.5281/zenodo.22639691).
Zenodo contains the same five release files, which were downloaded and
checked byte-for-byte against the local release set. GitHub reports the
release as immutable.

Citation metadata is in `CITATION.cff`, the technical report source and
submission metadata are in `paper/`, the release dossier is in
`PUBLICATION.md`, and release history is in `RELEASE_NOTES.md`.

## Authorship

**Ruturaj R Raval**

Independent Researcher

ORCID: [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981)

## Licensing And Provenance

Project-original code, evidence tooling, and documentation are MIT licensed.
The root `LICENSE` contains the applicable terms.

`data/baseline-36.txt` is an attributed normalized copy of the public CPro1
result and remains under Apache License 2.0. No CPro1 implementation source
is copied. Its source is CPro1 commit
`827f02b4048fc96a6b79f0970c87ca5a54f31f40`, path
`designs/covering-sequence/result-12-3-36-seed1000.txt`.

The fixture's provenance, source hash, normalized hash, modification details,
and full license terms are retained in `THIRD_PARTY_NOTICES.md` and
`LICENSES/Apache-2.0.txt`.

## References

1. F. Chung and J. N. Cooper, "De Bruijn cycles for covering codes",
   Random Structures and Algorithms 25 (2004), 421-431.
2. Y. M. Chee, T. Etzion, H. Ta, and V. K. Vu, "Constructions of Covering
   Sequences and 2D-Sequences", Designs, Codes and Cryptography 93 (2025),
   5445-5471, DOI `10.1007/s10623-025-01726-5`.
3. C. D. Rosin, "Using Reasoning Models to Generate Search Heuristics that
   Solve Open Instances of Combinatorial Design Problems",
   arXiv:2505.23881v1 (2025), DOI `10.48550/arXiv.2505.23881`.
4. T. Etzion, "Covering Sequences and Covering-Sequences Codes",
   arXiv:2607.14840.
5. H. Ta and V. K. Vu, "Near-Optimal Covering Sequences",
   arXiv:2606.29236.
