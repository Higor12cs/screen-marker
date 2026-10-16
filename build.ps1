[CmdletBinding()]
param(
    [switch]$OneFile,
    [switch]$SkipDeps,
    [switch]$Zip
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $root

Write-Host '== ScreenMarker: build ==' -ForegroundColor Cyan

if (-not $SkipDeps) {
    Write-Host 'Instalando dependencias...' -ForegroundColor DarkGray
    python -m pip install --upgrade --quiet --disable-pip-version-check pyinstaller PySide6-Essentials pillow
}

python tools\make_icon.py

$excludes = @(
    'tkinter', 'numpy', 'pandas', 'matplotlib', 'scipy', 'PIL', 'pytest',
    'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.QtQuick3D',
    'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets', 'PySide6.QtWebChannel', 'PySide6.QtWebSockets',
    'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.Qt3DCore',
    'PySide6.QtBluetooth', 'PySide6.QtNfc', 'PySide6.QtPositioning',
    'PySide6.QtSerialPort', 'PySide6.QtSql', 'PySide6.QtTest', 'PySide6.QtPdf',
    'PySide6.QtPdfWidgets', 'PySide6.QtDesigner', 'PySide6.QtHelp',
    'PySide6.QtOpenGL', 'PySide6.QtOpenGLWidgets', 'PySide6.QtSpatialAudio',
    'PySide6.QtTextToSpeech', 'PySide6.QtRemoteObjects', 'PySide6.QtScxml',
    'PySide6.QtSensors', 'PySide6.QtStateMachine', 'PySide6.QtHttpServer'
)

$arguments = @(
    '--noconfirm', '--clean', '--windowed',
    '--name', 'ScreenMarker',
    '--icon', 'screen_marker\resources\icon.ico'
)
foreach ($module in $excludes) { $arguments += @('--exclude-module', $module) }
if ($OneFile) { $arguments += '--onefile' }
$arguments += 'run.py'

python -m PyInstaller @arguments
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller falhou.' }

if ($OneFile) {
    $output = Join-Path $root 'dist\ScreenMarker.exe'
} else {
    $output = Join-Path $root 'dist\ScreenMarker\ScreenMarker.exe'
}

if (-not (Test-Path $output)) { throw "Executavel nao encontrado em $output" }

$size = [math]::Round((Get-Item $output).Length / 1MB, 1)
Write-Host ''
Write-Host "Build pronto: $output ($size MB)" -ForegroundColor Green

if ($Zip -and -not $OneFile) {
    $zipPath = Join-Path $root 'dist\ScreenMarkerPortable.zip'
    if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
    Compress-Archive -Path (Join-Path $root 'dist\ScreenMarker\*') -DestinationPath $zipPath
    Write-Host "Pacote portatil: $zipPath" -ForegroundColor Green
}

Write-Host 'Para instalar: .\install.ps1' -ForegroundColor Cyan
