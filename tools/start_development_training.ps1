[CmdletBinding()]
param(
    [ValidatePattern('^[a-z0-9][a-z0-9-]{0,90}$')]
    [string]$RunId = 'sohas-reviewed-development-20261026-v1',
    [switch]$Worker
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$repo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
Set-Location -LiteralPath $repo
$prepared = Join-Path $repo "data\processed\$RunId"
$logs = Join-Path $repo "runs\launch-$RunId"
$python = Join-Path $repo '.venv-ml\Scripts\python.exe'
$configPath = Join-Path $prepared 'training.json'
$authorizationPath = Join-Path $prepared 'development-authorization.json'
$config = Get-Content -LiteralPath $configPath -Encoding UTF8 -Raw | ConvertFrom-Json
$authorization = Get-Content -LiteralPath $authorizationPath -Encoding UTF8 -Raw | ConvertFrom-Json
if ($config.recipe_id -ne 'DEV-SOHAS' -or $config.run_name -ne $RunId -or
    $config.approval_required -ne $true -or $authorization.status -ne 'authorized_development_only' -or
    $authorization.final_evaluation_allowed -ne $false) {
    throw 'Only the bound development-only profile can be launched here.'
}
if (!(Test-Path -LiteralPath $python)) { throw 'Training Python is missing.' }
$env:PYTHONPATH = Join-Path $repo 'src'
$env:CUBLAS_WORKSPACE_CONFIG = ':4096:8'

if ($Worker) {
    if (!(Test-Path -LiteralPath $logs)) { throw 'Parent launch directory is missing.' }
    # CreateNew fails rather than allowing a second worker to launch the same run.
    $claim = [IO.File]::Open((Join-Path $logs 'worker-claim'), [IO.FileMode]::CreateNew)
    $claim.Close()
    $exitCode = 99
    try {
        # Windows PowerShell represents native stderr progress as ErrorRecords.
        # Continue captures it without terminating an otherwise healthy trainer.
        $ErrorActionPreference = 'Continue'
        & $python -m edge_threat_response.training `
            --config $configPath `
            --data (Join-Path $prepared 'data.yaml') `
            --dataset-manifest (Join-Path $prepared 'DEV-manifest.jsonl') `
            --approval $authorizationPath `
            --output-dir (Join-Path $repo 'runs\training') --require-cuda `
            1> (Join-Path $logs 'stdout.log') 2> (Join-Path $logs 'stderr.log')
        $exitCode = $LASTEXITCODE
    }
    catch {
        $exitCode = 98
        [IO.File]::AppendAllText((Join-Path $logs 'launcher-error.log'), $_.Exception.Message)
    }
    finally {
        [IO.File]::WriteAllText((Join-Path $logs 'exit-code.txt'), [string]$exitCode)
    }
    exit $exitCode
}

if ((Test-Path -LiteralPath $logs) -or
    (Test-Path -LiteralPath (Join-Path $repo "runs\training\$RunId")) -or
    (Test-Path -LiteralPath (Join-Path $repo "runs\training\$RunId-invocation.json"))) {
    throw 'This run/launch ID already exists; do not overwrite or double-launch.'
}
if (Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match 'edge_threat_response\.training(\s|$)' }) {
    throw 'Another project training process is active.'
}
New-Item -ItemType Directory -Path $logs | Out-Null
$powershell = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
$commandLine = '"{0}" -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy RemoteSigned -File "{1}" -RunId "{2}" -Worker' -f $powershell, $PSCommandPath, $RunId
$result = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{CommandLine = $commandLine}
if ($result.ReturnValue -ne 0) { throw "Detached process creation failed: $($result.ReturnValue)" }
$record = [ordered]@{
    run_id = $RunId
    scope = 'development_only'
    launcher_pid = $result.ProcessId
    return_value = $result.ReturnValue
    git_commit = (git rev-parse HEAD)
    launcher_sha256 = (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
    created_utc = [DateTime]::UtcNow.ToString('o')
}
$record | ConvertTo-Json | Out-File -LiteralPath (Join-Path $logs 'launch.json') -Encoding UTF8
$record | ConvertTo-Json
