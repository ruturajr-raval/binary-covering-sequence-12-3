# Exact-Result Evidence

Status date: 2026-09-07

## Supported Theorem

The retained evidence supports the computational theorem

```text
L(12,3) = 36.
```

The lower bound comes from complete enumeration of every positive binary
cyclic sequence of length at most 35. The upper bound comes from the
attributed 36-bit witness in `data/baseline-36.txt`.

## Exhaustive Totals

| Quantity | Value |
| --- | ---: |
| Lengths excluded | `1..35` |
| Raw binary sequences | 68,719,476,734 |
| Rotation-reversal-complement representatives | 506,526,514 |
| Covering representatives | 0 |
| C++ threads | 12 |
| Rust threads | 12 |
| C++ cumulative recorded wall time | 160.583 seconds |
| Rust cumulative recorded wall time | 421.825 seconds |

Runtime is hardware- and load-dependent. The recorded times are evidence
facts, not performance claims.

## Independent Implementations

The C++ and Rust programs were written separately. Each:

1. enumerates the complete raw sequence space;
2. retains one representative under cyclic rotation, reversal, and bit
   complement;
3. constructs every cyclic length-12 window, including repeated-index
   windows when the sequence length is below 12;
4. unions exact radius-3 Hamming balls over all 4,096 targets; and
5. reports whether any representative covers the complete target space.

For every length from 1 through 35, both programs report the same number of
symmetry representatives. Those counts also match an independent Burnside
calculation performed by the evidence checkers.

## Retained Artifacts

| Artifact | SHA-256 |
| --- | --- |
| `src/exhaustive.cpp` | `e3341e8290eae37c75c3968de93a38b57f7d7763a2db60dc94881b151703a67d` |
| `evidence/cpp-exhaustive-1-35.jsonl` | `1f28c3ff550aa609ed811298c3ccc6099e64e291c563c25b7daf234503c64e1e` |
| `evidence/cpp-exhaustive-1-35.json` | `173636186e17645f44d868bd7c4a1b517664ed16be81635863a91a1fda0b6766` |
| `rust-exhaustive/src/lib.rs` | `86720e27e45cb28404013a413ff5e5d7d2d9935476a6d71d7d77548364c28ea9` |
| `rust-exhaustive/src/main.rs` | `3cc3e81172ef43224cc44a7280043ccf2fb731e773dfff8bf4cf2b5435f20d14` |
| `evidence/rust-exhaustive-1-35.json` | `501b9e2fd2501ac0941521fab992d05e29ce4c82fa33a2af995e5fa92a655701` |
| `evidence/rust-exhaustive-1-35.metadata.json` | `5c792b2058fdfddd342b1f78428d3c5ac045c6bf7dcec3319913137d4ad97c66` |
| `data/baseline-36.txt` | `02bb4681195a71888260f535feaac94f7d45993e6b1ab63199dd369e9bf3eca1` |

The metadata files also bind the build commands, run commands, toolchain
versions, source hashes, binary hashes, thread counts, and log hashes.
The original macOS arm64 C++ and Rust binaries are prepared as versioned
GitHub release assets, allowing the recorded binary hashes to be checked
directly after publication.

| Release asset | SHA-256 |
| --- | --- |
| `binary-covering-sequence-12-3-cpp-exhaustive-v0.1.0-macos-arm64` | `f15b004f88447ce3484457d22b9168e409c671b99ba6c0f9371527fb777838f8` |
| `binary-covering-sequence-12-3-rust-exhaustive-v0.1.0-macos-arm64` | `f2198f1d83b7a1cf8988d095f6e442436e3f5183887e664f236c048072912432` |

After downloading those assets into the project root, authenticate them with:

```bash
python3 tools/check_exhaustive_evidence.py \
  --log evidence/cpp-exhaustive-1-35.jsonl \
  --metadata evidence/cpp-exhaustive-1-35.json \
  --binary binary-covering-sequence-12-3-cpp-exhaustive-v0.1.0-macos-arm64 \
  --min-length 1 --max-length 35
python3 tools/check_rust_exhaustive_evidence.py \
  --log evidence/rust-exhaustive-1-35.json \
  --metadata evidence/rust-exhaustive-1-35.metadata.json \
  --binary binary-covering-sequence-12-3-rust-exhaustive-v0.1.0-macos-arm64 \
  --min-length 1 --max-length 35
```

## Closest Noncovers

The C++ traversal additionally retained one representative with the fewest
uncovered targets at each length.

| Length | Uncovered targets | Representative |
| ---: | ---: | --- |
| 34 | 4 | `0000100101110110011110110100010011` |
| 35 | 2 | `00000100010011111011100111100101011` |

These nearcovers are search diagnostics. They are not used to infer
nonexistence.

## Validation

Validate the complete evidence package:

```bash
make test-evidence
```

Run the small-range implementation checks:

```bash
make test-exhaustive
```

This exhaustively compares the optimized C++ window, coverage, and
canonicality kernels with direct definitions for every sequence of lengths
1 through 8. The Rust tests independently compare optimized coverage and
canonicality with direct implementations on complete small instances.

Recompute the complete searches:

```bash
python3 tools/run_exhaustive.py --min-length 1 --max-length 35 \
  --threads 12
python3 tools/run_rust_exhaustive.py --min-length 1 --max-length 35 \
  --threads 12
```

The complete recomputation replaces the retained logs and metadata only
after each runner validates its new output. Each runner uses an exclusive
lock and a unique ignored staging directory. The log is replaced first and
the metadata, which binds the log hash, is replaced last, so interruption
fails closed rather than silently accepting a mismatched pair.

## Trust Boundary

This is a reproducible computational exclusion, not a formally verified
proof. Its strongest safeguards are complete raw-space traversal, independent
implementations, independent Burnside orbit counts, source- and log-bound
metadata, direct small-range kernel oracles, direct replay of reported
nearcovers, and three executed checks of the length-36 witness. External
mathematical review has not been completed, and the public novelty audit
cannot exclude unpublished or unindexed work.
