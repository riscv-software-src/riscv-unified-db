# H3 v5 Decision and Authority Lifecycle Contract

The v5 packet and readiness are machine-only, pre-decision outputs. Their
freeze inventory includes this contract, the v5 lifecycle implementation,
validators, writers, and tests. It includes the exact repository-local copy of
the v3 human approval source, bound to the original attachment locator, byte
length, and raw SHA-256. It excludes the two declared post-decision leaves:
`reviews/h3-branch-decision-v5.json` and `phase4/branch-authority-v5.json`.

Publication is a closed state machine:

```text
absent -> decision_only_exact -> decision_and_authority_exact
```

Only an approved canonical v5 decision can enter `decision_only_exact`. The
single authority publication orchestrator descriptor-reads that persisted
decision, revalidates its exact raw bytes, derives the authority from those
bytes, and binds both the decision raw SHA-256 and decision self SHA-256.
`decision_only_exact` may exact-resume to the full state. A full exact state
returns without writing. An authority without its decision, conflicting leaves,
hash drift, or any non-approved, incomplete, or disputed decision fails closed
without replacing a leaf.

Both protected leaves and every protected parent are read and written through
the descriptor boundary. A symlink, including a dangling symlink, is occupied
and untrusted rather than absent; special files and hardlink-dependent leaves
are also rejected. The pre-publication test uses an independent empty output
root, so historical v2/v4 authority leaves in the real checkout cannot affect
its result.

All v1--v4 records remain immutable historical predecessors and are not current
authority. v5 changes no Red semantics: `N_strict=0`, `repeat_count=0`, no
provider, credentials, model, network, H4, external call, production retrieval,
publication, or upstream-write authority. A post-approval defect is fail
closed and requires a new versioned successor rather than a v5 repair.
