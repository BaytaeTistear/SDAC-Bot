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
        if (Test-Path "apps/sdac-official-app") { git add -u apps/sdac-official-app }
        git add apps/sana-official-app/android/.gitignore apps/sana-official-app/android/app/.gitignore apps/sana-official-app/android/app/capacitor.build.gradle apps/sana-official-app/android/app/proguard-rules.pro apps/sana-official-app/android/app/src apps/sana-official-app/android/build.gradle apps/sana-official-app/android/capacitor.settings.gradle apps/sana-official-app/android/gradle.properties apps/sana-official-app/android/gradle/wrapper/gradle-wrapper.jar apps/sana-official-app/android/gradle/wrapper/gradle-wrapper.properties apps/sana-official-app/android/gradlew apps/sana-official-app/android/gradlew.bat apps/sana-official-app/android/settings.gradle apps/sana-official-app/android/variables.gradle apps/sana-official-app/assets apps/sana-official-app/index.html apps/sana-official-app/public/sana-companion-art.png apps/sana-official-app/src/vite-env.d.ts apps/sana-official-app/tsconfig.json apps/sana-official-app/vite.config.ts
        git add RELEASE.md README.md .gitignore .github/workflows/release.yml PLAY_STORE_UPLOAD_CHECKLIST.md HOSTING.md DOCKER.md ORACLE_RESTORE.md .dockerignore .env.example Dockerfile docker-compose.yml systemd/sana-bot.service.template systemd/sana-dashboard.service.template systemd/sana-journald.conf requirements.txt database_migrations.py bot.py dashboard.py dashboard_account_templates.py dashboard_admin_roles.py dashboard_shell_assets.py dashboard_sidebar.py server/RELEASE.md server/README.md server/.env.example server/systemd/sana-bot.service.template server/systemd/sana-dashboard.service.template server/systemd/sana-journald.conf server/requirements.txt server/database_migrations.py server/bot.py server/dashboard.py server/dashboard_account_templates.py server/dashboard_admin_roles.py server/dashboard_shell_assets.py server/dashboard_sidebar.py scripts/pre_release_smoke.py scripts/release_readiness.py scripts/reset_admin_login.py scripts/dashboard_layout_check.py scripts/install_nginx_site.sh scripts/install_ubuntu.sh scripts/install_backup_prereqs.sh scripts/sdac_doctor.py scripts/check_production.sh scripts/update_from_github.sh scripts/update_from_github_windows.ps1 scripts/windows/README.md scripts/windows/start_sana_local_server.ps1 nginx/sana-dashboard.conf.template tests/test_dashboard_access.py tests/test_bot_startup.py tests/test_dashboard_sidebar_layout.py tests/test_dashboard_sidebar_routes.py tests/test_dashboard_page_sweep.py tests/test_backend_release_readiness.py tests/test_app_readiness.py server/scripts/pre_release_smoke.py server/scripts/release_readiness.py server/scripts/reset_admin_login.py server/scripts/dashboard_layout_check.py server/scripts/install_nginx_site.sh server/scripts/install_ubuntu.sh server/scripts/install_backup_prereqs.sh server/scripts/sdac_doctor.py server/scripts/check_production.sh server/scripts/update_from_github.sh server/scripts/update_from_github_windows.ps1 server/nginx/sana-dashboard.conf.template tools/build_installers.ps1 tools/release_experimental.ps1 tools/release_official.ps1 apps/sana-official-app/package.json apps/sana-official-app/package-lock.json apps/sana-official-app/src/main.ts apps/sana-official-app/capacitor.config.ts apps/sana-official-app/src/styles.css apps/sana-official-app/.env.example apps/sana-official-app/README.md apps/sana-official-app/PLAY_STORE_LISTING.md apps/sana-official-app/android/app/build.gradle scripts/rollback_ubuntu.sh scripts/install_journal_limits.sh server/scripts/rollback_ubuntu.sh scripts/check_production.sh server/scripts/check_production.sh scripts/install_ubuntu.sh server/scripts/install_ubuntu.sh scripts/install_backup_prereqs.sh server/scripts/install_backup_prereqs.sh dist/Sana-Chan-Linux-Installer.sh dist/Sana-Chan-Ubuntu-Update.sh dist/Sana-Chan-Windows-Installer.exe dist/Sana-Chan-Windows-Update.ps1 dist/sana-update dist/sanachan-update
        git commit -m $CommitMessage
    }
}

$commit = (git rev-parse HEAD).Trim()

Run-Step "Archive app source" {
    git archive --format=zip --output=dist/Sana-Chan-App-Source.zip HEAD apps/sana-official-app
}

$releaseAssets = @(
    "systemd/sana-bot.service.template",
    "systemd/sana-dashboard.service.template",
    "systemd/sana-journald.conf",
    "nginx/sana-dashboard.conf.template",
    "scripts/rollback_ubuntu.sh",
    "scripts/install_journal_limits.sh",
    "scripts/check_production.sh",
    "scripts/install_ubuntu.sh",
    "scripts/install_backup_prereqs.sh",
    "dist/Sana-Chan-Linux-Installer.sh",
    "dist/Sana-Chan-Ubuntu-Update.sh",
    "dist/Sana-Chan-Windows-Installer.exe",
    "dist/Sana-Chan-Windows-Update.ps1",
    "dist/sana-update",
    "dist/sanachan-update",
    "dist/Sana-Chan-Android-Debug.apk",
    "dist/Sana-Chan-Android-Debug.apk.sha256",
    "dist/Sana-Chan-Android-Release.aab",
    "dist/Sana-Chan-Android-Release.aab.sha256",
    "dist/Sana-Chan-App-Source.zip"
)

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
    gh release create $tag @releaseAssets --repo $Repo --title "Version $Version Experimental" --notes $notes --prerelease
}

Run-Step "Update latest-experimental release" {
    gh release edit latest-experimental --repo $Repo --title "Latest Experimental ($Version)" --notes $notes --prerelease
    gh release upload latest-experimental @releaseAssets --repo $Repo --clobber
}

Run-Step "Verify releases" {
    gh release view $tag --repo $Repo --json tagName,name,isPrerelease,targetCommitish,assets,url
    gh release view latest-experimental --repo $Repo --json tagName,name,isPrerelease,targetCommitish,assets,url
}

