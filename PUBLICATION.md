# Release v0.1.0

## Release Identity

| Field | Value |
| --- | --- |
| Title | Exact Determination of the Binary Covering-Sequence Length L(12,3) |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981) |
| Tagged release | [`v0.1.0`](https://github.com/ruturajr-raval/binary-covering-sequence-12-3/releases/tag/v0.1.0) |
| Release date | 2026-09-07 |
| Audited release commit | `4a0475571637634067e68b4ab80cb972833c48b4` |
| Version DOI | [`10.5281/zenodo.22639692`](https://doi.org/10.5281/zenodo.22639692) |
| Concept DOI | [`10.5281/zenodo.22639691`](https://doi.org/10.5281/zenodo.22639691) |
| Archive status | Published five-file Zenodo record matching the immutable GitHub release |
| Protected tag ruleset | `22432924` |
| Public tag CI | `34102838139` |
| Full tagged replay and release | `34102838143` |
| License | MIT for project-original material; Apache-2.0 for the attributed witness |

## Supported Result

Two separately implemented exhaustive programs exclude every positive binary
cyclic sequence length from 1 through 35 for window length 12 and Hamming
radius 3. They scan `68,719,476,734` raw sequences through `506,526,514`
rotation-reversal-complement representatives and find no cover. Every
per-length representative count agrees between C++ and Rust and with two
independent Burnside calculations. Python, Rust, and C++ verifier paths
confirm the attributed length-36 witness. The supported result is:

```text
L(12,3) = 36.
```

## Significance And Reuse

The result closes the finite gap left by the published lower bound 34 and the
public upper bound 36. The independent raw-space traversal, symmetry
reduction, exact bitset coverage, Burnside accounting, and source-bound
evidence checks form a reusable architecture for nearby covering-sequence
cells. The retained nearcovers are diagnostics and may guide structural,
classification, or certificate-based follow-up work.

## Verification And Evidence

The package includes independently written C++ and Rust exhaustive
implementations, complete logs, toolchain and command metadata, source and
binary hashes, two evidence checkers, a machine-readable result summary,
sanitizer tests, direct small-range oracles for both optimized exhaustive
kernels, and Python, Rust, and C++ witness verifiers.
`release-manifest.sha256` authenticates the maintained `main` publication
surface.

Fast replay:

```bash
make
make test
make verify-exact-result
make verify-release-manifest
```

Complete recomputation:

```bash
python3 tools/run_exhaustive.py --min-length 1 --max-length 35 \
  --threads 12
python3 tools/run_rust_exhaustive.py --min-length 1 --max-length 35 \
  --threads 12
```

Public tag CI `34102838139` passed against audited commit
`4a0475571637634067e68b4ab80cb972833c48b4`. Full replay workflow
`34102838143` independently reran both complete traversals. The Rust job
completed in 15 minutes 32 seconds and the C++ job in 16 minutes 33 seconds
on the hosted runners. The release job then rebuilt the report from the
protected tag, checked the PDF byte-for-byte, verified the exact remote asset
set and every GitHub SHA-256 digest, and published only after all gates
passed. GitHub reports the release as immutable.

## Claim Boundary

The exact value is supported under the documented convention that sequence
lengths are positive and every window index is reduced modulo the sequence
length, including lengths below 12. The length-36 witness is prior art and is
not claimed as original. Formal verification, classification of all optimal
sequences, external mathematical review, and priority over unpublished or
unindexed work are not claimed. Nearcovers, heuristic search, and solver
timeouts are not theorem evidence.

## Provenance Boundary

The exhaustive implementations, evidence tools, tests, report, and
documentation are project-original and MIT licensed. The normalized
length-36 witness is attributed to CPro1 and remains under Apache-2.0. The
complete upstream license text, source commit, hashes, and normalization
details are retained. No upstream implementation source is copied.

## Review Status

The release passed local mathematical-scope review, adversarial source and
claim review, independent full replay, Burnside-count review, witness review,
direct-oracle checks, sanitizer checks, unit tests, lint and formatting
checks, package-boundary checks, tag-tree reconstruction, remote digest
verification, and public archive verification. The public Zenodo files were
downloaded and matched against the local release set by size, MD5, and
SHA-256. No external mathematical or peer review is claimed.

## Remaining Work And Next Acceptance Gate

The `v0.1.0` theorem and release lifecycle are complete. The principal
remaining limitation is computational trust: the independent implementations
are extensively tested and reproduced but are not formally verified.

The next research acceptance gate is one of:

1. a checked classification of all optimal length-36 sequences;
2. a substantially smaller independently verifiable exclusion certificate;
3. a proof-assistant reconstruction of the symmetry and coverage kernels; or
4. an exact improvement for an adjacent unresolved covering-sequence cell.

## Public Summary

Independent C++ and Rust traversals exclude all `68,719,476,734` binary
sequences of positive lengths through 35 after independently checked symmetry
reduction. A public attributed 36-bit witness is verified exactly. Together
these results establish the computer-assisted theorem `L(12,3) = 36`.

## Release And Archive

- Public repository:
  `https://github.com/ruturajr-raval/binary-covering-sequence-12-3`
- GitHub release:
  `https://github.com/ruturajr-raval/binary-covering-sequence-12-3/releases/tag/v0.1.0`
- Audited release commit:
  `4a0475571637634067e68b4ab80cb972833c48b4`
- Version DOI: `10.5281/zenodo.22639692`
- Stable concept DOI: `10.5281/zenodo.22639691`

Release assets:

| Asset | Size | SHA-256 |
| --- | ---: | --- |
| `SHA256SUMS` | 491 | `aede477377c2d9cabe6ff00fc99d667573823354a6ec5f7a6f6eabaae40c292e` |
| `binary-covering-sequence-12-3-cpp-exhaustive-v0.1.0-macos-arm64` | 40,008 | `f15b004f88447ce3484457d22b9168e409c671b99ba6c0f9371527fb777838f8` |
| `binary-covering-sequence-12-3-paper-v0.1.0.pdf` | 219,281 | `ca33e48929b0f26f24b295ec60d8abf39f161ef46b9dd46c25aa29d7aff52429` |
| `binary-covering-sequence-12-3-rust-exhaustive-v0.1.0-macos-arm64` | 500,352 | `f2198f1d83b7a1cf8988d095f6e442436e3f5183887e664f236c048072912432` |
| `binary-covering-sequence-12-3-source-v0.1.0.tar.gz` | 100,932 | `4adcc04ae2d4597de3e6fa43ea48f204dc89486051d0af51487b5dbb44c5a742` |

Zenodo record `22639692` contains the same five files. Both DOI redirects
resolve to that public record. Citation metadata is in `CITATION.cff`, and
historical release scope is recorded in `RELEASE_NOTES.md`.
