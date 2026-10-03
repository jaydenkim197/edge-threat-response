param(
    [string]$ReviewDir = 'data/review/sohas-click-review-20261003',
    [ValidateRange(1024, 65535)][int]$Port = 8765,
    [switch]$NoBrowser
)
$ErrorActionPreference = 'Stop'
$reviewRepo = Split-Path -Parent $PSScriptRoot
if (-not [IO.Path]::IsPathRooted($ReviewDir)) { $ReviewDir = Join-Path $reviewRepo $ReviewDir }
$reviewPack = (Resolve-Path -LiteralPath $ReviewDir).Path
$reviewCsv = [IO.File]::ReadAllBytes((Join-Path $reviewPack 'review.csv'))
$reviewEvidence = [IO.File]::ReadAllBytes((Join-Path $reviewPack 'image-evidence.jsonl'))
$reviewHasher = [Security.Cryptography.SHA256]::Create()
try { $reviewHash = ([BitConverter]::ToString($reviewHasher.ComputeHash([byte[]]($reviewCsv + $reviewEvidence)))).Replace('-', '').ToLowerInvariant() }
finally { $reviewHasher.Dispose() }
$reviewUrl = "http://127.0.0.1:$Port"
function Get-ReviewState {
    try { Invoke-RestMethod "$reviewUrl/api/items" -TimeoutSec 2 }
    catch { $null }
}
$reviewState = Get-ReviewState
if (-not $reviewState) {
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $Port is occupied by another service. Use -Port with a free port."
    }
    $reviewPython = @('.venv-ml/Scripts/python.exe', '.venv/Scripts/python.exe') |
        ForEach-Object { Join-Path $reviewRepo $_ } | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $reviewPython) { $reviewPython = (Get-Command python -ErrorAction Stop).Source }
    $reviewPreviousPath = $env:PYTHONPATH
    try {
        $env:PYTHONPATH = (Join-Path $reviewRepo 'src') + $(if ($reviewPreviousPath) { ";$reviewPreviousPath" })
        $reviewProcess = Start-Process -FilePath $reviewPython -WindowStyle Hidden -WorkingDirectory $reviewRepo -PassThru `
            -ArgumentList "-X utf8 -m edge_threat_response.dataset.review_web --review-dir `"$reviewPack`" --port $Port" `
            -RedirectStandardOutput (Join-Path $reviewPack "web-$Port-stdout.log") `
            -RedirectStandardError (Join-Path $reviewPack "web-$Port-stderr.log")
    }
    finally { $env:PYTHONPATH = $reviewPreviousPath }
    for ($reviewAttempt = 0; $reviewAttempt -lt 20; $reviewAttempt++) {
        $reviewState = Get-ReviewState
        if ($reviewState) { break }
        if ($reviewProcess.HasExited) { throw "Review server exited. Read web-$Port-stderr.log in the review folder." }
        Start-Sleep -Milliseconds 250
    }
    if (-not $reviewState) { throw 'Review server did not become ready. Check the review folder logs.' }
}
if ($reviewState.pack_hash -ne $reviewHash) { throw "Port $Port serves a different review pack. Use another -Port." }
Write-Output "Review ready: $reviewUrl"
if (-not $NoBrowser) { Start-Process $reviewUrl }
