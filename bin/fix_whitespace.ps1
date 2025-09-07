# PowerShell script to fix trailing whitespace in files

Write-Host "Fixing trailing whitespace in files..."

# File types to check
$fileTypes = @(
    "*.yml",
    "*.yaml",
    "*.rb",
    "*.py",
    "*.c",
    "*.h",
    "*.cpp",
    "*.md",
    "*.txt",
    "*.json",
    "*.js",
    "*.adoc"
)

# Get all files of specified types
$filesToCheck = @()
foreach ($fileType in $fileTypes) {
    $filesToCheck += Get-ChildItem -Path . -Filter $fileType -Recurse -File
}

# Count of files with whitespace fixed
$fixedFiles = 0

foreach ($file in $filesToCheck) {
    $content = Get-Content -Path $file.FullName -Raw
    $newContent = $content -replace '[ \t]+$', '' -replace '\r\n', "`n"
    
    if ($content -ne $newContent) {
        Set-Content -Path $file.FullName -Value $newContent -NoNewline
        $fixedFiles++
        Write-Host "Fixed: $($file.FullName)"
    }
}

Write-Host "Fixed trailing whitespace in $fixedFiles files."
