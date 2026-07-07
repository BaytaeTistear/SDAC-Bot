param(
    [string]$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Dist = (Join-Path $Root "dist")
)

$ErrorActionPreference = "Stop"

function Copy-PayloadFiles {
    param([string]$PayloadRoot)

    if (Test-Path -LiteralPath $PayloadRoot) {
        Remove-Item -LiteralPath $PayloadRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $PayloadRoot | Out-Null

    $files = @(
        ".env.example",
        ".dockerignore",
        ".gitignore",
        "Dockerfile",
        "README.md",
        "DEPLOY.md",
        "HOSTING.md",
        "DISCORD_PERMISSIONS.md",
        "PRODUCTION_NEXT.md",
        "MONITORING.md",
        "POSTGRESQL.md",
        "bot.py",
        "dashboard.py",
        "config.py",
        "database_backend.py",
        "database_migrations.py",
        "observability.py",
        "requirements.txt",
        "docker-compose.yml",
        "scripts\install_ubuntu.sh",
        "scripts\update_ubuntu.sh",
        "scripts\rollback_ubuntu.sh",
        "scripts\install_journal_limits.sh",
        "scripts\install_nginx_site.sh",
        "scripts\standardize_env_file.sh",
        "scripts\backup_offsite.sh",
        "scripts\backup_guild_offsite.sh",
        "scripts\install_backup_prereqs.sh",
        "scripts\reset_admin_login.py",
        "scripts\restore_guild_media_rclone.sh",
        "scripts\sync_media_rclone.sh",
        "scripts\support_bundle.sh",
        "scripts\check_production.sh",
        "scripts\release_checklist.sh",
        "scripts\pre_release_smoke.py",
        "scripts\sdac_doctor.py",
        "scripts\sdac-doctor",
        "scripts\migrate_database.py",
        "scripts\archive_old_history.py",
        "scripts\export_sqlite_to_postgres.py",
        "scripts\test_restore.sh",
        "scripts\update_from_github.sh",
        "scripts\update_from_github_windows.ps1",
        "systemd\sdac-bot.service.template",
        "systemd\sdac-dashboard.service.template",
        "systemd\sdac-journald.conf",
        "nginx\sdac-dashboard.conf.template"
    )

    foreach ($file in $files) {
        $source = Join-Path $Root $file
        if (-not (Test-Path -LiteralPath $source)) {
            throw "Missing payload file: $file"
        }
        $target = Join-Path $PayloadRoot $file
        $targetDir = Split-Path -Parent $target
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        Copy-Item -LiteralPath $source -Destination $target -Force
    }
}

function Convert-PayloadTextFilesToLf {
    param([string]$PayloadRoot)

    $textExtensions = @(
        ".conf",
        ".example",
        ".json",
        ".md",
        ".py",
        ".sh",
        ".template",
        ".txt",
        ".yml",
        ".yaml"
    )
    $textFileNames = @(
        "Dockerfile",
        "sdac-doctor"
    )

    Get-ChildItem -LiteralPath $PayloadRoot -Recurse -File |
        Where-Object {
            ($textExtensions -contains $_.Extension.ToLowerInvariant()) -or
            ($textFileNames -contains $_.Name)
        } |
        ForEach-Object {
            $content = [IO.File]::ReadAllText($_.FullName)
            $content = $content -replace "`r`n", "`n" -replace "`r", "`n"
            [IO.File]::WriteAllText(
                $_.FullName,
                $content,
                [Text.UTF8Encoding]::new($false)
            )
        }
}

function Split-Base64 {
    param([string]$Value, [int]$Width = 76)

    $builder = [Text.StringBuilder]::new()
    for ($index = 0; $index -lt $Value.Length; $index += $Width) {
        $length = [Math]::Min($Width, $Value.Length - $index)
        [void]$builder.Append($Value.Substring($index, $length))
        [void]$builder.Append("`n")
    }
    $builder.ToString()
}

function New-LinuxInstaller {
    param([string]$PayloadRoot, [string]$OutputPath)

    $archive = Join-Path $Dist "sdac-linux-payload.tar.gz"
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }

    Push-Location $PayloadRoot
    try {
        tar -czf $archive .
    }
    finally {
        Pop-Location
    }

    $payloadBytes = [IO.File]::ReadAllBytes($archive)
    $payloadBase64 = Split-Base64 ([Convert]::ToBase64String($payloadBytes))
    $payloadSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $archive).Hash.ToLowerInvariant()
    $payloadSize = (Get-Item -LiteralPath $archive).Length

    $header = @"
