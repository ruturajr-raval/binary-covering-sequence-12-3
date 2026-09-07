# Rust Exhaustive Checker

This directory contains a standalone exhaustive checker for binary cyclic
`(12,3)` covering sequences. It uses only the Rust standard library and does
not share implementation code with the other project tools.

For each requested sequence length, the checker enumerates every binary
sequence but evaluates coverage only for the lexicographically least member
of each orbit under:

- cyclic rotation
- reversal
- bitwise complement
- every composition of these operations

The exhaustive hot path tests canonicality lexicographically and stops as soon
as a smaller transformed sequence is found. The retained `canonical_form`
implementation constructs complete transforms independently for tests and
orbit utilities.

Coverage is exact. The checker precomputes the radius-3 coverage bitset for
each of the 4,096 possible windows once, then shares that immutable table
across workers. A candidate is evaluated by OR-ing the bitsets for its cyclic
length-12 windows. Threads receive disjoint integer intervals, and their exact
counts are combined after all workers finish.

## Commands

Run these commands from the repository root. Check one length:

```bash
cargo run --release --manifest-path rust-exhaustive/Cargo.toml -- \
  --length 12 --threads 8
```

Check an inclusive range:

```bash
cargo run --release --manifest-path rust-exhaustive/Cargo.toml -- \
  --range 4:12 --threads 8
cargo run --release --manifest-path rust-exhaustive/Cargo.toml -- \
  --range 4..=12 --threads 8
```

The program emits one JSON document containing:

- the total number of labeled binary sequences
- the number of full-symmetry orbit representatives
- the number of covering representatives
- the number of labeled covering sequences represented by those orbits
- the lexicographically least covering representative, if one exists
- elapsed milliseconds for each length

Lengths from 1 through 63 are accepted. Runtime remains exponential, so large
lengths require an explicit computational plan rather than an ordinary local
run.

The release evidence was produced on a 64-bit environment with Rust 1.96.1.
The crate declares Rust 1.85 as its minimum supported toolchain.

## Exact Release Run

Build, run, validate, and retain the complete `1..35` result:

```bash
python3 tools/run_rust_exhaustive.py \
  --min-length 1 --max-length 35 --threads 12
```

Expected totals:

```text
raw sequences: 68719476734
symmetry representatives: 506526514
covering representatives: 0
```

The runner writes:

```text
evidence/rust-exhaustive-1-35.json
evidence/rust-exhaustive-1-35.metadata.json
```

It validates temporary output before atomically replacing retained evidence.
The metadata binds the complete source set, release binary, commands,
toolchain, thread count, and log by SHA-256.

## Tests

```bash
cargo test --manifest-path rust-exhaustive/Cargo.toml
cargo clippy --manifest-path rust-exhaustive/Cargo.toml \
  --all-targets -- -D warnings
cargo fmt --manifest-path rust-exhaustive/Cargo.toml -- --check
```

The tests compare optimized canonicality with `canonical_form`, compare the
bitset coverage calculation against a separate target-by-target
Hamming-distance implementation, verify a known length-36 fixture, check
complete symmetry-orbit invariance, compare small-length orbit counts with an
independent Burnside calculation, and compare serial with threaded exhaustive
counts.
