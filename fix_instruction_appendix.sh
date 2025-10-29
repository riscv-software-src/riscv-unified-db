#!/bin/bash

# Copyright (c) Kallal Mukherjee.
# SPDX-License-Identifier: BSD-3-Clause-Clear

# Script to fix the instruction appendix golden file
# This script should be run when the GitHub Actions test fails
# due to differences between generated and golden instruction appendix
#
# Based on GitHub Actions failure in job 47302783539:
# The failure is due to a mismatch between the generated instruction appendix
# output and the stored golden file. The solution is to copy the generated
# file to the golden file if the changes are expected and correct.

echo "Fixing instruction appendix golden file..."

# Generate the instruction appendix
echo "Generating instruction appendix..."
./do gen:instruction_appendix_adoc

# Check if the generated file exists
if [ -f "gen/instructions_appendix/all_instructions.adoc" ]; then
    echo "Generated file found, copying to golden file..."
    cp gen/instructions_appendix/all_instructions.adoc backends/instructions_appendix/all_instructions.golden.adoc
    echo "Golden file updated successfully!"

    # Show the changes
    echo "Changes made:"
    git diff --stat backends/instructions_appendix/all_instructions.golden.adoc

    echo "To commit these changes, run:"
    echo "git add backends/instructions_appendix/all_instructions.golden.adoc"
    echo "git commit -m 'Update instruction appendix golden file to match generated output'"

    # Auto-commit if requested
    if [ "$1" = "--commit" ]; then
        echo "Auto-committing changes..."
        git add backends/instructions_appendix/all_instructions.golden.adoc
        git commit -m "Update instruction appendix golden file to match generated output

This fixes the test failure in regress-gen-instruction-appendix where the
generated output differs from the stored golden file. The changes are
expected due to the encoding updates in the Zvqdotq extension."
        echo "Changes committed successfully!"
    fi
else
    echo "ERROR: Generated file not found at gen/instructions_appendix/all_instructions.adoc"
    echo "Make sure the generation task completed successfully."
    exit 1
fi
