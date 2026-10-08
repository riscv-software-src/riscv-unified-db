# H3 v4 Decision and Authority Lifecycle Contract

The v4 packet and readiness are machine-only pre-decision outputs. Their
inventory includes this contract, the v4 H3 implementation, its public export,
and its tests; it explicitly excludes the post-decision decision and authority
leaves.

Pre-publication requires that neither `reviews/h3-branch-decision-v4.json` nor
`phase4/branch-authority-v4.json` exists. A decision is constructed from
human-owned fields, validated against one exact packet/readiness pair, and
written once through the descriptor-bound exact-resume writer. Missing,
incomplete, disputed, inconsistent, changed, or hash-drifted decisions cannot
construct authority.

Only a current, complete `approved_red` decision constructs a Red authority.
The authority writer validates the complete predecessor chain, recomputes the
frozen input root, validates both published leaves, and permits only byte-equal
resume. Conflicting, partial, symlinked, special, or hard-linked destinations
fail closed. Post-publication validation requires both exact canonical leaves.

If any implementation, schema, test, predecessor, packet, readiness, decision,
or authority defect is found after approval, v4 is not repaired in place. The
result is fail-closed and requires a new versioned successor. This contract does
not change Red semantics: `N_strict=0`, `repeat_count=0`, no provider, model,
credentials, network, production retrieval, H4, external call, publication, or
upstream-write authority.
