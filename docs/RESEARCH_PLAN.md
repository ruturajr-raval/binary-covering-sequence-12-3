# Research Record And Future Work

Status date: 2026-09-07

## Objective

The original objective was to determine or improve the finite frontier for
the binary covering-sequence length `L(12,3)`.

The starting frontier was

```text
34 <= L(12,3) <= 36.
```

The objective is complete:

```text
L(12,3) = 36.
```

## Completed Baseline

- Audited the 2025 finite table and recorded its `34..40` interval.
- Located and pinned the public CPro1 length-36 witness.
- Retained the normalized witness with source and normalized hashes.
- Added independent Python, Rust, and C++ verifier paths.
- Verified all 4,096 target words, including the all-ones endpoint omitted
  by the audited upstream verifier loop.
- Added direct and compact SAT formulations for exploratory construction and
  proof-producing search.
- Added a C++ heuristic construction search and exact coverage-state tests.

## Completed Exact Exclusion

- Implemented complete C++ raw-space enumeration for positive lengths
  `1..35`.
- Implemented a separate complete Rust enumeration.
- Proved and implemented rotation-reversal-complement reduction.
- Added independently implemented Burnside count calculations.
- Checked all `68,719,476,734` raw sequences through
  `506,526,514` symmetry representatives.
- Found zero covering representative at every length through 35.
- Retained source-, binary-, command-, and log-bound evidence.
- Added cross-implementation, sanitizer, oracle, lint, formatting, and
  package-boundary tests.
- Refreshed the public prior-art audit on 2026-09-07.
- Completed an adversarial code review and a separate mathematical audit.

## Acceptance Gate

The exact-result gate requires:

1. complete exclusion of every positive length below 36;
2. an independently verified length-36 witness;
3. at least two separately implemented lower-bound computations;
4. independently checked symmetry-orbit completeness;
5. source- and log-bound retained evidence;
6. a refreshed public-source audit;
7. precise claims and nonclaims;
8. clean-checkout replay and passing CI; and
9. publication-ready provenance and license records.

Items 1 through 7 are complete. Items 8 and 9 are final release-engineering
steps rather than open mathematical work.

## Why Direct Enumeration Is Sufficient

The earlier plan emphasized proof-producing SAT because the search cost was
initially uncertain. The final direct enumeration is stronger and simpler for
this finite instance:

- it traverses every raw binary sequence;
- symmetry removal is independently count-checked;
- coverage is evaluated exactly;
- a second implementation repeats the complete result; and
- no solver status or timeout is used.

A SAT proof log is therefore not required for the supported theorem. A
compact formal certificate would still be valuable future work.

## Future Research

### Formal Reconstruction

Formalize the symmetry action, Burnside count, cyclic-window semantics, and
Hamming-ball coverage kernel in a proof assistant. This would reduce the
trusted computation boundary.

### Certificate Compression

Investigate whether the exclusion can be represented by a compact
proof-producing SAT decomposition, decision diagram, or independently
checkable orbit certificate rather than complete program rerun.

### Optimal-Sequence Classification

Enumerate or classify length-36 covering sequences up to rotation, reversal,
and complement. The current theorem establishes existence and optimality but
does not count optimal orbits.

### Neighboring Cells

Apply the same implementation pair and evidence design to adjacent unresolved
covering-sequence parameters. Priority should favor cells whose complete
symmetry-reduced space is finite enough for independent replay.

### Structural Analysis

Study the retained length-34 four-hole and length-35 two-hole nearcovers.
Their uncovered-target geometry may reveal structural lower-bound lemmas that
generalize beyond this one cell.

## Limitations

- The theorem is computer-assisted, not formally verified.
- Full reruns are CPU-bound.
- The novelty audit is bounded to accessible public sources.
- No external peer review has been completed.
- The attributed upper witness remains third-party material under
  Apache-2.0.

These limitations do not change the finite logical implication of the
validated computation, but they define the correct release wording and future
review priorities.
