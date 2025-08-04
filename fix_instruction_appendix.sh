#!/bin/bash

# Script to fix the instruction appendix golden file
# This script should be run when the GitHub Actions test fails
# due to differences between generated and golden instruction appendix

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
else
    echo "ERROR: Generated file not found at gen/instructions_appendix/all_instructions.adoc"
    echo "Make sure the generation task completed successfully."
    exit 1
fi