#!/usr/bin/env bash
set -Eeuo pipefail

# SDAC Bot single-file Linux installer.
# This installer does not contain .env, Discord tokens, SQLite databases,
# media uploads, backups, virtualenvs, or Python cache files.
#
# Usage:
#   chmod +x SDAC-Bot-Linux-Installer.sh
#   ./SDAC-Bot-Linux-Installer.sh
#
# Optional environment overrides:
#   SDAC_APP_DIR=/home/ubuntu/discord-screenshot-bot
#   SDAC_APP_USER=ubuntu
#   SDAC_CREATE_APP_USER=1         # create SDAC_APP_USER if it is missing
#   SDAC_ENV_FILE=/etc/sdac-bot/sdac.env
#   SDAC_DASHBOARD_BIND=127.0.0.1:5000
#   SDAC_SKIP_SERVICES=1            # extract and compile only
#   SDAC_INSTALL_JOURNAL_LIMITS=1   # install journald retention limits

APP_DIR="`${SDAC_APP_DIR:-/home/ubuntu/discord-screenshot-bot}"
APP_USER="`${SDAC_APP_USER:-`$(id -un)}"
CREATE_APP_USER="`${SDAC_CREATE_APP_USER:-0}"
ENV_FILE="`${SDAC_ENV_FILE:-/etc/sdac-bot/sdac.env}"
DASHBOARD_BIND="`${SDAC_DASHBOARD_BIND:-127.0.0.1:5000}"
SKIP_SERVICES="`${SDAC_SKIP_SERVICES:-0}"
INSTALL_JOURNAL_LIMITS="`${SDAC_INSTALL_JOURNAL_LIMITS:-0}"
PAYLOAD_SHA256="$payloadSha"
PAYLOAD_SIZE_BYTES="$payloadSize"
STAMP="`$(date -u +%Y%m%d-%H%M%S)"

say() {
    printf '\n==> %s\n' "`$*"
}

fail() {
    echo "ERROR: `$*" >&2
    exit 1
}

need_command() {
    command -v "`$1" >/dev/null 2>&1 || fail "Missing required command: `$1"
}

if [[ "`$(uname -s)" != "Linux" ]]; then
    fail "This installer is intended for Linux. Build/run it on Ubuntu for production."
fi

need_command base64
need_command tar
need_command sudo

if ! id "`$APP_USER" >/dev/null 2>&1; then
    if [[ "`$CREATE_APP_USER" == "1" ]]; then
        say "Creating system user `$APP_USER"
        sudo useradd --system --home-dir "`$APP_DIR" --shell /usr/sbin/nologin --no-create-home "`$APP_USER"
    else
        fail "User `$APP_USER does not exist. Create it, use SDAC_APP_USER=`$(id -un), or set SDAC_CREATE_APP_USER=1."
    fi
fi

if ! command -v python3 >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        say "Installing Python system packages"
        sudo apt-get update
        sudo apt-get install -y python3 python3-venv python3-pip
    else
        fail "python3 is missing, and apt-get is not available to install it."
    fi
fi

if ! python3 -m venv --help >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        say "Installing python3-venv"
        sudo apt-get update
        sudo apt-get install -y python3-venv python3-pip
    else
        fail "python3-venv is missing, and apt-get is not available to install it."
    fi
fi

say "Preparing `$APP_DIR"
sudo mkdir -p "`$APP_DIR"
CURRENT_USER="`$(id -un)"
CURRENT_GROUP="`$(id -gn)"
sudo chown -R "`$CURRENT_USER":"`$CURRENT_GROUP" "`$APP_DIR" 2>/dev/null || sudo chown -R "`$CURRENT_USER" "`$APP_DIR"
mkdir -p "`$APP_DIR/media" "`$APP_DIR/backups" "`$APP_DIR/deploy-backups"

