# Claims And Nonclaims

Status date: 2026-09-07

## Main Claim

For positive-length cyclic binary sequences, with every window index reduced
modulo the sequence length even when that length is below 12,

```text
L(12,3) = 36.
```

This is a reproducible computer-assisted theorem.

## Lower Bound

Two separately written exhaustive programs checked every positive length from
1 through 35.

| Quantity | Value |
| --- | ---: |
| Raw binary sequences | 68,719,476,734 |
| Rotation-reversal-complement representatives | 506,526,514 |
| Covering representatives | 0 |

The C++ and Rust programs independently:

1. traverse the complete raw sequence space;
2. retain one representative under rotation, reversal, and complement;
3. construct the exact cyclic length-12 windows;
4. union exact radius-3 Hamming balls over all 4,096 targets; and
5. reject every representative.

Their per-length representative counts agree for all 35 lengths. Each
evidence checker also computes the expected counts from an independently
implemented Burnside formula.

Therefore no binary `(12,3)` covering sequence has positive length at most
35, so

```text
L(12,3) >= 36.
```

## Upper Bound

The attributed CPro1 witness

```text
010100011011000110111110101110010000
```

has:

```text
length = 36
distinct cyclic windows = 36
covered targets = 4096 / 4096
covering radius = 3
uncovered targets = 0
```

Python, Rust, and C++ verifiers independently reproduce these facts.
Therefore

```text
L(12,3) <= 36.
```

Combining the lower and upper bounds proves the main claim.

## Evidence Binding

The machine-readable theorem record is `evidence/result-summary.json`.
`tools/check_result_summary.py` binds and validates:

- the C++ source, log, metadata, and hashes;
- the Rust source set, log, metadata, and hashes;
- every per-length raw and orbit count;
- both independent Burnside calculations;
- the complete totals;
- the upper-bound witness; and
- the reported closest noncovers at lengths 34 and 35.

The complete repository package is additionally bound by
`release-manifest.sha256`.

## Exact Nonclaims

- The 36-bit witness is not claimed as project-original.
- The exhaustive programs are not formally verified.
- The computation is not represented by a compact SAT, DRAT, LRAT, or
  proof-assistant certificate.
- The length-34 and length-35 nearcovers are not part of the lower-bound
  argument.
- No solver timeout, failed heuristic run, or search stagnation is treated as
  evidence of nonexistence.
- No classification or count of all optimal length-36 sequences is claimed.
- No result is claimed for a different alphabet, window length, radius, or
  noncyclic convention.
- No external mathematical or peer review is claimed.
- No priority claim is made over unpublished, private, deleted, or unindexed
  work.

## Trust Boundary

The theorem depends on finite computation. Risk is reduced by:

- complete raw-space traversal rather than incomplete search;
- independent C++ and Rust implementations;
- exact bitset coverage over all 4,096 targets;
- two independent Burnside formulas;
- direct Hamming-distance oracle tests;
- sanitizer, unit, formatting, and lint checks;
- source-, binary-, and log-bound metadata;
- deterministic package checksums; and
- three independent upper-witness verifiers.

These measures support reproducibility and fault detection. They do not
replace formal verification or independent external review.

## Significance

The historical starting frontier was

```text
34 <= L(12,3) <= 36.
```

The complete exclusion of lengths 34 and 35 closes that table entry. The
enumeration, symmetry, evidence, and cross-implementation framework can also
support exact work on nearby covering-sequence parameters.
