[CmdletBinding()]
param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$ApiKey = "local-demo-api-key-change-me",
    [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Push-Location $RepoRoot

$script:failures = New-Object System.Collections.Generic.List[string]
$script:record = $null

function Wait-ForUrl {
    param([string]$Url, [int]$Timeout)

    $deadline = (Get-Date).AddSeconds($Timeout)
    while ((Get-Date) -lt $deadline) {
        try {
            return Invoke-RestMethod -Uri $Url -TimeoutSec 5
        } catch {
            Start-Sleep -Seconds 2
        }
    }
    throw "Timed out waiting for $Url"
}

function Assert-Equal {
    param($Expected, $Actual, [string]$Label)

    if ("$Expected" -ne "$Actual") {
        throw "$Label expected '$Expected' but got '$Actual'"
    }
}

function Assert-Status {
    param([scriptblock]$Request, [int]$Expected)

    $code = 0
    try {
        & $Request | Out-Null
        $code = 200
    } catch {
        if ($_.Exception.Response) {
            $code = [int]$_.Exception.Response.StatusCode.value__
        } else {
            throw
        }
    }
    if ($code -ne $Expected) {
        throw "Expected HTTP $Expected but got $code"
    }
}

function Check {
    param([string]$Name, [scriptblock]$Body)

    try {
        & $Body
        Write-Host "PASS  $Name" -ForegroundColor Green
    } catch {
        Write-Host "FAIL  $Name -- $($_.Exception.Message)" -ForegroundColor Red
        $script:failures.Add($Name)
    }
}

try {
    $health = Wait-ForUrl "$BaseUrl/health" $TimeoutSeconds
    Check "health endpoint" { Assert-Equal "ok" $health.status "status" }

    $ready = Wait-ForUrl "$BaseUrl/ready" $TimeoutSeconds
    Check "ready endpoint (DB + Vault)" { Assert-Equal "ready" $ready.status "status" }

    $headers = @{ "X-API-Key" = $ApiKey; "Content-Type" = "application/json" }

    Check "create encrypted record" {
        $body = @{ record_type = "smoke_test"; value = "0901234567" } | ConvertTo-Json
        $script:record = Invoke-RestMethod -Method Post -Uri "$BaseUrl/records" `
            -Headers $headers -Body $body
        Assert-Equal "encrypted_and_stored" $script:record.status "status"
        if (-not $script:record.id) {
            throw "response is missing id"
        }
    }

    Check "read back plaintext" {
        if (-not $script:record) { throw "no record from previous step" }
        $read = Invoke-RestMethod -Uri "$BaseUrl/records/$($script:record.id)" -Headers $headers
        Assert-Equal "0901234567" $read.value "value"
    }

    Check "metadata exposes ciphertext size" {
        if (-not $script:record) { throw "no record from previous step" }
        $meta = Invoke-RestMethod -Uri "$BaseUrl/records/$($script:record.id)/metadata" -Headers $headers
        if ([int]$meta.ciphertext_bytes -le 0) { throw "ciphertext_bytes is not positive" }
        if (-not $meta.kek_name) { throw "missing kek_name" }
    }

    Check "missing API key rejected" {
        Assert-Status { Invoke-RestMethod -Uri "$BaseUrl/records" } 401
    }

    Check "wrong API key rejected" {
        Assert-Status {
            Invoke-RestMethod -Uri "$BaseUrl/records" -Headers @{ "X-API-Key" = "wrong-key" }
        } 401
    }

    Check "record key cannot call admin" {
        Assert-Status {
            Invoke-RestMethod -Method Post -Uri "$BaseUrl/admin/rotation/transit-key" -Headers $headers
        } 403
    }

    Check "plaintext absent from database" {
        $sql = "SELECT count(*) FROM sensitive_records WHERE encode(ciphertext, 'escape') LIKE '%0901234567%' OR encrypted_dek LIKE '%0901234567%';"
        $count = docker compose exec -T postgres psql -U postgres -d encryption_db -tA -c $sql
        if ($LASTEXITCODE -ne 0) { throw "psql failed" }
        if ([int]$count -ne 0) { throw "plaintext was found in the database" }
    }
}
finally {
    if ($script:record -and $script:record.id) {
        $cleanup = "DELETE FROM audit_events WHERE record_id = '$($script:record.id)'; DELETE FROM sensitive_records WHERE id = '$($script:record.id)';"
        docker compose exec -T postgres psql -U postgres -d encryption_db -c $cleanup | Out-Null
    }
    Pop-Location
}

if ($script:failures.Count -gt 0) {
    Write-Host "$($script:failures.Count) check(s) failed: $($script:failures -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "Smoke test passed." -ForegroundColor Green
