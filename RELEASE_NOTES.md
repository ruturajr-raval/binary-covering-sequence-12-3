# Release Notes

## Unreleased

### Result

The current candidate establishes the exact computer-assisted theorem
`L(12,3) = 36`. It exhaustively excludes every positive binary sequence
length from 1 through 35 and independently verifies the attributed 36-bit
witness.

### Verification

Separately written C++ and Rust implementations traverse `68,719,476,734` raw
sequences through `506,526,514` rotation-reversal-complement representatives
and find zero covers. All 35 per-length orbit counts agree with two
independent Burnside calculations. Retained logs, metadata, hashes, evidence
checkers, sanitizer tests, witness verifiers, and a deterministic manifest
support replay.

### Claim Boundary

The witness is prior art and is not claimed as original. Formal verification,
classification of all optimal sequences, external mathematical review, and
priority over unpublished work are not claimed. Nearcovers and solver
timeouts are not used as proof.

### Next Gate

The package remains not yet released. Publication requires clean public
history, passing public CI, a protected immutable tag, complete tagged replay,
matching release assets, and durable archival.
