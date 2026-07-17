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
- sana-update latest-experimental
- sana-update $Version
"@

Run-Step "Compile dashboard and bot" {
    py -3.12 -m py_compile dashboard.py dashboard_account_templates.py dashboard_admin_roles.py dashboard_shell_assets.py dashboard_sidebar.py server\dashboard.py server\dashboard_account_templates.py server\dashboard_admin_roles.py server\dashboard_shell_assets.py server\dashboard_sidebar.py bot.py scripts\pre_release_smoke.py scripts\release_readiness.py scripts\dashboard_layout_check.py
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
        git add RELEASE.md README.md HOSTING.md requirements.txt bot.py dashboard.py dashboard_account_templates.py dashboard_admin_roles.py dashboard_shell_assets.py dashboard_sidebar.py server/RELEASE.md server/README.md server/requirements.txt server/bot.py server/dashboard.py server/dashboard_account_templates.py server/dashboard_admin_roles.py server/dashboard_shell_assets.py server/dashboard_sidebar.py scripts/pre_release_smoke.py scripts/release_readiness.py scripts/dashboard_layout_check.py scripts/install_nginx_site.sh nginx/sdac-dashboard.conf.template tests/test_dashboard_access.py server/scripts/pre_release_smoke.py server/scripts/release_readiness.py server/scripts/dashboard_layout_check.py server/scripts/install_nginx_site.sh server/nginx/sdac-dashboard.conf.template tools/release_experimental.ps1 tools/release_official.ps1 apps/sdac-official-app/package.json apps/sdac-official-app/package-lock.json apps/sdac-official-app/src/main.ts dist/Sana-Chan-Linux-Installer.sh dist/Sana-Chan-Ubuntu-Update.sh dist/Sana-Chan-Windows-Installer.exe dist/Sana-Chan-Windows-Update.ps1 dist/sana-update dist/sanachan-update
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
    gh release create $tag dist/Sana-Chan-Linux-Installer.sh dist/Sana-Chan-Ubuntu-Update.sh dist/Sana-Chan-Windows-Installer.exe dist/Sana-Chan-Windows-Update.ps1 dist/sana-update dist/sanachan-update --repo $Repo --title "Version $Version Experimental" --notes $notes --prerelease
}

Run-Step "Update latest-experimental release" {
    gh release edit latest-experimental --repo $Repo --title "Latest Experimental ($Version)" --notes $notes --prerelease
    gh release upload latest-experimental dist/Sana-Chan-Linux-Installer.sh dist/Sana-Chan-Ubuntu-Update.sh dist/Sana-Chan-Windows-Installer.exe dist/Sana-Chan-Windows-Update.ps1 dist/sana-update dist/sanachan-update --repo $Repo --clobber
}

Run-Step "Verify releases" {
    gh release view $tag --repo $Repo --json tagName,name,isPrerelease,targetCommitish,assets,url
    gh release view latest-experimental --repo $Repo --json tagName,name,isPrerelease,targetCommitish,assets,url
}
