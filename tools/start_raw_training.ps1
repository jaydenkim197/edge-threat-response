[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Queue,
    [string]$RuntimeRoot,
    [switch]$Worker
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repo
$runtime = if ($RuntimeRoot) { (Resolve-Path -LiteralPath $RuntimeRoot).Path } else { $repo }
$queuePath = (Resolve-Path -LiteralPath $Queue).Path
$spec = Get-Content -LiteralPath $queuePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($spec.scope -ne 'raw_source_annotations_development_only' -or
    $spec.human_review_complete -ne $false -or $spec.final_evaluation_allowed -ne $false -or
    $spec.suite_id -notmatch '^[a-z0-9][a-z0-9-]{0,90}$') { throw 'Invalid raw-only queue scope.' }
$logs = Join-Path $runtime ('runs\launch-' + $spec.suite_id)
$python = Join-Path $runtime '.venv-ml\Scripts\python.exe'
$env:PYTHONPATH = Join-Path $repo 'src'
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'
$env:YOLO_AUTOINSTALL = 'false'
if ($Worker) {
    $claim = [IO.File]::Open((Join-Path $logs 'worker-claim'), [IO.FileMode]::CreateNew)
    $claim.Close()
    $exitCode = 99
    try {
        $ErrorActionPreference = 'Continue'
        & $python -m edge_threat_response.raw_training run --queue $queuePath --output-dir (Join-Path $runtime 'runs\training') `
            1> (Join-Path $logs 'stdout.log') 2> (Join-Path $logs 'stderr.log')
        $exitCode = $LASTEXITCODE
    } catch {
        $exitCode = 98
        [IO.File]::AppendAllText((Join-Path $logs 'launcher-error.log'), $_.Exception.Message)
    } finally { [IO.File]::WriteAllText((Join-Path $logs 'exit-code.txt'), [string]$exitCode) }
    exit $exitCode
}
if ((Test-Path -LiteralPath $logs) -or (Test-Path -LiteralPath (Join-Path $runtime 'runs\training\gpu0-training.lock'))) {
    throw 'Existing launcher/queue claim; do not overwrite or double-launch.'
}
if (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match 'edge_threat_response\.(training|raw_training)(\s|$)' }) {
    throw 'Another project training process is active.'
}
New-Item -ItemType Directory -Path $logs | Out-Null
$powershell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$commandLine = '"{0}" -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File "{1}" -Queue "{2}" -RuntimeRoot "{3}" -Worker' -f $powershell, $PSCommandPath, $queuePath, $runtime
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $commandLine}
if ($result.ReturnValue -ne 0) { throw "Detached worker failed: $($result.ReturnValue)" }
[ordered]@{pid=$result.ProcessId; queue=$queuePath; git_commit=(git rev-parse HEAD); created_utc=[DateTime]::UtcNow.ToString('o')} |
    ConvertTo-Json | Out-File -LiteralPath (Join-Path $logs 'launch.json') -Encoding UTF8
Get-Content -LiteralPath (Join-Path $logs 'launch.json')
