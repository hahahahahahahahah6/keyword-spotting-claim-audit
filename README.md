# Documentation audit

An offline static audit tool that compares documented promises with source evidence.
It parses source without executing it. It uses no network, sends no telemetry,
and writes no files during an audit. Requires Python 3.9 or later.

```text
keyword-spotting-claim-audit 0.1.0
keyword_spotting_claim_audit
```

Install and run:

```sh
python3 -m pip install .
keyword-spotting-claim-audit . --json
python3 -m keyword_spotting_claim_audit . --verbose
```

The root README and Markdown files beneath a docs directory are examined.
Fenced blocks are excluded; inline code is included. Source files are parsed
with the standard AST parser. Tests count separately; fixtures, documentation,
examples, symlinks and invalid source provide no production evidence.
Static evidence is a heuristic and does not establish runtime correctness.

Options include repeatable `--ignore` relative path prefixes, `--json`,
`--verbose`, `--version`, and `--fail-on LOW|MEDIUM|HIGH` (default HIGH).
Exit status is 0 below the threshold, 2 for findings meeting the threshold,
and 1 for usage or I/O errors. A report can contain findings below the threshold.
The JSON report includes verdict, findings, document and source paths, and
evidence flags. Each finding includes an identifier, severity and message.

```text
documented-keyword-spotting-claim-false
documented-no-keyword-spotting-claim-false
```

Missing production evidence produces HIGH severity, or MEDIUM when evidence
exists only in tests. A denial contradicted by production evidence is HIGH.
With no source, a promise fails while a denial passes.

Run the suite and build:

```sh
python3 -m unittest discover
python3 -m build
```

Distributed under the MIT license.
