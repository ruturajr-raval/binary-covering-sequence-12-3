# Submission Metadata

## Status

The source is submission-ready after the immutable release and archive
identifiers are inserted. No arXiv identifier is currently assigned.

## Title

Exact Determination of the Binary Covering-Sequence Length `L(12,3)`

## Author

Ruturaj R Raval

Independent Researcher

ORCID: `0000-0003-4930-8981`

## Categories

- Primary: `math.CO`
- Secondary: `cs.DM`, `cs.IT`

## Abstract

An `(n,R)` binary covering sequence is a positive-length cyclic binary
sequence whose length-`n` windows cover every binary word of length `n`
within Hamming distance `R`. The published finite frontier for the parameter
`(12,3)` was reduced in 2025 to `34 <= L(12,3) <= 36` by combining a table
lower bound with an explicit 36-bit construction. We determine the exact
value. Two independently written exhaustive programs enumerate every binary
sequence of every positive length from 1 through 35. Rotation, reversal, and
bit complement reduce 68,719,476,734 raw sequences to 506,526,514
representatives. The C++ and Rust traversals find no covering representative,
and every per-length representative count agrees with independent Burnside
calculations. Three verifier implementations confirm that the attributed
36-bit construction has covering radius exactly 3. Therefore `L(12,3)=36`.
The complete source, logs, metadata, hashes, and replay tools are retained in
the accompanying repository.

## Comments

Computer-assisted exact determination with two independent exhaustive
implementations, complete retained logs, and reproducibility artifacts.

## Repository

```text
https://github.com/ruturajr-raval/binary-covering-sequence-12-3
```

## Archive

The version and concept DOI fields will be added after the first immutable
Zenodo archive is published.

## License Plan

The intended source-submission license is arXiv's perpetual, non-exclusive
license. Project-original repository material is MIT licensed. The attributed
length-36 witness fixture remains under Apache-2.0 and is not required in the
paper source archive.

## Final Manual Checks

Before submission:

1. insert the immutable release URL and DOI;
2. build the exact source archive from a clean release checkout;
3. let arXiv compile the source;
4. inspect every page of the generated PDF;
5. verify equations, tables, references, links, and line wrapping;
6. confirm the author name, Independent Researcher affiliation, and ORCID;
7. confirm the category and irrevocable license choice; and
8. replace any remaining unassigned-identifier wording.
