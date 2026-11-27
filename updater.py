"""Download a verified Windows executable from this project's GitHub Releases."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

VERSION = "0.5.0"
REPO = "GTAlex1/Jarvis"
ASSET = "JARVIS.exe"
MAX_SIZE = 100 * 1024 * 1024

# The helper runs after the packaged app closes. Windows may retain a lock
# briefly while the PyInstaller parent process cleans up.
INSTALL = r"""
$ErrorActionPreference = 'Stop'
$target = $env:JARVIS_UPDATE_TARGET
$staged = $env:JARVIS_UPDATE_STAGED
$backup = $staged + '.backup'
$receipt = $staged + '.ready'
$logDir = Join-Path $env:LOCALAPPDATA 'JARVIS'
$log = Join-Path $logDir 'actualizacion.log'
$nl = [Environment]::NewLine
$replaced = $false
$newApp = $null
$step = 'Preparar la actualización'
try {
    [IO.Directory]::CreateDirectory($logDir) | Out-Null
    $step = 'Esperar al cierre de JARVIS'
    $deadline = (Get-Date).AddSeconds(60)
    while (Get-Process -Id ([int]$env:JARVIS_UPDATE_PID) -ErrorAction SilentlyContinue) {
        if ((Get-Date) -gt $deadline) { throw 'JARVIS sigue abierto después de 60 segundos.' }
        Start-Sleep -Milliseconds 200
    }
    $step = 'Sustituir el ejecutable'
    # PyInstaller's parent can retain the executable after its Python child exits.
    $deadline = (Get-Date).AddSeconds(60)
    while (-not $replaced) {
        try {
            [IO.File]::Replace($staged, $target, $backup)
            $replaced = $true
        } catch {
            if ((Get-Date) -gt $deadline) { throw }
            Start-Sleep -Milliseconds 300
        }
    }
    $step = 'Abrir la nueva versión'
    $env:PYINSTALLER_RESET_ENVIRONMENT = '1'
    $env:JARVIS_UPDATE_RECEIPT = $receipt
    $newApp = Start-Process -FilePath $target -WorkingDirectory (Split-Path -Parent $target) -PassThru -ErrorAction Stop
    $step = 'Comprobar que aparece la interfaz'
    $deadline = (Get-Date).AddSeconds(40)
    while (-not (Test-Path -LiteralPath $receipt)) {
        if ($newApp.HasExited) { throw "El ejecutable se cerró con código $($newApp.ExitCode)." }
        if ((Get-Date) -gt $deadline) { throw 'La nueva versión sigue ejecutándose, pero no confirmó que la interfaz estuviera lista.' }
        Start-Sleep -Milliseconds 200
    }
    $version = [IO.File]::ReadAllText($receipt)
    [IO.File]::WriteAllText($log, "Actualización correcta a $version$nl$target")
    Remove-Item -LiteralPath $backup, $receipt -ErrorAction SilentlyContinue
} catch {
    $detail = $_.Exception.ToString()
    $restored = $false
    if ($replaced -and (($null -eq $newApp) -or $newApp.HasExited)) {
        try {
            [IO.File]::Replace($backup, $target, ($staged + '.failed'))
            Remove-Item -LiteralPath ($staged + '.failed') -ErrorAction SilentlyContinue
            $restored = $true
        } catch { $detail += $nl + 'Restauración: ' + $_.Exception.ToString() }
    }
    Remove-Item -LiteralPath $staged, $receipt -ErrorAction SilentlyContinue
    $message = "Falló el paso: $step$nl$detail$($nl)Ejecutable: $target"
    try {
        [IO.Directory]::CreateDirectory($logDir) | Out-Null
        [IO.File]::WriteAllText($log, $message)
    } catch {}
    if ($env:JARVIS_UPDATE_TEST -eq '1') {
        [Console]::Error.WriteLine($message)
        exit 1
    }
    Add-Type -AssemblyName PresentationFramework
    $recovery = if ($restored) { 'Se recuperó la versión anterior.' } else { 'Vuelve a abrir JARVIS cuando termine este proceso.' }
    [System.Windows.MessageBox]::Show(
        "No se completó la actualización.$nl$step$nl$recovery$($nl)Detalles guardados en $log",
        "JARVIS"
    ) | Out-Null
    exit 1
}
"""



def acknowledge_startup():
    receipt = os.environ.pop("JARVIS_UPDATE_RECEIPT", None)
    if not receipt:
        return
    temp = None
    try:
        path = Path(receipt)
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False, mode="w", encoding="utf-8") as output:
            temp = Path(output.name)
            output.write(VERSION)
        temp.replace(path)
    except OSError:
        if temp is not None:
            temp.unlink(missing_ok=True)


def version_tuple(tag):
    if not re.fullmatch(r"v?\d{1,6}\.\d{1,6}\.\d{1,6}", tag):
        raise ValueError("La versión publicada tiene un formato desconocido.")
    return tuple(map(int, tag.removeprefix("v").split(".")))


def latest_update():
    request = Request(
        f"https://api.github.com/repos/{REPO}/releases/latest",
        headers={"Accept": "application/vnd.github+json", "User-Agent": "JARVIS-Updater"},
    )
    with urlopen(request, timeout=10) as response:
        release = json.loads(response.read(512 * 1024))
    tag = release["tag_name"]
    if version_tuple(tag) <= version_tuple(VERSION):
        return None
    for asset in release["assets"]:
        if asset["name"] != ASSET:
            continue
        digest = asset.get("digest") or ""
        size = asset["size"]
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest) or not 0 < size <= MAX_SIZE:
            raise ValueError("GitHub no proporciona una huella SHA-256 válida para esta descarga.")
        return tag, digest[7:], size
    raise ValueError("La nueva versión todavía no contiene JARVIS.exe.")


def install_update(update):
    tag, expected_digest, size = update
    target = Path(sys.executable).resolve()
    source = f"https://github.com/{REPO}/releases/download/{tag}/{ASSET}"
    digest = hashlib.sha256()
    staged = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, suffix=".jarvis-update", delete=False) as output:
            staged = Path(output.name)
            length = 0
            with urlopen(source, timeout=20) as download:
                while chunk := download.read(128 * 1024):
                    length += len(chunk)
                    if length > size:
                        raise ValueError("El archivo descargado supera el tamaño publicado.")
                    output.write(chunk)
                    digest.update(chunk)
            if length != size or digest.hexdigest() != expected_digest:
                raise ValueError("La descarga no coincide con la huella SHA-256 publicada.")
        env = dict(os.environ, JARVIS_UPDATE_TARGET=str(target), JARVIS_UPDATE_STAGED=str(staged),
                   JARVIS_UPDATE_PID=str(os.getpid()))
        powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
        helper = subprocess.Popen(
            [str(powershell), "-NoProfile", "-STA", "-EncodedCommand",
             base64.b64encode(INSTALL.encode("utf-16le")).decode("ascii")],
            env=env, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            helper.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            return
        raise OSError("Windows cerró el actualizador antes de que pudiera instalar la actualización.")
    except (OSError, ValueError):
        if staged is not None:
            staged.unlink(missing_ok=True)
        raise