if [[ -f "`$APP_DIR/bot.py" || -f "`$APP_DIR/dashboard.py" ]]; then
    DEPLOY_BACKUP_DIR="`$APP_DIR/deploy-backups/installer-`$STAMP"
    say "Creating deploy snapshot at `$DEPLOY_BACKUP_DIR"
    mkdir -p "`$DEPLOY_BACKUP_DIR"
    for file in \
        bot.py \
        dashboard.py \
        config.py \
        database_migrations.py \
        observability.py \
        requirements.txt \
        README.md \
        HOSTING.md \
        DEPLOY.md \
        PRODUCTION_NEXT.md \
        MONITORING.md \
        POSTGRESQL.md \
        DISCORD_PERMISSIONS.md
    do
        if [[ -e "`$APP_DIR/`$file" ]]; then
            cp -a "`$APP_DIR/`$file" "`$DEPLOY_BACKUP_DIR/"
        fi
    done
    for directory in scripts systemd nginx; do
        if [[ -d "`$APP_DIR/`$directory" ]]; then
            mkdir -p "`$DEPLOY_BACKUP_DIR/`$directory"
            cp -a "`$APP_DIR/`$directory/." "`$DEPLOY_BACKUP_DIR/`$directory/"
        fi
    done
fi

if [[ -f "`$APP_DIR/sdac.db" ]]; then
    DB_BACKUP="`$APP_DIR/backups/sdac-pre-installer-`$STAMP.db"
    say "Creating SQLite backup at `$DB_BACKUP"
    SDAC_DB_FILE="`$APP_DIR/sdac.db" SDAC_DB_BACKUP="`$DB_BACKUP" python3 - <<'PY'
import os
import sqlite3

source_path = os.environ["SDAC_DB_FILE"]
backup_path = os.environ["SDAC_DB_BACKUP"]
source = sqlite3.connect(source_path)
destination = sqlite3.connect(backup_path)
try:
    with destination:
        source.backup(destination)
finally:
    destination.close()
    source.close()
print(f"Database backup created: {backup_path}")
PY
fi

TMP_DIR="`$(mktemp -d)"
cleanup() {
    rm -rf "`$TMP_DIR"
}
trap cleanup EXIT
PAYLOAD_FILE="`$TMP_DIR/sdac-payload.tar.gz"

say "Extracting embedded SDAC payload"
awk '/^__SDAC_PAYLOAD_BELOW__$/ {found=1; next} found {print}' "`$0" | base64 -d > "`$PAYLOAD_FILE"
ACTUAL_SHA256="`$(sha256sum "`$PAYLOAD_FILE" | awk '{print `$1}')"
if [[ "`$ACTUAL_SHA256" != "`$PAYLOAD_SHA256" ]]; then
    fail "Embedded payload checksum mismatch. Expected `$PAYLOAD_SHA256 but got `$ACTUAL_SHA256."
fi
ACTUAL_SIZE="`$(wc -c < "`$PAYLOAD_FILE" | tr -d ' ')"
if [[ "`$ACTUAL_SIZE" != "`$PAYLOAD_SIZE_BYTES" ]]; then
    fail "Embedded payload size mismatch. Expected `$PAYLOAD_SIZE_BYTES but got `$ACTUAL_SIZE."
fi

tar -xzf "`$PAYLOAD_FILE" -C "`$APP_DIR"
chmod +x "`$APP_DIR"/scripts/*.sh
mkdir -p "`$APP_DIR/media" "`$APP_DIR/backups"

if [[ "`$SKIP_SERVICES" == "1" ]]; then
    say "Compiling Python files without installing services"
    python3 -m py_compile "`$APP_DIR/bot.py" "`$APP_DIR/dashboard.py" "`$APP_DIR/config.py" "`$APP_DIR/database_backend.py"
    python3 -m py_compile "`$APP_DIR/database_migrations.py" "`$APP_DIR/observability.py" "`$APP_DIR/scripts/migrate_database.py" "`$APP_DIR/scripts/export_sqlite_to_postgres.py"
    echo "SDAC files extracted to `$APP_DIR"
    exit 0
fi

say "Running Ubuntu installer"
export SDAC_APP_DIR="`$APP_DIR"
export SDAC_APP_USER="`$APP_USER"
export SDAC_ENV_FILE="`$ENV_FILE"
export SDAC_DASHBOARD_BIND="`$DASHBOARD_BIND"
bash "`$APP_DIR/scripts/install_ubuntu.sh"

if [[ "`$INSTALL_JOURNAL_LIMITS" == "1" ]]; then
    say "Installing journald retention limits"
    bash "`$APP_DIR/scripts/install_journal_limits.sh"
fi

