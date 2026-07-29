#Requires -RunAsAdministrator
<#
Recupera acceso a D:\rag\.env despues de un bloqueo accidental de ACLs.
Ejecutar como Administrador:
    powershell -ExecutionPolicy Bypass -File D:\rag\recover_env_acl.ps1
#>
$ErrorActionPreference = "Stop"
$path = "D:\rag\.env"

if (-not (Test-Path -LiteralPath $path)) {
    Write-Error "No existe $path"
    exit 1
}

Write-Host "[1/4] Tomando propiedad del archivo..."
takeown /F "$path" | Out-Null

Write-Host "[2/4] Restaurando ACLs heredadas..."
icacls "$path" /reset | Out-Null

Write-Host "[3/4] Otorgando control total al usuario actual..."
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
icacls "$path" /grant "${currentUser}:F" | Out-Null

Write-Host "[4/4] Eliminando permisos de otros usuarios..."
# Quita grupos de usuarios no administrativos manteniendo al propietario/admin
icacls "$path" /remove "BUILTIN\Users" "NT AUTHORITY\Authenticated Users" 2>$null | Out-Null

$acl = Get-Acl -LiteralPath $path
Write-Host "Propietario: $($acl.Owner)"
Write-Host "ACL actual:"
icacls "$path"

Write-Host "[OK] $path recuperado. Puedes leerlo ahora."
