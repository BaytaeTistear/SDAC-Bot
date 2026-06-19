param(
    [Parameter(Position = 0)]
    [string]$ReleaseTag = "",
    [string]$Repo = "",
    [string]$AssetName = "SDAC-Bot-Windows-Installer.exe",
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"

if ($RemainingArgs.Count -gt 0) {
    $ReleaseTag = (@($ReleaseTag) + $RemainingArgs) -join " "
}

if ([string]::IsNullOrWhiteSpace($Repo)) {
    $Repo = $env:SDAC_GITHUB_REPO
}
if ([string]::IsNullOrWhiteSpace($Repo)) {
    $Repo = "BaytaeTistear/SDAC-Bot"
}

if ([string]::IsNullOrWhiteSpace($ReleaseTag)) {
    $ReleaseTag = $env:SDAC_RELEASE_TAG
}
if ([string]::IsNullOrWhiteSpace($ReleaseTag)) {
    $ReleaseTag = "latest-official"
}

function Resolve-ReleaseTag {
    param([string]$Value)

    if ($null -eq $Value) {
        $Value = ""
    }
    $lowered = $Value.Trim().ToLowerInvariant().Replace(" ", "-").Replace("_", "-")
    switch ($lowered) {
        "" { return "latest-official" }
        "latest" { return "latest-official" }
        "stable" { return "latest-official" }
        "official" { return "latest-official" }
        "latest-official" { return "latest-official" }
        "2" { return "latest-official" }
        "v2" { return "latest-official" }
        "version-2" { return "latest-official" }
        "experimental" { return "latest-experimental" }
        "expirimental" { return "latest-experimental" }
        "latest-experimental" { return "latest-experimental" }
        "latest-expirimental" { return "latest-experimental" }
        default {
            if ($lowered -match "^version-(\d+\.\d+(?:\.\d+)?)$") {
                return $lowered
            }
            if ($lowered -match "^v(\d+\.\d+(?:\.\d+)?)$") {
                return "version-$($Matches[1])"
            }
            if ($lowered -match "^(\d+\.\d+(?:\.\d+)?)$") {
                return "version-$lowered"
            }
            return $Value
        }
    }
}

function Show-Usage {
    Write-Host "Usage:"
    Write-Host "  .\SDAC-Bot-Windows-Update.ps1 [release-tag]"
    Write-Host "  .\SDAC-Bot-Windows-Update.ps1 'Version 2'"
    Write-Host "  .\SDAC-Bot-Windows-Update.ps1 2"
    Write-Host "  .\SDAC-Bot-Windows-Update.ps1 2.5"
    Write-Host "  .\SDAC-Bot-Windows-Update.ps1 latest-official"
    Write-Host "  .\SDAC-Bot-Windows-Update.ps1 latest-experimental"
    Write-Host "  .\SDAC-Bot-Windows-Update.ps1 latest-expirimental"
    Write-Host ""
    Write-Host "Environment:"
    Write-Host "  SDAC_GITHUB_REPO=$Repo"
    Write-Host "  SDAC_RELEASE_TAG=$ReleaseTag"
}

if ($Help) {
    Show-Usage
    exit 0
}

$ReleaseTag = Resolve-ReleaseTag -Value $ReleaseTag
$tempDir = Join-Path ([IO.Path]::GetTempPath()) ("sdac-update-" + [Guid]::NewGuid().ToString("N"))
$installerPath = Join-Path $tempDir $AssetName

function Download-WithGitHubCli {
    $gh = Get-Command gh -ErrorAction SilentlyContinue
    if (-not $gh) {
        return $false
    }

    Write-Host ""
    Write-Host "==> Downloading $AssetName from $Repo ($ReleaseTag) with GitHub CLI"
    & gh release download $ReleaseTag --repo $Repo --pattern $AssetName --dir $tempDir | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "GitHub CLI download failed. Trying HTTPS download next."
        return $false
    }

    return (Test-Path -LiteralPath $installerPath)
}

function Download-WithHttps {
    $url = "https://github.com/$Repo/releases/download/$ReleaseTag/$AssetName"
    Write-Host ""
    Write-Host "==> Downloading $AssetName from $url"
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $installerPath
    return (Test-Path -LiteralPath $installerPath)
}

try {
    New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

    $downloaded = Download-WithGitHubCli
    if (-not $downloaded) {
        $downloaded = Download-WithHttps
    }
    if (-not $downloaded) {
        throw "Downloaded installer was not found at $installerPath."
    }

    Write-Host ""
    Write-Host "==> Running Windows installer"
    & $installerPath
    if ($LASTEXITCODE -ne 0) {
        throw "Windows installer exited with code $LASTEXITCODE."
    }

    Write-Host ""
    Write-Host "Update complete."
    Write-Host "Release tag: $ReleaseTag"
    Write-Host "Installer: $AssetName"
}
finally {
    if (Test-Path -LiteralPath $tempDir) {
        Remove-Item -LiteralPath $tempDir -Recurse -Force
    }
}