say "SDAC single-file install complete"
echo "App directory: `$APP_DIR"
echo "Environment file: `$ENV_FILE"
echo "Logs:"
echo "  journalctl -u sdac-bot -n 80 --no-pager"
echo "  journalctl -u sdac-dashboard -n 80 --no-pager"
echo "Health:"
echo "  curl http://127.0.0.1:5000/health"

exit 0

__SDAC_PAYLOAD_BELOW__
"@

    $scriptContent = ($header + "`n" + $payloadBase64) `
        -replace "`r`n", "`n" `
        -replace "`r", "`n"

    [IO.File]::WriteAllText(
        $OutputPath,
        $scriptContent,
        [Text.UTF8Encoding]::new($false)
    )
    Remove-Item -LiteralPath $archive -Force
}

function New-WindowsInstaller {
    param([string]$PayloadRoot, [string]$OutputPath)

    $zipPath = Join-Path $Dist "sdac-windows-payload.zip"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $PayloadRoot "*") -DestinationPath $zipPath -CompressionLevel Optimal

    $payloadBytes = [IO.File]::ReadAllBytes($zipPath)
    $payloadSha = (Get-FileHash -Algorithm SHA256 -LiteralPath $zipPath).Hash.ToLowerInvariant()
    $payloadBase64 = [Convert]::ToBase64String($payloadBytes)
    $chunks = New-Object System.Collections.Generic.List[string]
    for ($index = 0; $index -lt $payloadBase64.Length; $index += 120) {
        $length = [Math]::Min(120, $payloadBase64.Length - $index)
        $chunks.Add($payloadBase64.Substring($index, $length))
    }
    $chunkLiteral = ($chunks | ForEach-Object { '            "' + $_ + '"' }) -join ",`r`n"

    $sourcePath = Join-Path $Dist "sdac-windows-installer.cs"
    $source = @"
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Security.Cryptography;
using System.Text;

class Program
{
    const string PayloadSha256 = "$payloadSha";
    static readonly string[] PayloadChunks = new string[]
    {
$chunkLiteral
    };
    static string InitialAdminUsername = "";
    static string InitialAdminPassword = "";

    static int Main(string[] args)
    {
        try
        {
            Console.Title = "SDAC Bot Windows Installer";
            Console.WriteLine("SDAC Bot Windows single-file installer");
            Console.WriteLine("This installer does not include tokens, databases, media, backups, venv, or cache files.");
            Console.WriteLine();

            string defaultDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.CommonApplicationData),
                "SDAC-Bot");
            string appDir = Prompt("Install directory", defaultDir);
            if (String.IsNullOrWhiteSpace(appDir))
            {
                appDir = defaultDir;
            }
            appDir = Environment.ExpandEnvironmentVariables(appDir.Trim().Trim('"'));
            Directory.CreateDirectory(appDir);
            Directory.CreateDirectory(Path.Combine(appDir, "media"));
            Directory.CreateDirectory(Path.Combine(appDir, "backups"));
            Directory.CreateDirectory(Path.Combine(appDir, "deploy-backups"));

            BackupExistingInstall(appDir);
            ExtractPayload(appDir);
            EnsureConfig(appDir);
            WriteEnvironmentFile(appDir);
            WriteLaunchers(appDir);
            InstallPythonDependencies(appDir);

