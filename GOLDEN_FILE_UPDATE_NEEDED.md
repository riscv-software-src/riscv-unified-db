<!--
Copyright (c) Kallal Mukherjee.
SPDX-License-Identifier: BSD-3-Clause-Clear
-->

# Golden File Update Required for PR #902

## Issue
The `regress-gen-instruction-appendix` test is failing because the golden file `backends/instructions_appendix/all_instructions.golden.adoc` does not include the new Zvqdotq instructions.

## Root Cause
This is **expected behavior** when adding new instructions. The test compares the generated instruction appendix against a stored golden file, and since we've added 7 new instructions (vqdot.vv, vqdot.vx, vqdotu.vv, vqdotu.vx, vqdotsu.vv, vqdotsu.vx, vqdotus.vx), the output naturally differs.

## Solution
The test failure message provides the exact solution:

```bash
cp gen/instructions_appendix/all_instructions.adoc backends/instructions_appendix/all_instructions.golden.adoc
git add backends/instructions_appendix/all_instructions.golden.adoc
```

## Status
- ✅ All schema validation is passing
- ✅ All instruction files are valid
- ✅ Documentation generation is working correctly
- ✅ The only issue is the expected diff due to new instructions

## Next Steps
1. Run the instruction appendix generation in CI
2. Update the golden file with the new output that includes Zvqdotq instructions
3. Commit the updated golden file

This is a **normal part of adding new instructions** and indicates that our extension is being processed correctly by the build system.
