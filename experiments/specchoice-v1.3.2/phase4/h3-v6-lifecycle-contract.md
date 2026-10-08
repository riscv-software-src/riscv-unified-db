# H3 v6 Lifecycle Contract

V1 through v5 artifacts are immutable predecessor evidence.  V5 decision and
authority leaves have status `historical_failed_publication_not_current_authority`:
their preserved bytes demonstrate the v5 closed-schema failure and grant no
current authority.

`V6_AUTHORITY_KEYS` is the single authority schema declaration.  Constructor
output, self-hash projection, validator, canonical round trip, mutation tests,
and publication all require that exact key set.  The state machine remains
`absent -> decision_only_exact -> decision_and_authority_exact`; authority is
derived only from descriptor-re-read, validated decision bytes.  Authority-only,
split-brain, conflicts, symlinks, dangling symlinks, unknown keys, missing keys,
and root drift fail closed.

The pre-decision inventory includes the repository-local v3 approval source,
this contract, lifecycle code/tests, and the Ruff 0.16 receipt.  It excludes
the declared post-decision v6 decision and authority leaves.  V6 changes only
the schema drift and static-check closure; Red counts, retrieval/model/provider
boundaries, and all other permissions remain unchanged.
