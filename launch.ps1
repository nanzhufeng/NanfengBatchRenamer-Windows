$ErrorActionPreference = "Stop"
$appDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $appDir
$env:PYTHONPATH = Join-Path $appDir "src"

$logDir = Join-Path $appDir "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$errorLog = Join-Path $logDir "launch_error.txt"

try {
    Start-Process -FilePath "pythonw.exe" -ArgumentList @("-m", "batch_renamer") -WorkingDirectory $appDir -WindowStyle Hidden
}
catch {
    $_.Exception.Message | Out-File -FilePath $errorLog -Encoding UTF8
    exit 1
}
