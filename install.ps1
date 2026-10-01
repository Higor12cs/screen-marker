[CmdletBinding()]
param(
    [switch]$OneFile,
    [switch]$Desktop,
    [switch]$Autostart,
    [switch]$NoLaunch
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$appName = 'ScreenMarker'
$target = Join-Path $env:LOCALAPPDATA "Programs\$appName"

if ($OneFile) {
    $source = Join-Path $root 'dist\ScreenMarker.exe'
} else {
    $source = Join-Path $root 'dist\ScreenMarker'
}

if (-not (Test-Path $source)) {
    throw "Nao encontrei o build em $source. Rode .\build.ps1 primeiro."
}

Write-Host "== Instalando $appName em $target ==" -ForegroundColor Cyan

Get-Process -Name $appName -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host 'Fechando instancia em execucao...' -ForegroundColor DarkGray
    try { $_.Kill(); $_.WaitForExit(5000) } catch {}
}

if (Test-Path $target) { Remove-Item $target -Recurse -Force }
New-Item -ItemType Directory -Path $target -Force | Out-Null

if ($OneFile) {
    Copy-Item $source (Join-Path $target 'ScreenMarker.exe') -Force
} else {
    Copy-Item (Join-Path $source '*') $target -Recurse -Force
}

$uninstaller = Join-Path $root 'uninstall.ps1'
if (Test-Path $uninstaller) { Copy-Item $uninstaller $target -Force }

$exe = Join-Path $target 'ScreenMarker.exe'
$shell = New-Object -ComObject WScript.Shell

$startMenu = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'
$shortcut = $shell.CreateShortcut((Join-Path $startMenu "$appName.lnk"))
$shortcut.TargetPath = $exe
$shortcut.WorkingDirectory = $target
$shortcut.IconLocation = $exe
$shortcut.Description = 'Marcador de tela com atalhos configuraveis'
$shortcut.Save()

if ($Desktop) {
    $desktopLink = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) "$appName.lnk"))
    $desktopLink.TargetPath = $exe
    $desktopLink.WorkingDirectory = $target
    $desktopLink.IconLocation = $exe
    $desktopLink.Save()
}

if ($Autostart) {
    Set-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name $appName -Value "`"$exe`""
}

$uninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName"
New-Item -Path $uninstallKey -Force | Out-Null
$version = '1.0.0'
$sizeKb = [int]((Get-ChildItem $target -Recurse -File | Measure-Object -Property Length -Sum).Sum / 1KB)
Set-ItemProperty -Path $uninstallKey -Name 'DisplayName' -Value 'ScreenMarker'
Set-ItemProperty -Path $uninstallKey -Name 'DisplayVersion' -Value $version
Set-ItemProperty -Path $uninstallKey -Name 'Publisher' -Value 'Higor Carneiro'
Set-ItemProperty -Path $uninstallKey -Name 'DisplayIcon' -Value $exe
Set-ItemProperty -Path $uninstallKey -Name 'InstallLocation' -Value $target
Set-ItemProperty -Path $uninstallKey -Name 'EstimatedSize' -Value $sizeKb -Type DWord
Set-ItemProperty -Path $uninstallKey -Name 'NoModify' -Value 1 -Type DWord
Set-ItemProperty -Path $uninstallKey -Name 'NoRepair' -Value 1 -Type DWord
Set-ItemProperty -Path $uninstallKey -Name 'UninstallString' -Value "powershell -NoProfile -ExecutionPolicy Bypass -File `"$target\uninstall.ps1`""

Write-Host 'Instalado.' -ForegroundColor Green
Write-Host "Executavel: $exe"
Write-Host 'Atalho criado no menu Iniciar. Desinstale por "Adicionar ou remover programas".'

if (-not $NoLaunch) {
    Start-Process $exe
    Write-Host 'ScreenMarker iniciado - procure o icone na area de notificacao (Ctrl+Alt+D para marcar).' -ForegroundColor Cyan
}