            Console.WriteLine();
            Console.WriteLine("SDAC Windows install complete.");
            Console.WriteLine("App directory: " + appDir);
            Console.WriteLine("Environment file: " + Path.Combine(appDir, ".env"));
            Console.WriteLine("Start SDAC with: " + Path.Combine(appDir, "start-sdac.bat"));
            Console.WriteLine("Dashboard URL: http://localhost:5000");
            Pause();
            return 0;
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine();
            Console.Error.WriteLine("Install failed: " + ex.Message);
            Pause();
            return 1;
        }
    }

    static string Prompt(string label, string defaultValue)
    {
        Console.Write(label + " [" + defaultValue + "]: ");
        string value = Console.ReadLine();
        return String.IsNullOrWhiteSpace(value) ? defaultValue : value.Trim();
    }

    static string PromptRequired(string label)
    {
        while (true)
        {
            Console.Write(label + ": ");
            string value = Console.ReadLine();
            if (!String.IsNullOrWhiteSpace(value))
            {
                return value.Trim();
            }
            Console.WriteLine(label + " cannot be blank.");
        }
    }

    static string PromptSecret(string label)
    {
        Console.Write(label + ": ");
        StringBuilder builder = new StringBuilder();
        while (true)
        {
            ConsoleKeyInfo key = Console.ReadKey(true);
            if (key.Key == ConsoleKey.Enter)
            {
                Console.WriteLine();
                break;
            }
            if (key.Key == ConsoleKey.Backspace)
            {
                if (builder.Length > 0)
                {
                    builder.Length--;
                    Console.Write("\b \b");
                }
                continue;
            }
            if (!Char.IsControl(key.KeyChar))
            {
                builder.Append(key.KeyChar);
                Console.Write("*");
            }
        }
        return builder.ToString();
    }

    static void BackupExistingInstall(string appDir)
    {
        if (!File.Exists(Path.Combine(appDir, "bot.py")) && !File.Exists(Path.Combine(appDir, "dashboard.py")))
        {
            return;
        }

        string stamp = DateTime.UtcNow.ToString("yyyyMMdd-HHmmss");
        string backupDir = Path.Combine(appDir, "deploy-backups", "windows-installer-" + stamp);
        Directory.CreateDirectory(backupDir);

        string[] files = new string[]
        {
            "bot.py", "dashboard.py", "config.py", "requirements.txt",
            "database_migrations.py", "observability.py",
            "README.md", "HOSTING.md", "DEPLOY.md", "PRODUCTION_NEXT.md",
            "MONITORING.md", "POSTGRESQL.md", "DISCORD_PERMISSIONS.md", ".env"
        };
        foreach (string file in files)
        {
            string source = Path.Combine(appDir, file);
            if (File.Exists(source))
            {
                File.Copy(source, Path.Combine(backupDir, file), true);
            }
        }
        CopyDirectoryIfExists(Path.Combine(appDir, "scripts"), Path.Combine(backupDir, "scripts"));
        CopyDirectoryIfExists(Path.Combine(appDir, "systemd"), Path.Combine(backupDir, "systemd"));
        CopyDirectoryIfExists(Path.Combine(appDir, "nginx"), Path.Combine(backupDir, "nginx"));

        string dbPath = Path.Combine(appDir, "sdac.db");
        if (File.Exists(dbPath))
        {
            string backupDb = Path.Combine(appDir, "backups", "sdac-pre-windows-installer-" + stamp + ".db");
            File.Copy(dbPath, backupDb, true);
            Console.WriteLine("Database backup created: " + backupDb);
        }
    }

    static void CopyDirectoryIfExists(string sourceDir, string targetDir)
    {
        if (!Directory.Exists(sourceDir))
        {
            return;
        }
        foreach (string directory in Directory.GetDirectories(sourceDir, "*", SearchOption.AllDirectories))
        {
            Directory.CreateDirectory(directory.Replace(sourceDir, targetDir));
        }
        foreach (string file in Directory.GetFiles(sourceDir, "*", SearchOption.AllDirectories))
        {
            string target = file.Replace(sourceDir, targetDir);
            Directory.CreateDirectory(Path.GetDirectoryName(target));
            File.Copy(file, target, true);
        }
    }

    static void ExtractPayload(string appDir)
    {
        byte[] payload = Convert.FromBase64String(String.Concat(PayloadChunks));
        string actualSha = Sha256Hex(payload);
        if (!String.Equals(actualSha, PayloadSha256, StringComparison.OrdinalIgnoreCase))
        {
            throw new InvalidOperationException("Embedded payload checksum mismatch.");
        }

        string tempZip = Path.Combine(Path.GetTempPath(), "sdac-windows-payload-" + Guid.NewGuid().ToString("N") + ".zip");
        File.WriteAllBytes(tempZip, payload);
        try
        {
            using (ZipArchive archive = ZipFile.OpenRead(tempZip))
            {
                foreach (ZipArchiveEntry entry in archive.Entries)
                {
                    string relative = entry.FullName.Replace('/', Path.DirectorySeparatorChar).TrimStart(Path.DirectorySeparatorChar);
                    if (String.IsNullOrWhiteSpace(relative))
                    {
                        continue;
                    }
                    if (relative.Equals(".env", StringComparison.OrdinalIgnoreCase))
                    {
                        continue;
                    }
                    string target = Path.GetFullPath(Path.Combine(appDir, relative));
                    string appFull = Path.GetFullPath(appDir).TrimEnd(Path.DirectorySeparatorChar) + Path.DirectorySeparatorChar;
                    if (!target.StartsWith(appFull, StringComparison.OrdinalIgnoreCase))
                    {
                        throw new InvalidOperationException("Unsafe payload path: " + entry.FullName);
                    }
                    if (entry.FullName.EndsWith("/", StringComparison.Ordinal))
                    {
                        Directory.CreateDirectory(target);
                        continue;
                    }
                    Directory.CreateDirectory(Path.GetDirectoryName(target));
                    entry.ExtractToFile(target, true);
                }
            }
        }
        finally
        {
            try { File.Delete(tempZip); } catch { }
        }
    }

    static void EnsureConfig(string appDir)
    {
        string configPath = Path.Combine(appDir, "config.json");
        if (File.Exists(configPath))
        {
            return;
        }
        File.WriteAllText(configPath,
@"{
    ""guilds"": {},
    ""limits"": {
        ""max_file_bytes"": 26214400,
        ""max_total_bytes"": 52428800,
        ""max_text_length"": 1500,
        ""wrong_guess_timeout_seconds"": 600,
        ""submission_user_cooldown_seconds"": 30,
        ""submission_category_cooldown_seconds"": 5,
        ""guess_command_cooldown_seconds"": 2,
        ""admin_action_cooldown_seconds"": 1,
        ""rate_limit_retention_days"": 30,
        ""orphan_media_cleanup_enabled"": true,
        ""audit_retention_days"": 365,
        ""pending_submission_retention_hours"": 48,
        ""media_warning_bytes"": 5368709120,
        ""database_warning_bytes"": 536870912,
        ""restore_test_enabled"": true,
        ""restore_test_weekday"": ""sunday"",
        ""restore_test_time_utc"": ""03:30"",
        ""monthly_submission_limit_per_guild"": 0,
        ""active_game_limit_per_guild"": 0,
        ""guild_storage_limit_bytes"": 0,
        ""offsite_backup_warning_hours"": 72,
        ""local_original_retention_days"": 30,
        ""thumbnail_max_dimension"": 640,
        ""image_compression_enabled"": false,
        ""image_compression_quality"": 85,
        ""archive_full_history_after_months"": 18,
        ""spam_review_threshold"": 40,
        ""spam_burst_count"": 5,
        ""spam_burst_window_minutes"": 10
    }
}
", new UTF8Encoding(false));
    }

    static void WriteEnvironmentFile(string appDir)
    {
        string envPath = Path.Combine(appDir, ".env");
        if (File.Exists(envPath))
        {
            Console.Write("Existing .env found. Replace token/settings? [y/N]: ");
            string answer = (Console.ReadLine() ?? "").Trim();
            if (!answer.Equals("y", StringComparison.OrdinalIgnoreCase) &&
                !answer.Equals("yes", StringComparison.OrdinalIgnoreCase))
            {
                Console.WriteLine("Keeping existing " + envPath);
                return;
            }
        }

        string token = PromptRequired("Discord bot token");
        string adminKey = Prompt("Dashboard admin key", "ImTheBestAdmin");
        InitialAdminUsername = Prompt("Initial dashboard owner username", "owner");
        InitialAdminPassword = PromptSecret("Initial dashboard owner password");
        while (String.IsNullOrWhiteSpace(InitialAdminPassword) || InitialAdminPassword.Length < 10)
        {
            Console.WriteLine("Use at least 10 characters for the dashboard owner password.");
            InitialAdminPassword = PromptSecret("Initial dashboard owner password");
        }
        string publicUrl = Prompt("Public dashboard URL or domain", "");
        string serverName = Prompt("Server label for dashboard status", "windows");
        string secretKey = RandomToken(48);

        StringBuilder env = new StringBuilder();
        env.AppendLine("DISCORD_TOKEN=" + QuoteEnv(token));
        env.AppendLine("SDAC_ADMIN_KEY=" + QuoteEnv(adminKey));
        env.AppendLine("SDAC_SECRET_KEY=" + QuoteEnv(secretKey));
        env.AppendLine("PYTHONUNBUFFERED=1");
        env.AppendLine("SDAC_PUBLIC_URL=" + QuoteEnv(publicUrl));
        env.AppendLine("SDAC_RELEASE=");
        env.AppendLine("SDAC_SERVER_NAME=" + QuoteEnv(serverName));
        File.WriteAllText(envPath, env.ToString(), new UTF8Encoding(false));
    }

    static void WriteLaunchers(string appDir)
    {
        string startBat = Path.Combine(appDir, "start-sdac.bat");
        File.WriteAllText(startBat,
@"@echo off
cd /d ""%~dp0""
if not exist ""venv\Scripts\python.exe"" (
    echo Missing venv\Scripts\python.exe. Re-run the installer after installing Python.
    pause
    exit /b 1
)
start ""SDAC Bot"" ""%~dp0venv\Scripts\python.exe"" ""%~dp0bot.py""
start ""SDAC Dashboard"" ""%~dp0venv\Scripts\python.exe"" ""%~dp0dashboard.py""
echo SDAC started.
echo Dashboard: http://localhost:5000
pause
", new UTF8Encoding(false));

        string updateBat = Path.Combine(appDir, "update-python-deps.bat");
        File.WriteAllText(updateBat,
@"@echo off
cd /d ""%~dp0""
if not exist ""venv\Scripts\python.exe"" (
    echo Missing venv\Scripts\python.exe.
    pause
    exit /b 1
)
""%~dp0venv\Scripts\python.exe"" -m pip install --upgrade pip
""%~dp0venv\Scripts\python.exe"" -m pip install -r requirements.txt
""%~dp0venv\Scripts\python.exe"" -m py_compile bot.py dashboard.py config.py database_backend.py database_migrations.py scripts\migrate_database.py scripts\export_sqlite_to_postgres.py
pause
", new UTF8Encoding(false));

        string updateSdacBat = Path.Combine(appDir, "update-sdac.bat");
        File.WriteAllText(updateSdacBat,
@"@echo off
cd /d ""%~dp0""
if not exist ""scripts\update_from_github_windows.ps1"" (
    echo Missing scripts\update_from_github_windows.ps1. Re-run the latest Windows installer.
    pause
    exit /b 1
)
powershell -NoProfile -ExecutionPolicy Bypass -File ""%~dp0scripts\update_from_github_windows.ps1"" %*
pause
", new UTF8Encoding(false));
    }

    static void InstallPythonDependencies(string appDir)
    {
        string pythonCommand = FindPythonCommand();
        if (String.IsNullOrEmpty(pythonCommand))
        {
            Console.WriteLine("Python was not found. Install Python 3.12+, then run update-python-deps.bat.");
            return;
        }

        string venvPython = Path.Combine(appDir, "venv", "Scripts", "python.exe");
        Run(pythonCommand, "-m venv \"" + Path.Combine(appDir, "venv") + "\"", appDir, true);
        Run(venvPython, "-m pip install --upgrade pip", appDir, false);
        Run(venvPython, "-m pip install \"discord.py>=2.3.2\" \"Flask>=3.0.0\" \"sentry-sdk>=2.0.0\"", appDir, false);
        Run(venvPython, "-m py_compile bot.py dashboard.py config.py database_backend.py database_migrations.py observability.py scripts\\migrate_database.py scripts\\export_sqlite_to_postgres.py", appDir, false);
        if (!String.IsNullOrWhiteSpace(InitialAdminUsername) && !String.IsNullOrWhiteSpace(InitialAdminPassword))
        {
            string script = Path.Combine(appDir, "scripts", "reset_admin_login.py");
            if (File.Exists(script))
            {
                Run(venvPython,
                    "scripts\\reset_admin_login.py --username \"" + InitialAdminUsername.Replace("\"", "\\\"") +
                    "\" --password \"" + InitialAdminPassword.Replace("\"", "\\\"") + "\" --role owner",
                    appDir,
                    false);
            }
        }
    }

    static string FindPythonCommand()
    {
        if (Run("py", "-3 --version", null, false) == 0)
        {
            return "py -3";
        }
        if (Run("python", "--version", null, false) == 0)
        {
            return "python";
        }
        return "";
    }

    static int Run(string command, string arguments, string workingDir, bool throwOnFailure)
    {
        string fileName = command;
        string extraArgs = arguments;
        if (command.StartsWith("py ", StringComparison.OrdinalIgnoreCase))
        {
            int split = command.IndexOf(' ');
            fileName = command.Substring(0, split);
            extraArgs = command.Substring(split + 1) + " " + arguments;
        }

        ProcessStartInfo psi = new ProcessStartInfo();
        psi.FileName = fileName.Trim('"');
        psi.Arguments = extraArgs;
        psi.WorkingDirectory = String.IsNullOrEmpty(workingDir) ? Environment.CurrentDirectory : workingDir;
        psi.UseShellExecute = false;
        psi.RedirectStandardOutput = true;
        psi.RedirectStandardError = true;

        Process process = Process.Start(psi);
        process.OutputDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) Console.WriteLine(e.Data); };
        process.ErrorDataReceived += delegate(object sender, DataReceivedEventArgs e) { if (e.Data != null) Console.Error.WriteLine(e.Data); };
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();
        process.WaitForExit();
        if (throwOnFailure && process.ExitCode != 0)
        {
            throw new InvalidOperationException(command + " failed with exit code " + process.ExitCode);
        }
        return process.ExitCode;
    }

    static string Sha256Hex(byte[] bytes)
    {
        using (SHA256 sha = SHA256.Create())
        {
            byte[] hash = sha.ComputeHash(bytes);
            StringBuilder builder = new StringBuilder();
            foreach (byte b in hash)
            {
                builder.Append(b.ToString("x2"));
            }
            return builder.ToString();
        }
    }

    static string RandomToken(int bytes)
    {
        byte[] data = new byte[bytes];
        using (RNGCryptoServiceProvider rng = new RNGCryptoServiceProvider())
        {
            rng.GetBytes(data);
        }
        return Convert.ToBase64String(data).TrimEnd('=').Replace('+', '-').Replace('/', '_');
    }

    static string QuoteEnv(string value)
    {
        return "\"" + value.Replace("\\", "\\\\").Replace("\"", "\\\"") + "\"";
    }

    static void Pause()
    {
        if (!Console.IsInputRedirected)
        {
            Console.WriteLine();
            Console.Write("Press Enter to exit...");
            Console.ReadLine();
        }
    }
}
"@
    [IO.File]::WriteAllText($sourcePath, $source, [Text.UTF8Encoding]::new($false))

    $cscCandidates = @(
        "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
        "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
    )
    $csc = $cscCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $csc) {
        throw "Could not find .NET Framework csc.exe."
    }

    & $csc /nologo /target:exe /platform:anycpu /optimize+ `
        /out:$OutputPath `
        /reference:System.IO.Compression.dll `
        /reference:System.IO.Compression.FileSystem.dll `
        $sourcePath
    if ($LASTEXITCODE -ne 0) {
        throw "Windows installer compilation failed."
    }

    Remove-Item -LiteralPath $zipPath -Force
    Remove-Item -LiteralPath $sourcePath -Force
}

