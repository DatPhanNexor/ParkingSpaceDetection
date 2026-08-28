$ErrorActionPreference = "Stop"

$workspace = "D:\Project\ParkingSpaceDetection"
$tempBase = "$env:TEMP\p"
$tempFlutter = "$env:TEMP\p\f"

$allowedDirs = @(
    ".github",
    "backend_microservices",
    "docs_tttn",
    "infrastructure"
)

foreach ($dir in $allowedDirs) {
    $sourcePath = Join-Path $tempBase $dir
    $destPath = Join-Path $workspace $dir
    if (Test-Path $sourcePath) {
        Write-Host "Copying $dir..."
        Copy-Item -Path "$sourcePath\*" -Destination $destPath -Recurse -Force
    }
}

$destFlutter = Join-Path $workspace "flutter_mobile_app"
if (Test-Path $tempFlutter) {
    Write-Host "Copying flutter_mobile_app..."
    # Ensure flutter directory exists
    if (-not (Test-Path $destFlutter)) {
        New-Item -ItemType Directory -Path $destFlutter | Out-Null
    }
    Copy-Item -Path "$tempFlutter\*" -Destination $destFlutter -Recurse -Force
}

Write-Host "Merge completed successfully."
