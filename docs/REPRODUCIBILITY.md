# Reproducibility

Status date: 2026-09-07

## Scope

The package supports the exact computer-assisted theorem

```text
L(12,3) = 36.
```

The lower bound is a complete raw-space exclusion through length 35. The
upper bound is a direct verification of an attributed length-36 witness.

## Requirements

- a 64-bit Unix-like environment;
- Python 3.9 or newer;
- a C++20 compiler with standard threads;
- Rust and Cargo;
- sufficient CPU time for the optional full recomputation.

The retained full C++ run used Apple clang 21.0.0. The retained full Rust run
used `rustc 1.96.1` and `cargo 1.96.1`. Exact toolchain strings, commands,
thread counts, binary hashes, source hashes, and log hashes are in the two
metadata files under `evidence/`.

## Fast Verification

Build all implementations and run the complete deterministic test suite:

```bash
make
make test
```

Verify the upper witness and retained lower-bound evidence:

```bash
make verify-exact-result
```

Verify the deterministic release package:

```bash
make verify-release-manifest
```

## Retained Evidence

The central record is:

```text
evidence/result-summary.json
```

Validate it directly:

```bash
python3 tools/check_result_summary.py
```

This checks the artifact hashes, both complete logs and metadata records, the
independent Burnside counts, the complete totals, the closest noncovers, and
the length-36 witness.

The retained complete totals are:

```text
raw sequences: 68719476734
symmetry representatives: 506526514
covering representatives: 0
```

## Small-Range Reimplementation Checks

The default test suite reruns both exhaustive implementations on lengths
1 through 18 and validates the output:

```bash
make test-exhaustive
```

The C++ source can also be checked with address and undefined-behavior
sanitizers on a supported toolchain:

```bash
mkdir -p build
c++ -std=c++20 -O1 -g \
  -fsanitize=address,undefined -fno-omit-frame-pointer \
  -Wall -Wextra -Wpedantic -Werror -pthread \
  src/exhaustive.cpp -o build/exhaustive-sanitize
ASAN_OPTIONS=detect_leaks=0 \
  build/exhaustive-sanitize 1 20 4 \
  > build/exhaustive-sanitize.jsonl
python3 tools/check_exhaustive_evidence.py \
  --log build/exhaustive-sanitize.jsonl \
  --min-length 1 --max-length 20
```

Leak detection may be enabled on platforms that support it.

## Full C++ Recalculation

```bash
python3 tools/run_exhaustive.py \
  --min-length 1 \
  --max-length 35 \
  --threads 12 \
  --log evidence/cpp-exhaustive-1-35.jsonl \
  --metadata evidence/cpp-exhaustive-1-35.json
```

The runner:

1. compiles `src/exhaustive.cpp` with warnings denied;
2. writes the new output to a temporary file;
3. validates every per-length count and best sequence;
4. atomically replaces the retained log;
5. writes source-, binary-, command-, and log-bound metadata;
6. validates the metadata before replacing the retained record.

## Full Rust Recalculation

```bash
python3 tools/run_rust_exhaustive.py \
  --min-length 1 \
  --max-length 35 \
  --threads 12 \
  --log evidence/rust-exhaustive-1-35.json \
  --metadata evidence/rust-exhaustive-1-35.metadata.json
```

The Rust runner follows the same temporary-output and metadata-validation
sequence. The Rust implementation has no external crate dependencies.

## Upper-Bound Replay

```bash
python3 src/verify.py data/baseline-36.txt \
  --n 12 --radius 3 --expected-length 36 --json

cargo run --release --manifest-path rust-verifier/Cargo.toml -- \
  --n 12 --radius 3 --expected-length 36 \
  --file data/baseline-36.txt

build/search --length 36 \
  --verify 010100011011000110111110101110010000
```

All three paths must report a valid length-36 sequence with zero uncovered
targets. The Python and Rust verifiers also report covering radius exactly 3.

## Completeness Checks

For each length `L`, the exhaustive programs inspect all `2^L` bit strings.
They reject a string only when a rotation, reversal, complemented rotation,
or complemented reversal is smaller. Every symmetry orbit has a minimum, so
at least one representative remains. The observed representative count must
also equal the Burnside count, independently computed by both evidence
checkers.

Coverage is invariant under all three symmetries. Therefore testing every
retained representative is sufficient to exclude every raw sequence.

## Resource Profile

The retained 12-thread runs recorded cumulative per-length wall times of
about 161 seconds for C++ and 422 seconds for Rust. These are not benchmark
claims. Runtime varies with processor, compiler, thread scheduling, and
concurrent load. The search uses modest memory because coverage is represented
by fixed 4,096-bit sets and candidates are processed in streaming order.

The GitHub `full-replay` workflow recomputes both complete traversals when
manually dispatched and whenever a version tag is pushed. The original
macOS arm64 evidence binaries are release assets whose SHA-256 values match
the binary hashes in the retained metadata.

## Trust Boundary

The C++ and Rust enumerators are independent at the implementation level.
The two evidence checkers use separate Burnside formulas. Direct target-based
oracles test the optimized Rust coverage kernel, and the C++ run has sanitizer
coverage on reduced ranges.

The computation is still trusted code rather than a proof-assistant kernel.
The retained logs do not list every representative because that would be
impractically large. Reproducibility therefore depends on source review,
independent rerun, exact aggregate counts, and checksum binding.
