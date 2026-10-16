# SpecChoice v1.3.2 evidence workspace

This directory is the dependency-light, standalone-first experiment boundary. Its Phase 1
construction identity uses only the Python standard library and the Git CLI; accepted-bundle
verification and downstream replay use only the Python standard library plus offline bundle
access. It does not require or probe `bin/setup`, `bin/doctor`, Ruby, IDL, C++, Node, a package
manager, or the full UDB toolchain.

Run the local environment receipt command from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m specchoice_evidence.cli record-environment
```

`receipts/environment-decision.json` is canonical, byte-stable experiment identity. It has only
route, stable capabilities, CPython/Git identities and versions, UDB-setup status, fallback
policy, and stable incident result fields.
`audit/environment/environment-receipt-phase-start-001.json` is deliberately non-canonical: it
contains sanitized local operational evidence and only a one-way SHA-256 reference to the
canonical decision. Audit timestamps, paths, platform facts, and commands therefore cannot alter
experiment identity.

The runtime external-API detector is not applicable: this workspace introduces no endpoint or
SDK, and Git transport is construction-only. These JSON files are versioned local artifact
contracts, not a production API or schema migration.
