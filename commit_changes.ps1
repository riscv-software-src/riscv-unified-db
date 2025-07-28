#!/usr/bin/env pwsh

# Commit and push the schema validation fixes
Write-Host "Adding all changes..."
git add -A

Write-Host "Committing changes..."
git commit -m "Fix CSR schema validation errors - Add missing required properties

- Add priv_mode property to all CSR files (M for Machine, S for Supervisor)  
- Add length property to all CSR files (MXLEN, SXLEN, or 32)
- Fix JSON Schema Validation Error for stopi.yaml
- Ensure all CSRs comply with required schema properties

This resolves the failing regression tests caused by schema validation errors."

Write-Host "Pushing to fork..."
git push fork feature/add-smaia-ssaia-aia-support

Write-Host "Done!"
