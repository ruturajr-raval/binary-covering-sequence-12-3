# Release Notes

## [v0.1.0](https://github.com/ruturajr-raval/binary-covering-sequence-12-3/releases/tag/v0.1.0) - 2026-09-07

### Result

This release establishes the exact computer-assisted theorem
`L(12,3) = 36`. It exhaustively excludes every positive binary sequence
length from 1 through 35 and independently verifies the attributed 36-bit
witness.

### Verification

Separately written C++ and Rust implementations traverse `68,719,476,734` raw
sequences through `506,526,514` rotation-reversal-complement representatives
and find zero covers. All 35 per-length orbit counts agree with two
independent Burnside calculations. Retained logs, metadata, hashes, evidence
checkers, direct C++ and Rust small-range oracles, sanitizer tests, executed
Python, Rust, and C++ witness verifiers, and a deterministic manifest support
replay.

### Claim Boundary

The witness is prior art and is not claimed as original. Formal verification,
classification of all optimal sequences, external mathematical review, and
priority over unpublished work are not claimed. Nearcovers and solver
timeouts are not used as proof.

### Release And Archive

- Tagged release:
  `https://github.com/ruturajr-raval/binary-covering-sequence-12-3/releases/tag/v0.1.0`
- Audited release commit:
  `4a0475571637634067e68b4ab80cb972833c48b4`
- Public tag CI: `34102838139`
- Full tagged replay and release workflow: `34102838143`
- Version DOI: `10.5281/zenodo.22639692`
- Stable concept DOI: `10.5281/zenodo.22639691`

The protected tag points at the audited commit. GitHub reports the published
release as immutable. The tagged workflow rebuilt the report from the tag,
verified all five assets and GitHub SHA-256 digests, and published only after
the independent C++ and Rust complete traversals passed. The five Zenodo files
were subsequently downloaded and matched against the local release set by
size, MD5, and SHA-256.
