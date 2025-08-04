# Instruction Appendix Fix for PR #902

## Problem
The `regress-gen-instruction-appendix` test is failing due to a mismatch between the generated instruction appendix output and the stored golden file.

## Root Cause
The encoding changes made to the Zvqdotq extension instructions (`vqdotsu.vx` and `vqdotus.vx`) have caused the generated instruction appendix to differ from the golden file. This is expected behavior.

## Solution
Based on GitHub Actions failure in job 47302783539, the exact solution is:

1. Review the changes in `gen/instructions_appendix/all_instructions.adoc`
2. If the changes are expected and correct (which they are), update the golden file:

```bash
cp gen/instructions_appendix/all_instructions.adoc backends/instructions_appendix/all_instructions.golden.adoc
git add backends/instructions_appendix/all_instructions.golden.adoc
git commit -m "Update golden instruction appendix to match generated output"
```

## Encoding Changes Made
- `vqdotsu.vx`: encoding changed from `101010` to `101110` (hex: 0x2a → 0x2e)
- `vqdotus.vx`: encoding changed from `101011` to `111001` (hex: 0x2b → 0x39)

These changes affect the Wavedrom diagrams in the instruction appendix, which is why the golden file needs to be updated.

## Automated Fix
Use the provided script:
```bash
./fix_instruction_appendix.sh --commit
```

This will automatically generate the instruction appendix and update the golden file.

## Status
This fix is needed to resolve the test failures in PR #902 and complete the Zvqdotq extension implementation.
