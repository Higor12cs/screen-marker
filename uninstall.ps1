[CmdletBinding()]
param([switch]$KeepSettings)

$ErrorActionPreference = 'SilentlyContinue'
$appName = 'ScreenMarker'
$target = Join-Path $env:LOCALAPPDATA "Programs\$appName"

Get-Process -Name $appName | ForEach-Object { try { $_.Kill(); $_.WaitForExit(5000) } catch {} }

Remove-ItemProperty -Path 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -Name $appName
Remove-Item -Path "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$appName" -Recurse -Force

Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\$appName.lnk") -Force
Remove-Item (Join-Path ([Environment]::GetFolderPath('Desktop')) "$appName.lnk") -Force

if (-not $KeepSettings) {
    Remove-Item (Join-Path $env:APPDATA $appName) -Recurse -Force
}

if (Test-Path $target) {
    Start-Process cmd.exe -ArgumentList '/c', 'timeout /t 2 /nobreak > nul & rmdir /s /q "' + $target + '"' -WindowStyle Hidden
}

Write-Host 'ScreenMarker removido.' -ForegroundColor Green
