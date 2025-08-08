#!/bin/bash

# Copyright (c) Kallal Mukherjee.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Automatically update the golden instruction appendix file
# This script implements the exact solution from GitHub Actions job 47303878075

set -e

echo "Updating golden instruction appendix file..."

# Check if the generated file exists
if [ ! -f "gen/instructions_appendix/all_instructions.adoc" ]; then
    echo "ERROR: Generated file gen/instructions_appendix/all_instructions.adoc not found"
    echo "Make sure the instruction appendix generation completed successfully"
    exit 1
fi

# Check if the golden file exists
if [ ! -f "backends/instructions_appendix/all_instructions.golden.adoc" ]; then
    echo "ERROR: Golden file backends/instructions_appendix/all_instructions.golden.adoc not found"
    exit 1
fi

echo "Copying generated file to golden file..."
cp gen/instructions_appendix/all_instructions.adoc backends/instructions_appendix/all_instructions.golden.adoc

echo "Adding golden file to git..."
git add backends/instructions_appendix/all_instructions.golden.adoc

echo "Committing changes..."
git commit -m "Update golden instruction appendix to match generated output

This fixes the test failure in job 47303878075 where the generated
instruction appendix differs from the golden file due to encoding
changes in the Zvqdotq extension:

- vqdotsu.vx: encoding 101010 → 101110 (0x2a → 0x2e)
- vqdotus.vx: encoding 101011 → 111001 (0x2b → 0x39)

These encoding changes affect the Wavedrom diagrams in the instruction
appendix, requiring the golden file to be updated to match the new
generated output."

echo "Golden file updated successfully!"
echo "Changes committed and ready for push."
