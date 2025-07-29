@echo off
cd /d "C:\Users\USER\OneDrive\Desktop\RISCV\riscv-unified-db"
git add -A
git commit -m "Fix CSR schema validation errors - Add missing required properties"
git push fork feature/add-smaia-ssaia-aia-support
pause