function Copy-ReleaseHelperScripts {
    $source = Join-Path $Root "scripts\update_from_github.sh"
    $content = [IO.File]::ReadAllText($source)
    $content = $content -replace "`r`n", "`n" -replace "`r", "`n"
    foreach ($targetName in @("SDAC-Bot-Ubuntu-Update.sh", "sdac-update")) {
        $target = Join-Path $Dist $targetName
        [IO.File]::WriteAllText(
            $target,
            $content,
            [Text.UTF8Encoding]::new($false)
        )
    }

    $windowsSource = Join-Path $Root "scripts\update_from_github_windows.ps1"
    $windowsContent = [IO.File]::ReadAllText($windowsSource)
    $windowsContent = $windowsContent -replace "`r`n", "`n" -replace "`r", "`n"
    [IO.File]::WriteAllText(
        (Join-Path $Dist "SDAC-Bot-Windows-Update.ps1"),
        $windowsContent,
        [Text.UTF8Encoding]::new($false)
    )
}

New-Item -ItemType Directory -Force -Path $Dist | Out-Null
$payloadRoot = Join-Path $Dist "payload-root"
Copy-PayloadFiles -PayloadRoot $payloadRoot
Convert-PayloadTextFilesToLf -PayloadRoot $payloadRoot

New-LinuxInstaller `
    -PayloadRoot $payloadRoot `
    -OutputPath (Join-Path $Dist "SDAC-Bot-Linux-Installer.sh")

New-WindowsInstaller `
    -PayloadRoot $payloadRoot `
    -OutputPath (Join-Path $Dist "SDAC-Bot-Windows-Installer.exe")

Copy-ReleaseHelperScripts

Remove-Item -LiteralPath $payloadRoot -Recurse -Force

Get-ChildItem -LiteralPath $Dist -File | Select-Object Name, Length
