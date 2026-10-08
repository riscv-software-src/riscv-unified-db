# H1 Source/Gold Review Packet

- Packet SHA-256: `4482bfe4c28a825e86365420c071ed267afc3d0370ce333e4cdd16916b58c81c`
- External publication authorized: `false`
- Aggregate disposition: human decision required (not present in this packet)

## Immutable bindings

- `adapter_batch_sha256`: `86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494`
- `adapter_version`: `pr2164-adapter-v1`
- `adversarial_report_sha256`: `1f466fb0490cd283e491cdf9b33f569f7b4c6297f3f4860da8aa1ac2a1a1f0ff`
- `formal_attempt_sha256`: `c81649ae4aaa4c29be289af1855934f66c907f8a0bf0a2e6c2ce2407bd3da756`
- `formal_diagnostics_sha256`: `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`
- `golden_predictions_sha256`: `78c3c7e02530bc612fe6cda38537f6a9b7a52743b4f0429673a0f7e9bb05265c`
- `h1_review_schema_sha256`: `42b5c2ad7b0022872805b2f02b87084be8b0eee55ee39c15ff1fe06d1ef85373`
- `rule_sha256`: `edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0`
- `schema_sha256`: `e6be3f36cc5dcaa2ca24ec56dec3f411be1831df06f575365c5726903cced2c7`
- `source_identity`: `{"generation":"source-contract-v3-pr2164-fixture-closure-22e84458-verifier-rooted-v2","manifest_sha256":"73b25a28ed237c228ffe40fb025a3f8a3c194443012500a3ce6f756437513a3c","pinned_commit_sha":"22e84458c87a7ccf4c07034de1eb6d0bf9764144","pinned_tree_sha":"af003b427c66bd8ac9803a91b3bf363a1b1304d9","registry_sha256":"ddda6f6c96b4007d8d57aed64210fc08701b89bfd27feac5f0732c828c388f36","root_sha256":"6a682538c35d678b15852963e4f8f5316ee84d184f6a96a7996133be3de02f6d"}`

## Fixture review items

### CAND_WARL_FIXED_LEGAL_SET

- Category: `candidate`
- expect_extract: `true`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `true`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_EXT_GATED_PBMTE

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_FIXED_ENCODING

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_SHALL_NO_DELEGATION

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### NEG_SOFTWARE_ADVICE

- Category: `negative`
- expect_extract: `false`
- Expected parameter count: `0`
- Expected parameter names: ``
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_CSR_RW_MTVEC_ACCESS

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `MTVEC_ACCESS`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_DIRECT_CACHE_BLOCK

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `CACHE_BLOCK_SIZE`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_DIRECT_NUM_PMP

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `NUM_PMP_ENTRIES`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_RECALL_COUNT_GEILEN

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `NUM_EXTERNAL_GUEST_INTERRUPTS`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_WARL_ASID_WIDTH

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `ASID_WIDTH`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review

### POS_WARL_MTVEC_MODES

- Category: `positive`
- expect_extract: `true`
- Expected parameter count: `1`
- Expected parameter names: `MTVEC_MODES`
- Candidate surfaced then classify_out: `false`
- Adapter lineage: `{"adapter_batch_sha256":"86fcdba7906ab5158fd31b92bd673976e9ffcfd5903b0521e083264173276494","adapter_version":"pr2164-adapter-v1","rule_sha256":"edd7f2121ff794b87ea6a25b0b508ded0fc536a9f52553b0cf3b51e5ff987ae0"}`
- Signature slot: reviewer/signature intentionally blank pending independent human review
