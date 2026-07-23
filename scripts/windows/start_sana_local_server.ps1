param(
    [string]$VmName = "Sana-Ubuntu-Test",
    [string]$VmHost = "172.17.188.232",
    [string]$VmUser = "sana",
    [string]$SshKey = "D:\HyperV\Sana-Ubuntu-Test\sana_vm_ed25519",
    [string]$RemoteAppDir = "/opt/sana-test/ScreenshotSubmit",
    [string]$CloudflaredPath = "D:\Tools\cloudflared\cloudflared.exe",
    [string]$StatusPath = "$env:USERPROFILE\.sana-chan\local-tunnel-status.json",
    [int]$StartupTimeoutSeconds = 120,
    [int]$TunnelUrlTimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-File {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "$Label was not found at $Path"
    }
}

function Invoke-SanaSsh {
    param([string]$Command)
    Assert-File -Path $SshKey -Label "SSH key"
    & ssh -i $SshKey -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 "$VmUser@$VmHost" $Command
    if ($LASTEXITCODE -ne 0) {
        throw "SSH command failed with exit code $LASTEXITCODE"
    }
}

function Invoke-SanaRemoteScript {
    param([string]$Script)
    $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Script))
    Invoke-SanaSsh -Command "printf '%s' '$encoded' | base64 -d | bash"
}

