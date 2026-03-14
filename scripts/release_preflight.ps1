$ErrorActionPreference = "Stop"

function Assert-True {
    param(
        [bool]$Condition,
        [string]$Message
    )
    if (-not $Condition) {
        throw $Message
    }
}

function Test-Section {
    param(
        [string]$Name,
        [scriptblock]$Block
    )
    try {
        & $Block
        return [pscustomobject]@{
            name = $Name
            status = "pass"
            detail = ""
        }
    }
    catch {
        return [pscustomobject]@{
            name = $Name
            status = "fail"
            detail = $_.Exception.Message
        }
    }
}

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $repoRoot

$requiredDocs = @(
    "README.md",
    "docs/demo-workflow.md",
    "docs/release-checklist.md",
    "docs/releases/TEMPLATE.md",
    "examples/sample-project-package/manifest.json",
    "examples/sample-project-package/inventory.json",
    "scripts/smoke.ps1"
)

$requiredRoutes = @(
    "POST /api/projects/{project_id}/export",
    "POST /api/projects/{project_id}/rebuild",
    "GET /api/projects/{project_id}/diagnostics/health",
    "POST /api/projects/import-package",
    "POST /api/projects/{project_id}/archive-snapshot",
    "POST /api/projects/{project_id}/backup",
    "GET /api/projects/{project_id}/snapshots"
)

$prefixedRouteSuffixes = @(
    "/export",
    "/rebuild",
    "/diagnostics/health",
    "/archive-snapshot",
    "/backup",
    "/snapshots"
)

$results = @()

$results += Test-Section "required-files" {
    foreach ($path in $requiredDocs) {
        Assert-True (Test-Path -LiteralPath $path) "Missing required file: $path"
    }
}

$results += Test-Section "readme-phase" {
    $readme = Get-Content README.md -Raw
    Assert-True ($readme -match "当前稳定阶段 = Phase 11") "README stable phase is not Phase 11."
}

$results += Test-Section "release-checklist-sections" {
    $checklist = Get-Content docs/release-checklist.md -Raw
    Assert-True ($checklist -match "## Must Pass Before Release") "Release checklist is missing Must Pass section."
    Assert-True ($checklist -match "## Known Limitations Accepted For This Release") "Release checklist is missing Known Limitations section."
}

$results += Test-Section "release-template-sections" {
    $template = Get-Content docs/releases/TEMPLATE.md -Raw
    foreach ($heading in @("## Summary", "## Included Capabilities", "## Verified Commands", "## Known Limitations", "## Commit Hash")) {
        Assert-True ($template -match [regex]::Escape($heading)) "Release notes template is missing heading: $heading"
    }
}

$results += Test-Section "sample-package-manifest" {
    $manifest = Get-Content examples/sample-project-package/manifest.json -Raw | ConvertFrom-Json
    Assert-True ($manifest.scope -eq "project") "Sample package manifest scope must be project."
    Assert-True ($manifest.package_version -eq "project_package_v1") "Sample package package_version must be project_package_v1."
    Assert-True ($manifest.format -eq "json_package") "Sample package format must be json_package."
}

$results += Test-Section "sample-package-inventory" {
    $inventory = Get-Content examples/sample-project-package/inventory.json -Raw | ConvertFrom-Json
    Assert-True ($inventory.package_version -eq "project_package_v1") "Sample package inventory package_version must be project_package_v1."
    $paths = @($inventory.items | ForEach-Object { $_.relative_path })
    $sortedPaths = @($paths | Sort-Object)
    Assert-True (($paths -join "`n") -eq ($sortedPaths -join "`n")) "Inventory items are not sorted by relative_path."
    foreach ($relativePath in $paths) {
        Assert-True (-not [System.IO.Path]::IsPathRooted($relativePath)) "Inventory path must be relative: $relativePath"
        Assert-True ($relativePath -notmatch "^[A-Za-z]:") "Inventory path contains drive letter: $relativePath"
        Assert-True ($relativePath -notmatch "\\\\.\\\\|\\.\\.") "Inventory path contains invalid segments: $relativePath"
    }
}

$results += Test-Section "sample-package-runtime-history" {
    foreach ($name in @("exports", "archives", "backups")) {
        Assert-True (-not (Test-Path -LiteralPath (Join-Path "examples/sample-project-package" $name))) "Sample package must not include $name history."
    }
}

$results += Test-Section "docs-route-alignment" {
    $productizationSource = Get-Content backend/app/api/productization.py -Raw
    $readme = Get-Content README.md -Raw
    $demo = Get-Content docs/demo-workflow.md -Raw
    Assert-True ($productizationSource -match 'prefix="/api/projects/\{project_id\}"') "project_router prefix is missing in productization.py."
    foreach ($suffix in $prefixedRouteSuffixes) {
        Assert-True ($productizationSource -match [regex]::Escape($suffix)) "Route suffix missing in productization.py: $suffix"
    }
    Assert-True ($productizationSource -match [regex]::Escape('/api/projects/import-package')) "Import route missing in productization.py."
    foreach ($route in $requiredRoutes) {
        Assert-True ($readme -match [regex]::Escape($route)) "Route missing in README.md: $route"
    }
    foreach ($route in @(
        "/api/projects/import-package",
        "/diagnostics/health"
    )) {
        Assert-True ($demo -match [regex]::Escape($route)) "Route missing in demo workflow: $route"
    }
}

$results += Test-Section "git-status" {
    $status = git status --short
    if ($LASTEXITCODE -ne 0) {
        throw "git status failed."
    }
    if ($status) {
        throw "Working tree is not clean.`n$status"
    }
}

$failed = @($results | Where-Object { $_.status -eq "fail" })
$report = [pscustomobject]@{
    checked_at = (Get-Date).ToUniversalTime().ToString("o")
    repo_root = $repoRoot.Path
    overall_status = if ($failed.Count -eq 0) { "pass" } else { "fail" }
    checks = $results
}

$report | ConvertTo-Json -Depth 5

if ($failed.Count -gt 0) {
    exit 1
}
