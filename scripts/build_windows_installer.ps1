param(
    [string]$Version = "1.1.5"
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$innoCompiler = Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"
$specFile = Join-Path $projectRoot "南枫批量改名-Windows.spec"
$innoScript = Join-Path $projectRoot "installer\NanfengBatchRenamer-Windows.iss"
$releaseDir = Join-Path $projectRoot "release"
$installerName = "NanfengBatchRenamer-Windows-v$Version-Setup.exe"
$installerPath = Join-Path $releaseDir $installerName
$checksumPath = "$installerPath.sha256"

if (-not (Test-Path -LiteralPath $innoCompiler)) {
    throw "未找到 Inno Setup 7 编译器：$innoCompiler"
}

# Keep unrelated desktop-tool DLLs out of PyInstaller dependency discovery.
$buildOriginalPath = $env:PATH
$buildPythonDir = Split-Path -Parent (Get-Command python.exe).Source
$env:PATH = "$buildPythonDir;$buildPythonDir\Scripts;$env:SystemRoot\System32;$env:SystemRoot"

Push-Location $projectRoot
try {
    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) { throw "自动测试失败" }

    python -m compileall src tests scripts
    if ($LASTEXITCODE -ne 0) { throw "源码编译检查失败" }

    python scripts\check_icon_assets.py
    if ($LASTEXITCODE -ne 0) { throw "Icon asset validation failed" }

    python -m PyInstaller --noconfirm --clean $specFile
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller 构建失败" }

    & $innoCompiler "/DMyAppVersion=$Version" $innoScript
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup 构建失败" }

    if (-not (Test-Path -LiteralPath $installerPath)) {
        throw "安装包未生成：$installerPath"
    }

    $hash = (Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash *$installerName" | Set-Content -LiteralPath $checksumPath -Encoding ascii
    Write-Host "安装包：$installerPath"
    Write-Host "SHA-256：$hash"
}
finally {
    $env:PATH = $buildOriginalPath
    Pop-Location
}
