param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [string]$Repo = "BaytaeTistear/SDAC-Bot",
    [string]$CommitMessage = "",
    [switch]$SkipCommit
)

$ErrorActionPreference = "Stop"

function Run-Step {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Script
    )
    Write-Host "==> $Label" -ForegroundColor Cyan
    & $Script
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$tag = "version-$Version"
$notes = @"
Latest experimental build: Version $Version.

Update with:
- sdac-update latest-experimental
- sdac-update $Version
"@

Run-Step "Compile dashboard and bot" {
    py -3.12 -m py_compile dashboard.py dashboard_account_templates.py dashboard_admin_roles.py dashboard_shell_assets.py dashboard_sidebar.py server\dashboard.py server\dashboard_account_templates.py server\dashboard_admin_roles.py server\dashboard_shell_assets.py server\dashboard_sidebar.py bot.py scripts\pre_release_smoke.py scripts\release_readiness.py
}

Run-Step "Run backend release readiness" {
    py -3.12 scripts\release_readiness.py
}

Run-Step "Run release smoke tests" {
    py -3.12 scripts\pre_release_smoke.py
}

Run-Step "Build installers" {
    & "$root\tools\build_installers.ps1"
}

if (-not $SkipCommit) {
    if (-not $CommitMessage) {
        $CommitMessage = "Release experimental $Version"
    }
    Run-Step "Commit changes" {
        git add RELEASE.md README.md bot.py dashboard.py dashboard_account_templates.py dashboard_admin_roles.py dashboard_shell_assets.py dashboard_sidebar.py server/RELEASE.md server/README.md server/bot.py server/dashboard.py server/dashboard_account_templates.py server/dashboard_admin_roles.py server/dashboard_shell_assets.py server/dashboard_sidebar.py scripts/release_readiness.py server/scripts/release_readiness.py dist/SDAC-Bot-Linux-Installer.sh dist/SDAC-Bot-Ubuntu-Update.sh dist/SDAC-Bot-Windows-Installer.exe dist/SDAC-Bot-Windows-Update.ps1 dist/sdac-update
        git commit -m $CommitMessage
    }
}

$commit = (git rev-parse HEAD).Trim()

Run-Step "Tag $tag and latest-experimental" {
    git tag $tag $commit
    git tag -f latest-experimental $commit
}

Run-Step "Push branch and tags" {
    git push origin main
    git push origin $tag
    git push origin latest-experimental --force
}

Run-Step "Create version release" {
    gh release create $tag dist/SDAC-Bot-Linux-Installer.sh dist/SDAC-Bot-Ubuntu-Update.sh dist/SDAC-Bot-Windows-Installer.exe dist/SDAC-Bot-Windows-Update.ps1 dist/sdac-update --repo $Repo --title "Version $Version Experimental" --notes $notes --prerelease
}

Run-Step "Update latest-experimental release" {
    gh release edit latest-experimental --repo $Repo --title "Latest Experimental ($Version)" --notes $notes --prerelease
    gh release upload latest-experimental dist/SDAC-Bot-Linux-Installer.sh dist/SDAC-Bot-Ubuntu-Update.sh dist/SDAC-Bot-Windows-Installer.exe dist/SDAC-Bot-Windows-Update.ps1 dist/sdac-update --repo $Repo --clobber
}

Run-Step "Verify releases" {
    gh release view $tag --repo $Repo --json tagName,name,isPrerelease,targetCommitish,assets,url
    gh release view latest-experimental --repo $Repo --json tagName,name,isPrerelease,targetCommitish,assets,url
}
