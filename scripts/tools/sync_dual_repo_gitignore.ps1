param(
    [string]$PrimaryRepo = "D:\Projects\auto-git",
    [string]$SecondaryRepo = "D:\Projects\AutoGIT_repo_clean",
    [string]$SecondaryBranch = "main",
    [string]$PrimaryBranch = "master"
)

$ErrorActionPreference = "Stop"

$primaryIgnore = Join-Path $PrimaryRepo ".gitignore"
$secondaryIgnore = Join-Path $SecondaryRepo ".gitignore"

if (!(Test-Path $primaryIgnore)) {
    throw "Primary .gitignore not found: $primaryIgnore"
}
if (!(Test-Path $secondaryIgnore)) {
    throw "Secondary .gitignore not found: $secondaryIgnore"
}

Copy-Item -Path $primaryIgnore -Destination $secondaryIgnore -Force

Push-Location $SecondaryRepo
try {
    git add .gitignore
    if (git diff --cached --quiet) {
        Write-Host "No .gitignore changes to commit in secondary repo."
    } else {
        git commit -m "chore: sync gitignore from primary repo"
        git push origin $SecondaryBranch
        Write-Host "Secondary repo updated."
    }
} finally {
    Pop-Location
}

Push-Location $PrimaryRepo
try {
    git add .gitignore
    if (git diff --cached --quiet) {
        Write-Host "No .gitignore changes to commit in primary repo."
    } else {
        git commit -m "chore: harden gitignore policy"
        git push origin $PrimaryBranch
        Write-Host "Primary repo updated."
    }
} finally {
    Pop-Location
}