function Wait-ForSsh {
    $deadline = (Get-Date).AddSeconds($StartupTimeoutSeconds)
    do {
        try {
            & ssh -i $SshKey -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=5 "$VmUser@$VmHost" "true" 2>$null
            if ($LASTEXITCODE -eq 0) {
                return
            }
        }
        catch {
            Start-Sleep -Seconds 2
        }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "Timed out waiting for SSH at $VmUser@$VmHost"
}

function Start-SanaVm {
    $vm = Get-VM -Name $VmName -ErrorAction SilentlyContinue
    if (-not $vm) {
        Write-Step "VM $VmName was not found; assuming $VmHost is already reachable"
        return
    }
    if ($vm.State -ne "Running") {
        Write-Step "Starting Hyper-V VM $VmName"
        Start-VM -Name $VmName | Out-Null
    }
    else {
        Write-Step "Hyper-V VM $VmName is already running"
    }
}

function Stop-PreviousCloudflareTunnel {
    if (-not (Test-Path -LiteralPath $StatusPath)) {
        return
    }
    try {
        $status = Get-Content -Raw -LiteralPath $StatusPath | ConvertFrom-Json
        $pidToStop = [int]$status.cloudflared_pid
        if ($pidToStop -le 0) {
            return
        }
        $process = Get-Process -Id $pidToStop -ErrorAction SilentlyContinue
        if ($process -and $process.ProcessName -like "cloudflared*") {
            Write-Step "Stopping previous Cloudflare tunnel process $pidToStop"
            Stop-Process -Id $pidToStop -Force
            Start-Sleep -Seconds 1
        }
    }
    catch {
        Write-Host "Could not clean up previous tunnel process: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}
function Start-CloudflareQuickTunnel {
    param([string]$LocalServiceUrl)

    Assert-File -Path $CloudflaredPath -Label "cloudflared"
    $statusDirectory = Split-Path -Parent $StatusPath
    New-Item -ItemType Directory -Force -Path $statusDirectory | Out-Null

    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $stdoutLog = Join-Path $statusDirectory "cloudflared-$timestamp.out.log"
    $stderrLog = Join-Path $statusDirectory "cloudflared-$timestamp.err.log"

    Write-Step "Opening Cloudflare quick tunnel to $LocalServiceUrl"
    $process = Start-Process -FilePath $CloudflaredPath `
        -ArgumentList @("tunnel", "--url", $LocalServiceUrl) `
        -RedirectStandardOutput $stdoutLog `
        -RedirectStandardError $stderrLog `
        -WindowStyle Hidden `
        -PassThru

    $deadline = (Get-Date).AddSeconds($TunnelUrlTimeoutSeconds)
    $tunnelUrl = $null
    do {
        Start-Sleep -Milliseconds 500
        if ($process.HasExited) {
            $log = ""
            if (Test-Path -LiteralPath $stdoutLog) { $log += Get-Content -Raw -LiteralPath $stdoutLog }
            if (Test-Path -LiteralPath $stderrLog) { $log += Get-Content -Raw -LiteralPath $stderrLog }
            throw "cloudflared exited before a tunnel URL was created.`n$log"
        }
        $log = ""
        if (Test-Path -LiteralPath $stdoutLog) { $log += Get-Content -Raw -LiteralPath $stdoutLog }
        if (Test-Path -LiteralPath $stderrLog) { $log += Get-Content -Raw -LiteralPath $stderrLog }
        if ($log -match "https://[a-z0-9-]+\.trycloudflare\.com") {
            $tunnelUrl = $Matches[0]
            break
        }
    } while ((Get-Date) -lt $deadline)

    if (-not $tunnelUrl) {
        throw "Timed out waiting for cloudflared to print a trycloudflare.com URL. See $stderrLog"
    }

    return [pscustomobject]@{
        ProcessId = $process.Id
        TunnelUrl = $tunnelUrl
        StdoutLog = $stdoutLog
        StderrLog = $stderrLog
    }
}

function Update-RemoteEnvironment {
    param([string]$TunnelUrl)

    $safeAppDir = $RemoteAppDir.Replace("'", "'\''")
    $safeUrl = $TunnelUrl.Replace("'", "'\''")
    $remoteScript = @"
set -Eeuo pipefail
cd '$safeAppDir'
touch .env
set_env() {
    key="`$1"
    value="`$2"
    if grep -q "^`$key=" .env; then
        sed -i "s|^`$key=.*|`$key=`$value|" .env
    else
        printf '\n%s=%s\n' "`$key" "`$value" >> .env
    fi
}
set_env SANA_DASHBOARD_URL '$safeUrl'
set_env SDAC_PUBLIC_URL '$safeUrl'
docker compose up -d dashboard bot
docker compose ps
"@
    Write-Step "Updating VM .env public URL fields and restarting Sana-Chan"
    Invoke-SanaRemoteScript -Script $remoteScript
}

Write-Step "Preparing Sana-Chan local server"
Start-SanaVm
Wait-ForSsh

Write-Step "Starting dashboard and bot containers"
$startScript = @"
set -Eeuo pipefail
cd '$($RemoteAppDir.Replace("'", "'\''"))'
docker compose up -d dashboard bot
docker compose ps
"@
Invoke-SanaRemoteScript -Script $startScript

$localServiceUrl = "http://$VmHost`:5000"
Stop-PreviousCloudflareTunnel
$tunnel = Start-CloudflareQuickTunnel -LocalServiceUrl $localServiceUrl
Update-RemoteEnvironment -TunnelUrl $tunnel.TunnelUrl

$status = [ordered]@{
    started_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    vm_name = $VmName
    vm_host = $VmHost
    vm_user = $VmUser
    remote_app_dir = $RemoteAppDir
    local_service_url = $localServiceUrl
    tunnel_url = $tunnel.TunnelUrl
    cloudflared_pid = $tunnel.ProcessId
    cloudflared_stdout_log = $tunnel.StdoutLog
    cloudflared_stderr_log = $tunnel.StderrLog
}
$status | ConvertTo-Json | Set-Content -LiteralPath $StatusPath -Encoding UTF8

Write-Host ""
Write-Host "Sana-Chan is running." -ForegroundColor Green
Write-Host "Dashboard: $($tunnel.TunnelUrl)"
Write-Host "Status:    $StatusPath"
Write-Host "Logs:      $($tunnel.StderrLog)"
Write-Host ""
Write-Host "Add this Discord OAuth redirect if the tunnel URL changed:"
Write-Host "$($tunnel.TunnelUrl)/account/oauth/callback" -ForegroundColor Yellow