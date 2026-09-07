# Third-Party Notices

Status date: 2026-09-07

## Chee Et Al. Paper

This repository cites and summarizes:

- Yeow Meng Chee, Tuvi Etzion, Hoang Ta, and Van Khu Vu
- "Constructions of Covering Sequences and 2D-Sequences"
- Designs, Codes and Cryptography 93 (2025), 5445-5471
- DOI: `10.1007/s10623-025-01726-5`
- arXiv:2502.08424v2
- https://arxiv.org/abs/2502.08424

No paper text, figure, table image, or source archive is redistributed. The
numerical Table I entry `34 <= L(12,3) <= 40` is reported as an attributed
mathematical fact.

## Later General Papers

This repository also cites and summarizes:

- Tuvi Etzion, "Covering Sequences and Covering-Sequences Codes",
  arXiv:2607.14840v2.
- Hoang Ta and Van Khu Vu, "Near-Optimal Covering Sequences",
  arXiv:2606.29236v1.

No text, source archive, figure, or table image from either paper is
redistributed.

## Rosin Paper

This repository cites the CPro1 construction paper by Christopher D. Rosin:

- "Using Reasoning Models to Generate Search Heuristics that Solve Open
  Instances of Combinatorial Design Problems"
- arXiv:2505.23881v1
- DOI: `10.48550/arXiv.2505.23881`
- https://arxiv.org/abs/2505.23881

No paper text, figure, table image, or source archive is redistributed.

## CPro1 Construction And Software

The public 36-bit `(12,3)` covering-sequence witness and its construction
software are maintained by the Constructive-Codes project:

- Repository: https://github.com/Constructive-Codes/CPro1
- Audited commit:
  `827f02b4048fc96a6b79f0970c87ca5a54f31f40`
- Witness path:
  `designs/covering-sequence/result-12-3-36-seed1000.txt`
- Result history commit:
  `5b26b1a5ca0625a857cf6c2adcc6668e1d66a2ac`
- Upstream raw-file SHA-256:
  `2fbbf39ccfa94ca3c0af465a51042d97152b94a6dc435057e1989cfa67d1a610`
- Normalized local fixture: `data/baseline-36.txt`
- Normalized fixture SHA-256:
  `02bb4681195a71888260f535feaac94f7d45993e6b1ab63199dd369e9bf3eca1`
- License path:
  https://github.com/Constructive-Codes/CPro1/blob/827f02b4048fc96a6b79f0970c87ca5a54f31f40/LICENSE
- Upstream license: Apache License 2.0
- Included license copy: `LICENSES/Apache-2.0.txt`

The exact witness bits are transcribed into `data/baseline-36.txt` as a
normalized one-line regression fixture. The local formatting differs from the
tab-separated upstream file, so both hashes are recorded. No upstream
implementation source is copied.

Redistribution of the fixture, or any later import of CPro1 source, must:

1. Preserve the Apache License 2.0 terms.
2. Preserve applicable copyright, attribution, and notice information.
3. Mark project modifications clearly.
4. Keep the upstream material outside the project-original license grant.
5. Record the exact imported commit and file hash.
6. Include a complete copy of the Apache License 2.0 in any public release
   bundle that contains the fixture or other upstream material.

No project-original claim is made for the CPro1 witness, its construction
method, or its source code.

## Independent Implementations

The project verifiers, exhaustive implementations, encodings, evidence
tooling, and search code were written independently from the public
mathematical definition. Comparing their output with the CPro1 witness does
not transfer ownership of the upstream witness or software.

Project-original software and documentation are licensed under the root MIT
License. That license does not apply to or relicense the Apache-2.0 fixture.

## External Solvers And Checkers

No third-party solver, proof checker, source tree, binary, or package is
currently vendored in this repository.

Any later development-only or release dependency must be pinned, attributed,
and documented under its own license. Generated proof objects remain subject
to the terms of the tools and formats used to create and check them.
