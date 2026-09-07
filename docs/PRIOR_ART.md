# Prior Art And Frontier Audit

Status date: 2026-09-07

## Problem And Notation

A binary `(n,R)` covering sequence is a positive-length cyclic binary
sequence whose cyclic length-`n` windows form a radius-`R` covering code.
Write `L(n,R)` for the minimum possible length. This project determines
`L(12,3)`.

## Origin

Fan Chung and Joshua N. Cooper introduced de Bruijn covering sequences in:

- F. Chung and J. N. Cooper,
  "De Bruijn cycles for covering codes",
  Random Structures and Algorithms 25 (2004), 421-431.

Their work established the subject and general bounds.

## Published 2025 Table

Yeow Meng Chee, Tuvi Etzion, Hoang Ta, and Van Khu Vu compiled finite bounds
and new constructions in:

- "Constructions of Covering Sequences and 2D-Sequences"
- Designs, Codes and Cryptography 93 (2025), 5445-5471
- DOI: `10.1007/s10623-025-01726-5`
- arXiv:2502.08424v2
- https://arxiv.org/abs/2502.08424

Their finite table records

```text
34 <= L(12,3) <= 40.
```

That interval is attributed prior art, not a result of this project.

## Public Length-36 Construction

Christopher D. Rosin reports a `(12,3,36)` construction in:

- arXiv:2505.23881v1
- https://arxiv.org/abs/2505.23881

The exact witness and construction source are maintained in:

- Repository: https://github.com/Constructive-Codes/CPro1
- Audited main commit:
  `827f02b4048fc96a6b79f0970c87ca5a54f31f40`
- Result path:
  `designs/covering-sequence/result-12-3-36-seed1000.txt`
- Result history commit:
  `5b26b1a5ca0625a857cf6c2adcc6668e1d66a2ac`
- Upstream license: Apache License 2.0
- Raw result SHA-256:
  `2fbbf39ccfa94ca3c0af465a51042d97152b94a6dc435057e1989cfa67d1a610`
- Normalized fixture: `data/baseline-36.txt`
- Normalized SHA-256:
  `02bb4681195a71888260f535feaac94f7d45993e6b1ab63199dd369e9bf3eca1`

Independent full-target replay confirms this witness, giving the pre-project
working frontier

```text
34 <= L(12,3) <= 36.
```

## Later General Work

The refreshed audit also checked:

- Tuvi Etzion, "Covering Sequences and Covering-Sequences Codes",
  arXiv:2607.14840v2, https://arxiv.org/abs/2607.14840.
- Hoang Ta and Van Khu Vu, "Near-Optimal Covering Sequences",
  arXiv:2606.29236v1, https://arxiv.org/abs/2606.29236.

These papers develop general code-based and asymptotic constructions. The
audited versions do not report an exact determination of `L(12,3)` or an
exclusion of both lengths 34 and 35.

## 2026-09-07 Public Audit

The release audit checked:

1. the 2025 finite table and its journal/arXiv versions;
2. the Rosin paper and all listed covering-sequence parameters;
3. the CPro1 main branch, tags, result directory, source files, and commit
   history;
4. all arXiv records returned by an exact phrase search for covering
   sequences, including the two 2026 papers above;
5. public GitHub code searches for `L(12,3)`, `(12,3,35)`,
   `result-12-3-35`, and close variants; and
6. public repository searches for the exact parameter and problem title.

The CPro1 main head remained the audited 2025 commit and contained the
length-36 result but no length-35 result. No prior public complete exclusion
of lengths 34 and 35, and no prior public exact determination of `L(12,3)`,
was located.

This is a bounded public-source audit. It cannot exclude unpublished,
privately circulated, deleted, inaccessible, or unindexed work. The audit
supports release wording but is not part of the mathematical proof.

## Result Of This Project

The project supplies a complete independent finite exclusion:

```text
no positive length L <= 35 admits a binary (12,3) covering sequence.
```

Together with the attributed and independently verified length-36 witness,
this gives

```text
L(12,3) = 36.
```

The lower-bound computation and evidence are project-original. The upper
witness remains attributed prior art.

## Licensing And Provenance

External papers are cited and summarized but not redistributed. The
normalized CPro1 witness fixture is retained under Apache-2.0, with its exact
source commit, path, raw hash, normalized hash, and modification recorded.
The complete Apache-2.0 text is included at
`LICENSES/Apache-2.0.txt`.

All exhaustive implementations, evidence checkers, tests, and documentation
were written independently and are covered by the root MIT License.
