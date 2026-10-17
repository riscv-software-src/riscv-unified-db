# H1 Source/Gold Review Packet

- Packet SHA-256: `65b4a3a0f1d1df32112cd7e8f9080ae247a704368756295273b52a6d99111aad`
- External publication authorized: `false`
- Aggregate disposition: human decision required (not present in this packet)

## Immutable bindings

- `adapter_batch_sha256`: `c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606`
- `adapter_version`: `pr2164-adapter-v1`
- `adversarial_report_sha256`: `326ddbf2de9e4a0888fd0cc6da5ef00c34330060f594ceb047be1b8ee5b36cd0`
- `formal_attempt_sha256`: `5af7673e4b02cbafac57336805a28cb245466abe23450953d01452efc2bd655d`
- `formal_diagnostics_sha256`: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`
- `golden_predictions_sha256`: `9767a5870b145a1ced1fd6a42025200b94bce3a3c219dbbc820e407be602a704`
- `h1_review_schema_sha256`: `e9b78cbba7564c2c2eddb0d4d3fff4ee14f020c601770b171124812b520e2ee8`
- `rule_sha256`: `edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0`
- `schema_sha256`: `e6be3f36cc5dcaa2ca24ec56dec3f411be1831df06f575365c5726903cced2c7`
- `source_identity`: `{"generation":"source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v3","manifest_sha256":"3292c170244cb8096521eadd575c0e8b0230f96d2e298d9b1078dccc134d3564","pinned_commit_sha":"22e84458c87a7ccf4c07034de1eb6d0bf9764144","pinned_tree_sha":"af003b427c66bd8ac9803a91b3bf363a1b1304d9","registry_sha256":"ddda6f6c96b4007d8d57aed64210fc08701b89bfd27feac5f0732c828c388f36","root_sha256":"4ead0825002c60eca58070d3104c59dbfa58a3d184f6f81a70b18be7e94677c5"}`

## Fixture review items

### CAND_WARL_FIXED_LEGAL_SET

- Category: `candidate`
- expect_extract: `true`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `true`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_EXT_GATED_PBMTE

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_FIXED_ENCODING

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_SHALL_NO_DELEGATION

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_SOFTWARE_ADVICE

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_CSR_RW_MTVEC_ACCESS

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `MTVEC_ACCESS`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_DIRECT_CACHE_BLOCK

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `CACHE_BLOCK_SIZE`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_DIRECT_NUM_PMP

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `NUM_PMP_ENTRIES`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_RECALL_COUNT_GEILEN

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `NUM_EXTERNAL_GUEST_INTERRUPTS`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_WARL_ASID_WIDTH

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `ASID_WIDTH`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_WARL_MTVEC_MODES

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `MTVEC_MODES`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"c5108bc539322bafb7415634755c12e8c206f0fee909513f493a3bf34a346606","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review
