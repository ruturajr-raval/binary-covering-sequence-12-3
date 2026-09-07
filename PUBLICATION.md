# Publication Dossier

## Release Identity

| Field | Value |
| --- | --- |
| Title | Exact Determination of the Binary Covering-Sequence Length L(12,3) |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981) |
| Candidate version | `v0.1.0` |
| Package status | not yet released |
| Planned repository | `ruturajr-raval/binary-covering-sequence-12-3` |
| License | MIT for project-original material; Apache-2.0 for the attributed witness |

## Supported Result

Two separately implemented exhaustive programs exclude every positive binary
cyclic sequence length from 1 through 35 for window length 12 and Hamming
radius 3. They scan `68,719,476,734` raw sequences through `506,526,514`
rotation-reversal-complement representatives and find no cover. Every
per-length representative count agrees between C++ and Rust and with two
independent Burnside calculations. Three verifier paths confirm the
attributed length-36 witness. The supported result is:

```text
L(12,3) = 36.
```

## Significance And Reuse

The result closes the finite gap left by the published lower bound 34 and the
public upper bound 36. The independent raw-space traversal, symmetry
reduction, exact bitset coverage, Burnside accounting, and source-bound
evidence checks form a reusable architecture for nearby covering-sequence
cells. The retained nearcovers are diagnostics and may also guide structural
or certificate-based follow-up work.

## Verification And Evidence

The package includes independently written C++ and Rust exhaustive
implementations, complete logs, toolchain and command metadata, source and
binary hashes, two evidence checkers, a machine-readable result summary,
sanitizer tests, direct small-range oracles for both optimized exhaustive
kernels, and Python, Rust, and C++ witness verifiers that are executed during
retained-evidence validation. `release-manifest.sha256` authenticates the
publication surface.

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

The complete traversals are CPU-bound, need no GPU, and are intended for a
commodity multicore workstation. The retained 12-thread runs completed in
under ten minutes per implementation on the recorded macOS arm64 system.

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
complete upstream license text is included, and no upstream implementation
source is copied.

## Review Status

The candidate has passed local mathematical-scope review, adversarial source
review, independent full replay, Burnside-count review, witness review,
direct-oracle checks, sanitizer checks, unit tests, lint and formatting
checks, package-boundary checks, and claim/nonclaim review. No external
mathematical or peer review is claimed.

## Remaining Work And Next Acceptance Gate

The theorem and retained evidence are complete, but the package is not yet
released. The next acceptance gate is a clean public-history import, passing
public CI, a protected immutable tag, complete tagged replay, matching release
assets verified byte-for-byte against the tag tree, a release PDF matching a
fresh tagged-source build, remote asset-digest agreement, immutable release
assets, and durable archival. Later research can pursue proof-assistant
reconstruction, compact exclusion certificates, classification of optimal
length-36 sequences, and adjacent parameter cells.

## Public Summary

Independent C++ and Rust traversals exclude all `68,719,476,734` binary
sequences of positive lengths through 35 after independently checked symmetry
reduction. A public attributed 36-bit witness is verified exactly. Together
these results establish the computer-assisted theorem `L(12,3) = 36`.

## Archive And Citation

The package is not yet released or archived, and its version and concept
identifiers remain unassigned. `CITATION.cff` contains the planned citation
metadata and `RELEASE_NOTES.md` records the current unreleased state. Archive
identifiers and immutable release details will be added only after those
records exist.
